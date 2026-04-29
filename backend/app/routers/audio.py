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
from app.models.channel import Channel
from app.services.kokoro_tts import VOICES, generate_speech
from app.services.audio_assembler import assemble_project_audio, generate_scene_timings

router = APIRouter(prefix="/audio", tags=["audio"])


class TTSRequest(BaseModel):
    project_id: str
    voice_id: str
    speed: float = 1.0
    mode: str = "full"  # "full" = assemble all scenes | "scene" = single scene


class PreviewRequest(BaseModel):
    text: str
    voice_id: str
    speed: float = 1.0


class SceneTTSRequest(BaseModel):
    project_id: str
    scene_id: int
    voice_id: str
    speed: float = 1.0


@router.get("/voices")
async def list_voices(language: str = None):
    """List all available TTS voices, optionally filtered by language."""
    if language:
        return [v for v in VOICES if v["language"] == language]
    return VOICES


@router.get("/voices/by-language")
async def voices_by_language():
    """Return voices grouped by language."""
    grouped: dict = {}
    for v in VOICES:
        lang = v["language"]
        grouped.setdefault(lang, []).append(v)
    return grouped


@router.get("/preview")
async def preview_voice(text: str, voice_id: str, speed: float = 1.0):
    """Generate a short audio preview for a voice (GET so browser <audio> can use it directly)."""
    text = text[:250].strip() or "Hello, this is a voice preview."
    path = await generate_speech(text, voice_id, speed)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=500, detail="Audio generation failed")
    return FileResponse(path, media_type="audio/mpeg", filename="preview.mp3")


@router.post("/generate")
async def generate_audio(req: TTSRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Generate full project narration by assembling per-scene TTS.
    Returns immediately; audio assembly runs in background.
    """
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.scenes), selectinload(Project.channel))
        .where(Project.id == req.project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes_data = [
        {"id": s.id, "script_text": s.script_text or "", "duration": s.duration}
        for s in sorted(project.scenes, key=lambda x: x.order)
    ]

    channel = project.channel
    bg_music = getattr(channel, "bg_music_url", None) if channel else None

    # Update project immediately so the UI shows "processing"
    project.voice_id = req.voice_id
    project.audio_speed = req.speed
    project.status = "audio_generating"
    await db.commit()

    background_tasks.add_task(
        _do_assemble,
        project_id=req.project_id,
        scenes_data=scenes_data,
        voice_id=req.voice_id,
        speed=req.speed,
        bg_music=bg_music,
    )

    return {"status": "audio_generating", "project_id": req.project_id, "scenes": len(scenes_data)}


async def _do_assemble(project_id: str, scenes_data: list, voice_id: str, speed: float, bg_music: Optional[str]):
    """Background task: assemble audio and update project."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            audio_path = await assemble_project_audio(
                scenes=scenes_data,
                voice_id=voice_id,
                speed=speed,
                project_id=project_id,
                bg_music_path=bg_music,
            )
            project = await db.get(Project, project_id)
            if project:
                project.audio_url = audio_path
                project.status = "audio_ready"
                await db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Audio assembly failed for {project_id}: {e}")
            project = await db.get(Project, project_id)
            if project:
                project.status = "audio_failed"
                await db.commit()


@router.post("/generate-scene")
async def generate_scene_audio(req: SceneTTSRequest, db: AsyncSession = Depends(get_db)):
    """Generate TTS for a single scene."""
    scene = await db.get(Scene, req.scene_id)
    if not scene or scene.project_id != req.project_id:
        raise HTTPException(status_code=404, detail="Scene not found")
    if not scene.script_text:
        raise HTTPException(status_code=400, detail="Scene has no script text")

    path = await generate_speech(scene.script_text, req.voice_id, req.speed)
    scene.audio_url = path
    await db.commit()
    return {"scene_id": req.scene_id, "audio_path": path, "status": "ready"}


@router.get("/timings/{project_id}")
async def get_scene_timings(project_id: str, voice_id: str, speed: float = 1.0, db: AsyncSession = Depends(get_db)):
    """Return actual per-scene audio durations for accurate SRT generation."""
    result = await db.execute(
        select(Project).options(selectinload(Project.scenes)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes_data = [
        {"id": s.id, "script_text": s.script_text or "", "duration": s.duration, "order": s.order}
        for s in sorted(project.scenes, key=lambda x: x.order)
    ]
    timings = await generate_scene_timings(scenes_data, voice_id, speed, project_id)
    return {"timings": timings, "total_duration": sum(t["actual_duration"] for t in timings)}


@router.get("/status/{project_id}")
async def audio_status(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        "status": project.status,
        "audio_url": project.audio_url,
        "voice_id": project.voice_id,
        "speed": project.audio_speed,
    }


@router.get("/download/{project_id}")
async def download_audio(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project or not project.audio_url:
        raise HTTPException(status_code=404, detail="Audio not found")
    if not os.path.exists(project.audio_url):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    return FileResponse(project.audio_url, media_type="audio/mpeg", filename=f"{project_id}_narration.mp3")
