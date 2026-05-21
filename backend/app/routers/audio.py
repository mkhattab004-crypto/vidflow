from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
import os
import logging
from app.config import settings
from app.database import get_db
from app.models.project import Project, Scene
from app.services.kokoro_tts import VOICES, generate_speech, _select_edge_tts_voice, _select_gtts_voice, resolve_voice_for_project
from app.services.audio_assembler import assemble_project_audio, generate_scene_timings
from app.services.storage import ensure_project_dirs, get_project_audio_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["audio"])


class TTSRequest(BaseModel):
    project_id: str
    voice_id: str
    speed: float = 1.0
    tts_provider: Optional[str] = None
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




@router.get("/provider")
async def tts_provider(language: str = "en"):
    from app.config import settings
    provider = (settings.TTS_PROVIDER or "edge_tts").strip().lower()
    selected_voice = _select_gtts_voice(language) if provider == "gtts" else _select_edge_tts_voice(language)
    is_known = provider in {"edge_tts", "gtts", "free_api"}
    return {
        "tts_provider": provider,
        "project_language": language,
        "selected_tts_voice": selected_voice,
        "voice_gender": "male" if any(v in selected_voice.lower() for v in ["shakir", "guy", "ahmet"]) else "unknown",
        "fallback_used": False,
        "provider_warning": None if is_known else "Unknown or fallback provider configured. Check TTS_PROVIDER.",
    }
@router.get("/preview")
async def preview_voice(text: str, voice_id: str, speed: float = 1.0):
    """Generate a short audio preview for a voice (GET so browser <audio> can use it directly)."""
    text = text[:250].strip() or "Hello, this is a voice preview."
    path = await generate_speech(text, voice_id, speed, language="en")
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
    language = (project.language or (project.channel.language if project.channel else "en") or "en")
    selected_provider = (req.tts_provider or settings.TTS_PROVIDER or "edge_tts").strip().lower()
    if selected_provider == "gtts":
        selected_voice_id = (req.voice_id or _select_gtts_voice(language)).strip() or _select_gtts_voice(language)
        resolution = "gtts_selected"
    else:
        selected_voice_id, resolution = resolve_voice_for_project(language, req.voice_id, user_selected=bool(req.voice_id))
    logger.info(
        "project_id=%s project_language=%s selected_tts_provider=%s selected_voice=%s voice_gender=%s tts_engine_function_called=%s fallback_used=false voice_resolution=%s",
        req.project_id,
        language,
        (selected_provider if selected_provider in {"edge_tts", "gtts", "free_api"} else "edge_tts"),
        selected_voice_id,
        "male" if any(m in selected_voice_id.lower() for m in ["shakir", "guy", "ahmet"]) else "unknown",
        "generate_speech",
        resolution,
    )

    # Update project immediately so the UI shows "processing"
    project.voice_id = selected_voice_id
    project.audio_speed = req.speed
    project.status = "audio_generating"
    await db.commit()

    background_tasks.add_task(
        _do_assemble,
        project_id=req.project_id,
        scenes_data=scenes_data,
        voice_id=selected_voice_id,
        speed=req.speed,
        bg_music=bg_music,
        language=language,
        provider=selected_provider,
    )

    return {"status": "audio_generating", "project_id": req.project_id, "scenes": len(scenes_data)}


async def _do_assemble(project_id: str, scenes_data: list, voice_id: str, speed: float, bg_music: Optional[str], language: str, provider: str):
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
                language=language,
                provider_override=provider,
            )
            project = await db.get(Project, project_id)
            if project:
                ensure_project_dirs(project_id)
                expected_audio = os.path.join(get_project_audio_dir(project_id), "narration.mp3")
                if audio_path and audio_path != expected_audio:
                    logger.info("narration_audio_valid_for_project=false current_project_id=%s audio_output_path=%s expected_audio_output_path=%s", project_id, audio_path, expected_audio)
                project.audio_url = expected_audio if os.path.exists(expected_audio) else audio_path
                project.output_url = None
                project.output_9_16_url = None
                project.output_1_1_url = None
                logger.info("current_project_id=%s output_cleared_due_to_audio_or_script_change=true", project_id)
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

    project = await db.get(Project, req.project_id)
    language = (project.language if project else "en")
    path = await generate_speech(scene.script_text, req.voice_id, req.speed, language=language)
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
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
