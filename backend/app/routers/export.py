from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json
import os
from app.database import get_db
from app.models.project import Project

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{project_id}/metadata")
async def export_metadata(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    metadata = {
        "title": project.title,
        "description": project.description,
        "tags": project.metadata_tags,
        "pinned_comment": project.pinned_comment,
        "sharia_reference": project.sharia_reference,
    }
    content = json.dumps(metadata, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{project_id}_metadata.json"'},
    )


@router.get("/{project_id}/script")
async def export_script(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).options(selectinload(Project.scenes)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    lines = [f"# {project.title}\n"]
    for scene in sorted(project.scenes, key=lambda s: s.order):
        lines.append(f"## Scene {scene.order}")
        if scene.script_text:
            lines.append(f"{scene.script_text}")
        if scene.script_ar:
            lines.append(f"\n[AR] {scene.script_ar}")
        lines.append("")
    content = "\n".join(lines)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}_script.txt"'},
    )


@router.get("/{project_id}/subtitles")
async def export_subtitles(project_id: str, format: str = "srt", db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).options(selectinload(Project.scenes)).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    scenes = sorted(project.scenes, key=lambda s: s.order)
    lines = []
    current_time = 0.0
    for i, scene in enumerate(scenes, 1):
        duration = scene.duration or 5
        start = _seconds_to_srt_time(current_time)
        end = _seconds_to_srt_time(current_time + duration)
        current_time += duration
        if format == "srt":
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(scene.script_text or "")
            lines.append("")
        else:
            lines.append(f"{start} {scene.script_text or ''}")
    content = "\n".join(lines)
    ext = "srt" if format == "srt" else "txt"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}_subtitles.{ext}"'},
    )


def _seconds_to_srt_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
