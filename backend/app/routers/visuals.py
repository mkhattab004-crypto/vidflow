from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project, Scene
from app.services import pexels, pixabay, wikimedia
from app.services.storage import get_project_assets_dir, ensure_project_dirs
import os
import re
import httpx
import logging
import uuid
from datetime import datetime, timezone
router = APIRouter(prefix="/visuals", tags=["visuals"])

logger = logging.getLogger(__name__)

ISLAMIC_DETECTION_KEYWORDS = {
    "islam", "islamic", "quran", "qur'an", "koran", "ayat", "surah", "hadith", "prophet", "allah", "prayer", "salah", "mosque", "ramadan", "dua", "dhikr",
    "إسلام", "اسلامي", "القرآن", "آية", "سورة", "حديث", "النبي", "الله", "الصلاة", "مسجد", "رمضان", "دعاء", "ذكر",
    "islami", "kuran", "ayet", "sure", "hadis", "peygamber", "namaz", "cami", "ramazan", "zikir",
}

ISLAMIC_BLOCKED_KEYWORDS = {
    "woman", "girl", "female model", "hair", "uncovered hair", "sexy", "bikini", "swimsuit", "beach girl", "dancing", "party", "nightclub",
    "romance", "couple kissing", "alcohol", "bar", "fashion model", "lingerie", "body", "legs", "cleavage", "makeup model", "yoga woman", "fitness woman",
    "امرأة", "بنت", "شعر", "عارضة", "رقص", "حفلة", "بحر", "مايوه", "حب", "قبلات", "كحول",
    "kadın", "kız", "saç", "model", "dans", "parti", "plaj", "aşk", "öpüşme", "alkol",
}

ISLAMIC_PROPHETIC_BLOCKLIST = {"muhammad", "prophet muhammad", "prophet", "messenger", "rasul", "sahaba", "companion", "angel", "allah figure", "تصوير النبي", "صحابة", "ملائكة"}
ISLAMIC_SAFE_QUERY_TERMS = [
    "mosque interior", "quran close up", "muslim prayer silhouette", "islamic architecture", "arabic calligraphy", "prayer beads",
    "crescent moon", "night sky", "spiritual light", "old manuscript", "peaceful desert", "minaret", "muslim man praying", "hands dua",
]
ISLAMIC_FALLBACK_QUERIES = [
    "mosque interior", "quran close up", "islamic calligraphy", "minaret night", "prayer beads close up", "night sky stars",
]


def _normalize_text(value: str | None) -> str:
    return (value or "").lower().strip()


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _detect_islamic_visual_profile(project: Project, scenes: list[Scene]) -> bool:
    haystack = " ".join([
        _normalize_text(project.niche),
        _normalize_text(project.title),
        _normalize_text(project.idea),
        _normalize_text(project.description),
        " ".join(_normalize_text(s.script_text) for s in scenes),
        " ".join(_normalize_text(s.script_ar) for s in scenes),
    ])
    return bool(project.is_islamic or _contains_any(haystack, ISLAMIC_DETECTION_KEYWORDS))


def _rewrite_safe_query(original_query: str) -> str:
    base_terms = ", ".join(ISLAMIC_SAFE_QUERY_TERMS[:4])
    return base_terms if _contains_any(_normalize_text(original_query), ISLAMIC_PROPHETIC_BLOCKLIST) else f"{base_terms}, {_normalize_text(original_query)}"


def _is_blocked_visual_candidate(candidate: dict) -> str | None:
    text_blob = " ".join([
        _normalize_text(str(candidate.get("title", ""))),
        _normalize_text(str(candidate.get("description", ""))),
        _normalize_text(str(candidate.get("tags", ""))),
        _normalize_text(str(candidate.get("url", ""))),
        _normalize_text(str(candidate.get("attribution", ""))),
    ])
    for term in ISLAMIC_BLOCKED_KEYWORDS.union(ISLAMIC_PROPHETIC_BLOCKLIST):
        if term in text_blob:
            return term
    return None

