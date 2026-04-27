from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.project import Project
from app.services.kokoro_tts import VOICES, generate_speech

router = APIRouter(prefix="/audio", tags=["audio"])


class TTSRequest(BaseModel):
    project_id: str
    text: str
    voice_id: str
    speed: float = 1.0


class PreviewRequest(BaseModel):
    text: str
    voice_id: str
    speed: float = 1.0


@router.get("/voices")
async def list_voices(language: str = None):
    if language:
        return [v for v in VOICES if v["language"] == language]
    return VOICES


@router.post("/generate")
async def generate_audio(req: TTSRequest, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    path = await generate_speech(req.text, req.voice_id, req.speed)
    project.audio_url = path
    project.voice_id = req.voice_id
    project.audio_speed = req.speed
    await db.commit()
    return {"audio_path": path, "status": "generated"}


@router.post("/preview")
async def preview_voice(req: PreviewRequest):
    path = await generate_speech(req.text[:200], req.voice_id, req.speed)
    return FileResponse(path, media_type="audio/wav", filename="preview.wav")


@router.get("/download/{project_id}")
async def download_audio(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project or not project.audio_url:
        raise HTTPException(status_code=404, detail="Audio not found")
    import os
    if not os.path.exists(project.audio_url):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    return FileResponse(project.audio_url, media_type="audio/wav", filename=f"{project_id}_audio.wav")
