from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import os
from app.database import get_db
from app.models.project import Project
from app.models.channel import Channel
from app.services.thumbnail import generate_thumbnail

router = APIRouter(prefix="/thumbnails", tags=["thumbnails"])


class ThumbnailRequest(BaseModel):
    project_id: str
    use_sd: bool = False
    custom_prompt: Optional[str] = None


@router.post("/generate")
async def generate_project_thumbnail(req: ThumbnailRequest, db: AsyncSession = Depends(get_db)):
    """Generate a thumbnail for a project using Stable Diffusion or PIL fallback."""
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    channel = await db.get(Channel, project.channel_id)
    primary_color = channel.primary_color if channel else "#0ea5e9"
    logo_path = channel.logo_url if channel else None

    prompt = req.custom_prompt or project.thumbnail_prompt or f"cinematic {project.title}"

    thumb_path = await generate_thumbnail(
        prompt=prompt,
        title=project.title,
        project_id=project.id,
        primary_color=primary_color,
        logo_path=logo_path,
        use_sd=req.use_sd,
    )

    return {"thumbnail_path": thumb_path, "status": "generated"}


@router.get("/download/{project_id}")
async def download_thumbnail(project_id: str, db: AsyncSession = Depends(get_db)):
    """Download the generated thumbnail."""
    from app.config import settings
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    # Find any thumbnail file
    if os.path.exists(out_dir):
        for f in os.listdir(out_dir):
            if f.startswith("thumbnail_") and f.endswith(".jpg"):
                path = os.path.join(out_dir, f)
                return FileResponse(path, media_type="image/jpeg", filename="thumbnail.jpg")
    raise HTTPException(status_code=404, detail="Thumbnail not found — generate it first")


@router.post("/preview")
async def preview_thumbnail(
    prompt: str,
    title: str,
    primary_color: str = "#0ea5e9",
):
    """Quick preview thumbnail without saving to project."""
    import tempfile, uuid
    tmp_id = str(uuid.uuid4())
    path = await generate_thumbnail(
        prompt=prompt,
        title=title,
        project_id=f"preview_{tmp_id}",
        primary_color=primary_color,
        use_sd=False,
    )
    return FileResponse(path, media_type="image/jpeg", filename="thumbnail_preview.jpg")
