from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project, Scene
from app.services import pexels, pixabay, wikimedia

router = APIRouter(prefix="/visuals", tags=["visuals"])


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
    for scene in scenes:
        if not scene.visual_query:
            continue
        videos = await pexels.search_videos(scene.visual_query, per_page=1)
        if not videos:
            videos = await pixabay.search_videos(scene.visual_query, per_page=1)
        if videos:
            scene.visual_url = videos[0]["url"]
            scene.visual_source = videos[0]["source"]
            scene.visual_status = "suggested"
            filled += 1
        else:
            scene.visual_status = "needs_ai"
    await db.commit()
    return {"filled": filled, "total": len(scenes)}


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
