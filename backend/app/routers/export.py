from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json, os
from app.database import get_db
from app.models.project import Project
from app.services.audio_assembler import generate_scene_timings
from app.config import settings

router = APIRouter(prefix="/export", tags=["export"])


async def _get_project_with_scenes(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.scenes))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/metadata")
async def export_metadata(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await _get_project_with_scenes(project_id, db)
    payload = {
        "title": project.title,
        "description": project.description or "",
        "tags": project.metadata_tags or [],
        "pinned_comment": project.pinned_comment or "",
        "thumbnail_prompt": project.thumbnail_prompt or "",
        "sharia_reference": project.sharia_reference,
        "trust_level": project.trust_level,
        "video_type": project.video_type,
        "aspect_ratio": project.aspect_ratio,
        "youtube_chapters": (project.script or {}).get("youtube_chapters", []),
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{project_id}_metadata.json"'},
    )


@router.get("/{project_id}/script")
async def export_script(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await _get_project_with_scenes(project_id, db)
    scenes = sorted(project.scenes, key=lambda s: s.order)
    lines = [
        f"# {project.title}",
        f"Channel Video | Type: {project.video_type}",
        "",
        f"## Description",
        project.description or "(no description)",
        "",
    ]
    if project.sharia_reference:
        lines += [f"## Sharia Reference", project.sharia_reference, f"Trust: {project.trust_level or 'unspecified'}", ""]

    lines.append("## Script")
    for scene in scenes:
        lines.append(f"\n### Scene {scene.order} [{scene.duration}s | {scene.transition}]")
        if scene.script_text:
            lines.append(scene.script_text)
        if scene.script_ar:
            lines.append(f"\n[AR] {scene.script_ar}")
        if scene.on_screen_source:
            lines.append(f"[Source on screen: {scene.on_screen_source}]")
        if scene.visual_query:
            lines.append(f"[Visual: {scene.visual_query}]")

    lines += ["", "## Pinned Comment", project.pinned_comment or "(none)"]
    content = "\n".join(lines)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}_script.txt"'},
    )


@router.get("/{project_id}/subtitles")
async def export_subtitles(
    project_id: str,
    format: str = Query("srt", pattern="^(srt|vtt|txt)$"),
    use_audio_timing: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """
    Export subtitles. If use_audio_timing=True and audio exists,
    generates timing from actual TTS audio durations (accurate).
    Otherwise uses scene.duration estimates.
    """
    project = await _get_project_with_scenes(project_id, db)
    scenes = sorted(project.scenes, key=lambda s: s.order)

    # Build timed scene list
    if use_audio_timing and project.voice_id and project.audio_url:
        scenes_data = [
            {"id": s.id, "script_text": s.script_text or "", "duration": s.duration, "order": s.order}
            for s in scenes
        ]
        timed = await generate_scene_timings(scenes_data, project.voice_id, project.audio_speed, project_id)
    else:
        timed = []
        t = 0.0
        for s in scenes:
            timed.append({"script_text": s.script_text or "", "start_time": t, "actual_duration": s.duration, "order": s.order})
            t += s.duration

    if format == "srt":
        content = _build_srt(timed)
        ext, mime = "srt", "text/plain"
    elif format == "vtt":
        content = _build_vtt(timed)
        ext, mime = "vtt", "text/vtt"
    else:
        content = _build_txt(timed)
        ext, mime = "txt", "text/plain"

    return Response(
        content=content,
        media_type=f"{mime}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}_subtitles.{ext}"'},
    )


@router.get("/{project_id}/full-bundle")
async def export_full_bundle(project_id: str, db: AsyncSession = Depends(get_db)):
    """Return everything as a single JSON for archiving / re-import."""
    project = await _get_project_with_scenes(project_id, db)
    return {
        "format": "vidflow_bundle_v1",
        "project_id": project_id,
        "title": project.title,
        "idea": project.idea,
        "video_type": project.video_type,
        "status": project.status,
        "channel_id": project.channel_id,
        "script": {"description": project.description, "pinned_comment": project.pinned_comment,
                   "thumbnail_prompt": project.thumbnail_prompt, "tags": project.metadata_tags,
                   "sharia_reference": project.sharia_reference, "trust_level": project.trust_level},
        "scenes": [
            {"order": s.order, "script_text": s.script_text, "script_ar": s.script_ar,
             "duration": s.duration, "visual_query": s.visual_query, "visual_type": s.visual_type,
             "visual_url": s.visual_url, "visual_source": s.visual_source,
             "on_screen_source": s.on_screen_source, "transition": s.transition, "effects": s.effects}
            for s in sorted(project.scenes, key=lambda x: x.order)
        ],
        "template": {"aspect_ratio": project.aspect_ratio, **project.template_config},
        "audio": {"voice_id": project.voice_id, "speed": project.audio_speed, "url": project.audio_url},
        "reviews": {"r1": project.review1_approved, "r2": project.review2_approved, "r3": project.review3_approved,
                    "notes": project.review_notes},
        "outputs": {"16:9": project.output_url, "9:16": project.output_9_16_url, "1:1": project.output_1_1_url},
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


# ── Subtitle format builders ────────────────────────────────────────────────

def _srt_time(s: float) -> str:
    h, m = int(s // 3600), int((s % 3600) // 60)
    sec, ms = int(s % 60), int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _vtt_time(s: float) -> str:
    return _srt_time(s).replace(",", ".")


def _build_srt(scenes: list[dict]) -> str:
    lines, i = [], 1
    for sc in scenes:
        if not sc.get("script_text", "").strip():
            continue
        start, end = sc["start_time"], sc["start_time"] + sc["actual_duration"]
        lines += [str(i), f"{_srt_time(start)} --> {_srt_time(end)}", sc["script_text"].strip(), ""]
        i += 1
    return "\n".join(lines)


def _build_vtt(scenes: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for i, sc in enumerate(scenes, 1):
        if not sc.get("script_text", "").strip():
            continue
        start, end = sc["start_time"], sc["start_time"] + sc["actual_duration"]
        lines += [f"{_vtt_time(start)} --> {_vtt_time(end)}", sc["script_text"].strip(), ""]
    return "\n".join(lines)


def _build_txt(scenes: list[dict]) -> str:
    return "\n\n".join(
        f"[{_srt_time(sc['start_time'])}] {sc.get('script_text', '').strip()}"
        for sc in scenes if sc.get("script_text", "").strip()
    )
