import os
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.project import Project
from app.services.video_processor import (
    compose_video,
    convert_aspect_ratio,
    generate_srt,
    render_diagnostic_video,
)
from app.services.audio_assembler import generate_scene_timings
from app.services.n8n_service import notify_video_ready
from app.config import settings


def _static_to_fs(url: Optional[str]) -> Optional[str]:
    """Convert a /static/... URL path to its real filesystem path."""
    if url and url.startswith("/static/"):
        return os.path.join(settings.UPLOAD_DIR, url[len("/static/"):])
    return url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video", tags=["video"])


class RenderRequest(BaseModel):
    project_id: str
    aspect_ratio: str = "16:9"
    burn_subtitles: bool = False


class MultiFormatRequest(BaseModel):
    project_id: str
    formats: list[str] = ["16:9"]


async def _do_render(project_id: str, aspect_ratio: str, burn_subtitles: bool):
    """Background task: full render pipeline."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Project)
                .options(selectinload(Project.scenes), selectinload(Project.channel))
                .where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if not project:
                return

            output_dir = os.path.join(settings.OUTPUT_DIR, project_id)
            os.makedirs(output_dir, exist_ok=True)
            fmt_name = aspect_ratio.replace(":", "x")
            output_path = os.path.join(output_dir, f"output_{fmt_name}.mp4")

            scenes = sorted(project.scenes, key=lambda s: s.order)
            channel = project.channel

            # Build SRT if subtitles requested
            srt_path = None
            if burn_subtitles and project.voice_id and project.audio_url:
                timings = await generate_scene_timings(
                    [{"id": s.id, "script_text": s.script_text, "duration": s.duration, "order": s.order} for s in scenes],
                    project.voice_id, project.audio_speed, project_id,
                )
                srt_path = await generate_srt(timings, output_path)

            scenes_data = [
                {
                    "id": s.id,
                    "order": s.order,
                    "visual_url": s.visual_url,
                    "visual_status": getattr(s, "visual_status", None),
                    "duration": s.duration,
                    "script_text": s.script_text,
                    "on_screen_source": s.on_screen_source,
                }
                for s in scenes
            ]
            logger.info("Sending %s scenes to compose_video for project %s", len(scenes_data), project_id)
            for scene in scenes_data:
                logger.info(
                    "render scene payload: id=%s order=%s visual_url=%s visual_status=%s",
                    scene.get("id"),
                    scene.get("order"),
                    scene.get("visual_url"),
                    scene.get("visual_status"),
                )

            subtitle_config = project.template_config if burn_subtitles and srt_path else None

            ok = await compose_video(
                scenes=scenes_data,
                audio_path=project.audio_url or "",
                output_path=output_path,
                aspect_ratio=aspect_ratio,
                intro_path=_static_to_fs(channel.intro_url if channel else None),
                outro_path=_static_to_fs(channel.outro_url if channel else None),
                bg_music_path=_static_to_fs(channel.bg_music_url if channel else None),
                subtitle_config=subtitle_config,
                logo_path=_static_to_fs(channel.logo_url if channel else None),
                logo_position=project.template_config.get("logo_position", "top-right"),
            )

            if ok:
                if aspect_ratio == "16:9":
                    project.output_url = output_path
                elif aspect_ratio == "9:16":
                    project.output_9_16_url = output_path
                elif aspect_ratio == "1:1":
                    project.output_1_1_url = output_path
                project.status = "rendered"
                logger.info(f"Render complete: {project.title} ({aspect_ratio})")
                await db.commit()

                # Notify n8n
                await notify_video_ready(
                    project_id=project.id,
                    title=project.title,
                    channel_name=channel.name if channel else "",
                    output_url=output_path,
                )
            else:
                if aspect_ratio == "16:9":
                    project.output_url = None
                elif aspect_ratio == "9:16":
                    project.output_9_16_url = None
                elif aspect_ratio == "1:1":
                    project.output_1_1_url = None
                project.status = "render_failed"
                await db.commit()
                logger.error(
                    "Render failed because no valid visual clips were available: %s (%s)",
                    project.title,
                    aspect_ratio,
                )

        except Exception as e:
            logger.error(f"Render task exception for {project_id}: {e}", exc_info=True)
            try:
                project = await db.get(Project, project_id)
                if project:
                    project.status = "render_failed"
                    await db.commit()
            except Exception:
                pass


@router.post("/render")
async def render_video(req: RenderRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.review1_approved or not project.review2_approved:
        raise HTTPException(status_code=400, detail="Reviews 1 and 2 must be approved before rendering")

    project.status = "rendering"
    await db.commit()
    background_tasks.add_task(_do_render, req.project_id, req.aspect_ratio, req.burn_subtitles)
    return {"status": "rendering_started", "project_id": req.project_id, "aspect_ratio": req.aspect_ratio}


@router.post("/render-all-formats")
async def render_all_formats(req: MultiFormatRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Render the video in multiple formats at once."""
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.review1_approved or not project.review2_approved:
        raise HTTPException(status_code=400, detail="Both reviews must be approved")

    project.status = "rendering"
    await db.commit()
    for fmt in req.formats:
        background_tasks.add_task(_do_render, req.project_id, fmt, False)
    return {"status": "rendering_started", "formats": req.formats}


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
        "review1_approved": project.review1_approved,
        "review2_approved": project.review2_approved,
        "review3_approved": project.review3_approved,
    }


@router.get("/download/{project_id}")
async def download_video(project_id: str, format: str = "16:9", db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    path_map = {
        "16:9": project.output_url,
        "9:16": project.output_9_16_url,
        "1:1":  project.output_1_1_url,
    }
    path = path_map.get(format, project.output_url)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Video file not found — please render first")
    safe_title = "".join(c for c in project.title if c.isalnum() or c in " -_")[:50]
    fmt_name = format.replace(":", "x")
    return FileResponse(path, media_type="video/mp4", filename=f"{safe_title}_{fmt_name}.mp4")


@router.get("/diagnostic-render")
async def diagnostic_render():
    diagnostics_dir = os.path.join(settings.OUTPUT_DIR, "diagnostics")
    os.makedirs(diagnostics_dir, exist_ok=True)
    output_path = os.path.join(diagnostics_dir, "diagnostic_16x9.mp4")

    result = await render_diagnostic_video(output_path, "16:9")
    payload = {
        "ok": bool(result.get("ok")),
        "path": result.get("output_path", output_path),
        "size": int(result.get("size", 0) or 0),
        "command": result.get("command_name", ""),
        "stderr_tail": (result.get("stderr") or "")[-2000:],
    }

    if not payload["ok"]:
        raise HTTPException(status_code=500, detail=payload)

    return payload


@router.get("/diagnostic-download")
async def diagnostic_download():
    output_path = os.path.join(settings.OUTPUT_DIR, "diagnostics", "diagnostic_16x9.mp4")
    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=404,
            detail="Diagnostic video not found — run diagnostic-render first",
        )
    return FileResponse(output_path, media_type="video/mp4", filename="diagnostic_16x9.mp4")
