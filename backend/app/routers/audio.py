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
from app.services.kokoro_tts import (
    VOICES,
    generate_speech,
    _select_edge_tts_voice,
    _select_gtts_voice,
    resolve_voice_for_project,
    get_edge_voice_catalog,
)
from app.services.audio_assembler import assemble_project_audio, generate_scene_timings
from app.services.storage import ensure_project_dirs, get_project_audio_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["audio"])


class TTSRequest(BaseModel):
    project_id: str
    voice_id: str
    speed: float = 1.0
    tts_provider: Optional[str] = None
    mode: str = "full"


@router.get("/voices")
async def list_voices():
    edge_voices, _ = await get_edge_voice_catalog()
    gtts = {
        "ar": [{"provider": "gtts", "language": "ar", "name": "gtts-ar", "display_name": "Arabic gTTS", "gender": "N/A", "locale": "ar"}],
        "en": [{"provider": "gtts", "language": "en", "name": "gtts-en", "display_name": "English gTTS", "gender": "N/A", "locale": "en"}],
        "tr": [{"provider": "gtts", "language": "tr", "name": "gtts-tr", "display_name": "Turkish gTTS", "gender": "N/A", "locale": "tr"}],
    }
    return {"providers": {"edge_tts": edge_voices, "gtts": gtts}}


@router.get("/preview")
async def preview_voice(text: str, voice_id: str, speed: float = 1.0, provider: str = "edge_tts", language: str = "en"):
    text = text[:250].strip() or "Hello, this is a voice preview."
    path = await generate_speech(text, voice_id, speed, language=language, provider_override=provider)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=500, detail="Audio generation failed")
    return FileResponse(path, media_type="audio/mpeg", filename="preview.mp3")


@router.post("/generate")
async def generate_audio(req: TTSRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.scenes), selectinload(Project.channel))
        .where(Project.id == req.project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes_data = [{"id": s.id, "script_text": s.script_text or "", "duration": s.duration} for s in sorted(project.scenes, key=lambda x: x.order)]
    channel = project.channel
    bg_music = getattr(channel, "bg_music_url", None) if channel else None
    language = (project.language or (project.channel.language if project.channel else "en") or "en")
    selected_provider = (req.tts_provider or settings.TTS_PROVIDER or "edge_tts").strip().lower()

    voice_info = None
    mismatch = False
    if selected_provider == "gtts":
        selected_voice_id = (req.voice_id or _select_gtts_voice(language)).strip() or _select_gtts_voice(language)
    else:
        try:
            selected_voice_id, _, voice_info, mismatch = await resolve_voice_for_project(language, req.voice_id, user_selected=bool(req.voice_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="INVALID_TTS_VOICE")

    logger.info(
        "project_id=%s project_language=%s selected_provider=%s selected_voice_requested=%s selected_voice_used=%s selected_voice_gender=%s selected_voice_locale=%s voice_language_mismatch=%s tts_engine_function_called=%s",
        req.project_id,
        language,
        selected_provider,
        req.voice_id,
        selected_voice_id,
        (voice_info or {}).get("gender", "unknown"),
        (voice_info or {}).get("locale", "unknown"),
        str(mismatch).lower(),
        "edge_tts.Communicate" if selected_provider == "edge_tts" else "gtts.gTTS",
    )

    project.voice_id = selected_voice_id
    project.audio_speed = req.speed
    project.status = "audio_generating"
    await db.commit()

    background_tasks.add_task(_do_assemble, req.project_id, scenes_data, selected_voice_id, req.speed, bg_music, language, selected_provider)
    return {"status": "audio_generating", "project_id": req.project_id, "scenes": len(scenes_data)}


async def _do_assemble(project_id: str, scenes_data: list, voice_id: str, speed: float, bg_music: Optional[str], language: str, provider: str):
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            audio_path = await assemble_project_audio(scenes=scenes_data, voice_id=voice_id, speed=speed, project_id=project_id, bg_music_path=bg_music, language=language, provider_override=provider)
            project = await db.get(Project, project_id)
            if project:
                ensure_project_dirs(project_id)
                expected_audio = os.path.join(get_project_audio_dir(project_id), "narration.mp3")
                project.audio_url = expected_audio if os.path.exists(expected_audio) else audio_path
                project.output_url = None
                project.output_9_16_url = None
                project.output_1_1_url = None
                logger.info("current_project_id=%s output_cleared_due_to_audio_or_script_change=true", project_id)
                logger.info(
                    "provider_that_generated_audio=%s voice_that_generated_audio=%s audio_output_path=%s audio_size_bytes=%s fallback_used=false",
                    provider,
                    voice_id,
                    project.audio_url,
                    os.path.getsize(project.audio_url) if project.audio_url and os.path.exists(project.audio_url) else 0,
                )
                project.status = "audio_ready"
                await db.commit()
        except Exception as e:
            logger.error(f"Audio assembly failed for {project_id}: {e}")
            project = await db.get(Project, project_id)
            if project:
                project.status = "audio_failed"
                await db.commit()
