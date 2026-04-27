from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
import os
from app.database import get_db
from app.models.project import Project, Scene
from app.services.video_processor import compose_video, convert_aspect_ratio
from app.config import settings

router = APIRouter(prefix="/video", tags=["video"])


class RenderRequest(BaseModel):
    project_id: str
    aspect_ratio: str = "16:9"


async def _do_render(project_id: str, aspect_ratio: str, db: AsyncSession):
    result = await db.execute(
        select(Project).options(selectinload(Project.scenes)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        return
    output_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"output_{aspect_ratio.replace(':', 'x')}.mp4")
    scenes_data = [
        {"visual_url": sc.visual_url, "duration": sc.duration, "script_text": sc.script_text}
        for sc in project.scenes
    ]
    channel = project.channel
    success = await compose_video(
        scenes=scenes_data,
        audio_path=project.audio_url or "",
        output_path=output_path,
        aspect_ratio=aspect_ratio,
        intro_path=getattr(channel, "intro_url", None) if channel else None,
        outro_path=getattr(channel, "outro_url", None) if channel else None,
        bg_music_path=getattr(channel, "bg_music_url", None) if channel else None,
    )
    if success:
        if aspect_ratio == "16:9":
            project.output_url = output_path
        elif aspect_ratio == "9:16":
            project.output_9_16_url = output_path
        elif aspect_ratio == "1:1":
            project.output_1_1_url = output_path
        project.status = "rendered"
        await db.commit()


@router.post("/render")
async def render_video(req: RenderRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.review1_approved or not project.review2_approved:
        raise HTTPException(status_code=400, detail="Reviews 1 and 2 must be approved before rendering")
    project.status = "rendering"
    await db.commit()
    background_tasks.add_task(_do_render, req.project_id, req.aspect_ratio, db)
    return {"status": "rendering_started", "project_id": req.project_id}


@router.get("/status/{project_id}")
async def render_status(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "status": project.status,
        "output_url": project.output_url,
        "output_9_16_url": project.output_9_16_url,
        "output_1_1_url": project.output_1_1_url,
    }


@router.get("/download/{project_id}")
async def download_video(project_id: str, format: str = "16:9", db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    path_map = {
        "16:9": project.output_url,
        "9:16": project.output_9_16_url,
        "1:1": project.output_1_1_url,
    }
    path = path_map.get(format, project.output_url)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(path, media_type="video/mp4", filename=f"{project.title}_{format.replace(':', 'x')}.mp4")