def _resolve_local_visual_path(visual_url: str | None) -> str | None:
    if not visual_url:
        return None

    if visual_url.startswith("http://") or visual_url.startswith("https://"):
        return None

    if visual_url.startswith("/static/"):
        return visual_url[len("/static/"):].lstrip("/")

    return visual_url


def _needs_visual_refill(scene: Scene) -> bool:
    if scene.visual_status == "pending":
        return True

    if scene.visual_status not in {"suggested", "approved", "ok"}:
        return False

    local_path = _resolve_local_visual_path(scene.visual_url)

    if local_path is None:
        return not scene.visual_url

    return not os.path.exists(local_path)


def _safe_name(value: str) -> str:
    value = value or "asset"
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
    return value[:80]


def normalize_uuid(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        logger.error("invalid_uuid field=%s value=%r value_type=%s", field_name, value, type(value).__name__)
        raise ValueError(f"Invalid UUID for {field_name}: {value!r}") from exc


async def download_visual_asset(url: str, project_id: str, scene_order: int, source: str) -> str | None:
    """
    Download external visual URL into a local file so ffmpeg can use it.
    Returns local file path, or None if download fails.
    """
    if not url:
        return None

    if not url.startswith("http"):
        return url if os.path.exists(url) else None

    ensure_project_dirs(project_id)
    project_dir = get_project_assets_dir(project_id)
    os.makedirs(project_dir, exist_ok=True)

    clean_url = url.split("?")[0]
    ext = os.path.splitext(clean_url)[1].lower()

    if ext not in [".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".mp4"

    filename = f"scene_{int(scene_order):03d}_{_safe_name(source)}_{abs(hash(url)) % 100000}{ext}"
    local_path = os.path.join(project_dir, filename)

    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": "VidFlow/1.0"}) as response:
                response.raise_for_status()

                with open(local_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            f.write(chunk)

        if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
            logger.info("saved_visual_asset_path=%s", local_path)
            return local_path

        logger.error(f"Downloaded visual file is empty or too small: {local_path}")
        return None

    except Exception as e:
        logger.error(f"Failed to download visual asset for scene {scene_order}: {e}")
        return None
FALLBACK_ORDER = {
    "curiobuzz": ["pexels", "pixabay", "wikimedia", "ai", "text"],
    "finance": ["pexels", "pixabay", "charts", "text"],
    "islamic": ["pexels_mosque", "wikimedia", "ai_safe", "text"],
    "default": ["pexels", "pixabay", "wikimedia", "text"],
}


def _build_scene_visual_query(project: Project, scene: Scene) -> str:
    parts = [
        project.title or "",
        project.niche or "",
        project.language or "",
        scene.script_text or "",
        f"scene {scene.order}",
        scene.visual_query or "",
    ]
    query = " ".join(part.strip() for part in parts if part and part.strip())
    return re.sub(r"\s+", " ", query).strip()


def _scene_visual_owned_by_project(scene: Scene, project_id: str) -> bool:
    return bool(
        scene.visual_selected_for_project_id == project_id
        and scene.visual_selected_for_scene_id == scene.id
    )


async def refill_scene_visual(
    project: Project,
    scene: Scene,
    project_id: str,
    is_islamic_profile: bool,
    used_asset_urls: set[str] | None = None,
) -> bool:
    """Refill a scene visual using existing auto-fill search/safety logic."""
    used_asset_urls = used_asset_urls or set()
    generated_query = _build_scene_visual_query(project, scene)
    scene.visual_query = generated_query
    if not generated_query:
        scene.visual_status = "missing_query"
        return False

    downloaded_path = None
    selected_source = None
    selected_attribution = None
    selected_remote_url = None

    query_to_use = generated_query
    if is_islamic_profile:
        query_to_use = _rewrite_safe_query(scene.visual_query)
        logger.info("original_visual_query=%s", scene.visual_query)
        logger.info("rewritten_safe_query=%s", query_to_use)

    logger.info("trying pexels videos")
    video_candidates = await pexels.search_videos(query_to_use, per_page=3)

    for candidate in video_candidates:
        candidate_url = candidate.get("url")
        candidate_source = candidate.get("source", "unknown")
        if is_islamic_profile:
            blocked_reason = _is_blocked_visual_candidate(candidate)
            if blocked_reason:
                logger.info("blocked_visual_result reason=%s source=%s url=%s", blocked_reason, candidate_source, candidate_url)
                continue
        if candidate_url in used_asset_urls:
            logger.info("duplicate_visual_skipped=true project_id=%s scene_id=%s scene_order=%s duplicate_source_url=%s source=%s", project_id, scene.id, scene.order, candidate_url, candidate_source)
            continue
        local_path = await download_visual_asset(url=candidate_url, project_id=project_id, scene_order=scene.order, source=candidate_source)
        if local_path:
            downloaded_path = local_path
            selected_source = candidate_source
            selected_attribution = candidate.get("attribution")
            selected_remote_url = candidate_url
            logger.info("pexels video selected")
            break

    if not downloaded_path:
        logger.info("trying pixabay videos")
        video_candidates = await pixabay.search_videos(query_to_use, per_page=3)
        for candidate in video_candidates:
            candidate_url = candidate.get("url")
            candidate_source = candidate.get("source", "unknown")
            if is_islamic_profile:
                blocked_reason = _is_blocked_visual_candidate(candidate)
                if blocked_reason:
                    logger.info("blocked_visual_result reason=%s source=%s url=%s", blocked_reason, candidate_source, candidate_url)
                    continue
            if candidate_url in used_asset_urls:
                logger.info("duplicate_visual_skipped=true project_id=%s scene_id=%s scene_order=%s duplicate_source_url=%s source=%s", project_id, scene.id, scene.order, candidate_url, candidate_source)
                continue
            local_path = await download_visual_asset(url=candidate_url, project_id=project_id, scene_order=scene.order, source=candidate_source)
            if local_path:
                downloaded_path = local_path
                selected_source = candidate_source
                selected_attribution = candidate.get("attribution")
                selected_remote_url = candidate_url
                logger.info("pixabay video selected")
                break

    if not downloaded_path:
        logger.info("no valid video found, trying photos")
        photo_candidates = await pexels.search_photos(query_to_use, per_page=3)
        if not photo_candidates:
            photo_candidates = await pixabay.search_photos(query_to_use, per_page=3)
        for candidate in photo_candidates:
            candidate_url = candidate.get("url")
            candidate_source = candidate.get("source", "unknown")
            if is_islamic_profile:
                blocked_reason = _is_blocked_visual_candidate(candidate)
                if blocked_reason:
                    logger.info("blocked_visual_result reason=%s source=%s url=%s", blocked_reason, candidate_source, candidate_url)
                    continue
            if candidate_url in used_asset_urls:
                logger.info("duplicate_visual_skipped=true project_id=%s scene_id=%s scene_order=%s duplicate_source_url=%s source=%s", project_id, scene.id, scene.order, candidate_url, candidate_source)
                continue
            local_path = await download_visual_asset(url=candidate_url, project_id=project_id, scene_order=scene.order, source=candidate_source)
            if local_path:
                downloaded_path = local_path
                selected_source = candidate_source
                selected_attribution = candidate.get("attribution")
                selected_remote_url = candidate_url
                logger.info("photo fallback selected")
                break

    if not downloaded_path and is_islamic_profile:
        for fallback_query in ISLAMIC_FALLBACK_QUERIES:
            logger.info("fallback_safe_visual_query=%s", fallback_query)
            fallback_candidates = await pexels.search_photos(fallback_query, per_page=3)
            if not fallback_candidates:
                fallback_candidates = await pixabay.search_photos(fallback_query, per_page=3)
            for candidate in fallback_candidates:
                candidate_url = candidate.get("url")
                blocked_reason = _is_blocked_visual_candidate(candidate)
                if blocked_reason or candidate_url in used_asset_urls:
                    if blocked_reason:
                        logger.info("blocked_visual_result reason=%s source=%s url=%s", blocked_reason, candidate.get("source", "unknown"), candidate_url)
                    continue
                local_path = await download_visual_asset(url=candidate_url, project_id=project_id, scene_order=scene.order, source=candidate.get("source", "unknown"))
                if local_path:
                    downloaded_path = local_path
                    selected_source = candidate.get("source", "unknown")
                    selected_attribution = candidate.get("attribution")
                    selected_remote_url = candidate_url
                    break
            if downloaded_path:
                break

    if not downloaded_path:
        scene.visual_status = "needs_ai"
        return False

    selected_project_uuid = None
    selected_scene_uuid = None
    try:
        selected_project_uuid = normalize_uuid(project.id, "project.id")
    except ValueError:
        selected_project_uuid = None
    try:
        selected_scene_uuid = normalize_uuid(scene.id, "scene.id")
    except ValueError:
        selected_scene_uuid = None

    scene.visual_url = downloaded_path
    scene.visual_source_url = selected_remote_url
    scene.visual_source = selected_source if selected_source else "stock"
    scene.visual_status = "suggested"
    scene.visual_locked = False
    scene.visual_selected_for_project_id = selected_project_uuid
    scene.visual_selected_for_scene_id = selected_scene_uuid
    scene.visual_selected_at = datetime.utcnow()
    scene.visual_metadata = {"generated_visual_query": generated_query}
    scene.thumbnail_url = None
    if selected_attribution:
        scene.on_screen_source = selected_attribution
    if scene.visual_source_url:
        used_asset_urls.add(scene.visual_source_url)
    logger.info(
        "visual_assignment_debug project_id=%s scene_id=%s project_id_type=%s scene_id_type=%s visual_selected_for_project_id=%s visual_selected_for_project_id_type=%s visual_selected_for_scene_id=%s visual_selected_for_scene_id_type=%s visual_metadata_type=%s visual_source_url=%s",
        project.id,
        scene.id,
        type(project.id).__name__,
        type(scene.id).__name__,
        scene.visual_selected_for_project_id,
        type(scene.visual_selected_for_project_id).__name__,
        scene.visual_selected_for_scene_id,
        type(scene.visual_selected_for_scene_id).__name__,
        type(scene.visual_metadata).__name__,
        scene.visual_source_url,
    )
    logger.info("project_id=%s scene_id=%s scene_order=%s generated_visual_query=%s selected_visual_url=%s", project_id, scene.id, scene.order, generated_query, scene.visual_source_url or scene.visual_url)
    if is_islamic_profile:
        logger.info("selected_safe_visual_url=%s", scene.visual_url)
    return True


@router.get("/search")
async def search_visuals(
    query: str = Query(...),
    source: str = Query("all"),
    media_type: str = Query("video"),
    limit: int = Query(10),
):
    results = []
    if source in ("all", "pexels"):
        if media_type == "video":
            results += await pexels.search_videos(query, per_page=min(limit, 10))
        else:
            results += await pexels.search_photos(query, per_page=min(limit, 10))
    if source in ("all", "pixabay"):
        if media_type == "video":
            results += await pixabay.search_videos(query, per_page=min(limit, 10))
        else:
            results += await pixabay.search_photos(query, per_page=min(limit, 10))
    if source in ("all", "wikimedia") and media_type == "photo":
        results += await wikimedia.search_images(query, limit=min(limit, 10))
    return {"results": results[:limit], "total": len(results)}


@router.post("/assign")
async def assign_visual(
    scene_id: int,
    visual_url: str,
    visual_source: str,
    on_screen_source: str = None,
    db: AsyncSession = Depends(get_db),
):
    scene = await db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    scene.visual_url = visual_url
    scene.visual_source_url = visual_url if visual_url.startswith(("http://", "https://")) else scene.visual_source_url
    scene.visual_source = visual_source
    scene.visual_status = "approved"
    scene.visual_locked = True
    try:
        selected_project_uuid = normalize_uuid(scene.project_id, "scene.project_id")
    except ValueError:
        selected_project_uuid = None
    try:
        selected_scene_uuid = normalize_uuid(scene.id, "scene.id")
    except ValueError:
        selected_scene_uuid = None
    scene.visual_selected_for_project_id = selected_project_uuid
    scene.visual_selected_for_scene_id = selected_scene_uuid
    scene.visual_selected_at = datetime.utcnow()
    logger.info(
        "visual_assignment_debug project_id=%s scene_id=%s project_id_type=%s scene_id_type=%s visual_selected_for_project_id=%s visual_selected_for_project_id_type=%s visual_selected_for_scene_id=%s visual_selected_for_scene_id_type=%s visual_metadata_type=%s visual_source_url=%s",
        scene.project_id,
        scene.id,
        type(scene.project_id).__name__,
        type(scene.id).__name__,
        scene.visual_selected_for_project_id,
        type(scene.visual_selected_for_project_id).__name__,
        scene.visual_selected_for_scene_id,
        type(scene.visual_selected_for_scene_id).__name__,
        type(scene.visual_metadata).__name__,
        scene.visual_source_url,
    )
    if on_screen_source:
        scene.on_screen_source = on_screen_source
    await db.commit()
    return {"success": True}


@router.post("/auto-fill/{project_id}")
async def auto_fill_visuals(project_id: str, niche: str = "default", force_refresh: bool = True, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(select(Scene).where(Scene.project_id == project_id))
    all_scenes = result.scalars().all()
    for scene in all_scenes:
        if force_refresh and not scene.visual_locked:
            scene.visual_url = None
            scene.visual_source_url = None
            scene.visual_source = None
            scene.visual_status = "pending"
            scene.visual_metadata = {}
            scene.thumbnail_url = None
            scene.on_screen_source = None
            scene.visual_selected_for_project_id = None
            scene.visual_selected_for_scene_id = None
            scene.visual_selected_at = None
    scenes = [scene for scene in all_scenes if (not scene.visual_locked and _needs_visual_refill(scene))]
    is_islamic_profile = _detect_islamic_visual_profile(project, all_scenes)

    if is_islamic_profile:
        logger.info("visual_safety_profile=islamic project_id=%s", project_id)

    filled = 0
    failed = 0
    used_asset_urls: set[str] = set(filter(None, [s.visual_source_url for s in all_scenes if s.visual_locked]))

    for scene in scenes:
        ok = await refill_scene_visual(
            project=project,
            scene=scene,
            project_id=project_id,
            is_islamic_profile=is_islamic_profile,
            used_asset_urls=used_asset_urls,
        )
        if ok:
            filled += 1
        else:
            failed += 1

    await db.commit()

    return {
        "filled": filled,
        "failed": failed,
        "total": len(scenes),
    }
@router.get("/gap-analysis/{project_id}")
async def visual_gap_analysis(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Scene).where(Scene.project_id == project_id))
    scenes = result.scalars().all()
    analysis = []
    for scene in scenes:
        status = scene.visual_status
        gap_type = "ok" if scene.visual_url else "missing"
        if status == "needs_ai":
            gap_type = "needs_ai"
        elif not scene.visual_url:
            gap_type = "missing"
        analysis.append({
            "scene_id": scene.id,
            "order": scene.order,
            "visual_query": scene.visual_query,
            "status": status,
            "gap_type": gap_type,
            "visual_url": scene.visual_url,
            "visual_source": scene.visual_source,
        })
    return {"scenes": analysis}
