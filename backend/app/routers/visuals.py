from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project, Scene
from app.services import pexels, pixabay, wikimedia
import os
import re
import httpx
import logging
router = APIRouter(prefix="/visuals", tags=["visuals"])

logger = logging.getLogger(__name__)

ASSET_ROOT = "/tmp/vidflow_assets"


def _safe_name(value: str) -> str:
    value = value or "asset"
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
    return value[:80]


async def download_visual_asset(url: str, project_id: str, scene_order: int, source: str) -> str | None:
    """
    Download external visual URL into a local file so ffmpeg can use it.
    Returns local file path, or None if download fails.
    """
    if not url:
        return None

    if not url.startswith("http"):
        return url if os.path.exists(url) else None

    project_dir = os.path.join(ASSET_ROOT, _safe_name(project_id))
    os.makedirs(project_dir, exist_ok=True)

    clean_url = url.split("?")[0]
    ext = os.path.splitext(clean_url)[1].lower()

    if ext not in [".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png"]:
        ext = ".mp4"

    filename = f"scene_{int(scene_order):03d}_{_safe_name(source)}{ext}"
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
    scene.visual_source = visual_source
    scene.visual_status = "approved"
    if on_screen_source:
        scene.on_screen_source = on_screen_source
    await db.commit()
    return {"success": True}


@router.post("/auto-fill/{project_id}")
async def auto_fill_visuals(project_id: str, niche: str = "default", db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Scene).where(Scene.project_id == project_id, Scene.visual_status == "pending")
    )
    scenes = result.scalars().all()

    filled = 0
    failed = 0

    for scene in scenes:
        if not scene.visual_query:
            scene.visual_status = "missing_query"
            failed += 1
            continue

        videos = await pexels.search_videos(scene.visual_query, per_page=3)

        if not videos:
            videos = await pixabay.search_videos(scene.visual_query, per_page=3)

        if not videos:
            scene.visual_status = "needs_ai"
            failed += 1
            continue

        selected = None
        local_path = None

        for candidate in videos:
            candidate_url = candidate.get("url")
            candidate_source = candidate.get("source", "unknown")

            local_path = await download_visual_asset(
                url=candidate_url,
                project_id=project_id,
                scene_order=scene.order,
                source=candidate_source,
            )

            if local_path:
                selected = candidate
                break

        if selected and local_path:
            scene.visual_url = local_path
            scene.visual_source = selected.get("source", "stock")
            scene.visual_status = "suggested"

            if selected.get("attribution"):
                scene.on_screen_source = selected.get("attribution")

            filled += 1
        else:
            scene.visual_status = "download_failed"
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
