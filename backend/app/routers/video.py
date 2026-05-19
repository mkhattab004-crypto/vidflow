import os
import logging
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional

SHORT_FORM_TYPES = {"short_form", "reels", "tiktok", "shorts"}
from app.database import get_db
from app.models.project import Project
from app.services.video_processor import (
    compose_video,
    configure_storage_cleanup_callback,
    consume_no_space_error_flag,
    convert_aspect_ratio,
    generate_srt,
    render_diagnostic_video,
    probe_media_duration,
)
from app.services.audio_assembler import generate_scene_timings, assemble_project_audio
from app.services.n8n_service import notify_video_ready
from app.config import settings
from app.services.storage import ensure_project_dirs, get_project_renders_dir, cleanup_project_storage
from app.routers.visuals import (
    _detect_islamic_visual_profile,
    refill_scene_visual,
    download_visual_asset,
)


def _static_to_fs(url: Optional[str]) -> Optional[str]:
    """Convert a /static/... URL path to its real filesystem path."""
    if url and url.startswith("/static/"):
        return os.path.join(settings.UPLOAD_DIR, url[len("/static/"):])
    return url


def _extract_project_id_from_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    m = re.search(r"/projects/([^/]+)/", path.replace("\\", "/"))
    return m.group(1) if m else None


def _validate_project_asset_path(current_project_id: str, asset_path: Optional[str]) -> bool:
    if not asset_path:
        return False
    normalized = asset_path.replace("\\", "/")
    detected = _extract_project_id_from_path(normalized)
    ok = f"/projects/{current_project_id}/" in normalized and (detected is None or detected == str(current_project_id))
    if not ok:
        logger.error("asset_project_mismatch current_project_id=%s asset_path=%s detected_asset_project_id=%s action=reject_and_regenerate", current_project_id, asset_path, detected)
    return ok

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video", tags=["video"])


class RenderRequest(BaseModel):
    project_id: str
    aspect_ratio: str = "16:9"
    burn_subtitles: bool = False


class MultiFormatRequest(BaseModel):
    project_id: str
    formats: list[str] | None = None


async def _do_render(project_id: str, aspect_ratio: str, burn_subtitles: bool, render_job_id: str):
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

            ensure_project_dirs(project_id)
            cleanup_project_storage(project_id)
            async def _cleanup_on_no_space():
                cleanup_project_storage(project_id)
            configure_storage_cleanup_callback(_cleanup_on_no_space)
            logger.info("current_project_id=%s render_job_id=%s using_existing_output_as_input=false", project_id, render_job_id)
            output_dir = get_project_renders_dir(project_id)
            os.makedirs(output_dir, exist_ok=True)
            fmt_name = aspect_ratio.replace(":", "x")
            output_name = {"16x9": "youtube_16x9.mp4", "9x16": "tiktok_9x16.mp4", "1x1": "instagram_1x1.mp4"}.get(fmt_name, f"output_{fmt_name}.mp4")
            output_path = os.path.join(output_dir, output_name)
            if not _validate_project_asset_path(project_id, output_path):
                raise RuntimeError("render_output_path invalid for project")

            scenes = sorted(project.scenes, key=lambda s: s.order)
            channel = project.channel
            is_islamic_profile = _detect_islamic_visual_profile(project, scenes)

            recovered_scene_count = 0
            unrecovered_scene_count = 0
            for scene in scenes:
                visual_valid = _validate_project_asset_path(project_id, scene.visual_url) if scene.visual_url else False
                logger.info("scene_id=%s scene_project_id=%s current_project_id=%s visual_asset_valid_for_project=%s", scene.id, scene.project_id, project_id, visual_valid)
                vurl = scene.visual_url or ""
                is_local_path = bool(vurl) and not vurl.startswith("http://") and not vurl.startswith("https://")
                missing_local = is_local_path and not os.path.exists(vurl)
                if visual_valid and not missing_local:
                    continue

                logger.warning(
                    "scene visual missing: scene_id=%s order=%s visual_url=%s",
                    scene.id,
                    scene.order,
                    scene.visual_url,
                )
                logger.info(
                    "recovering missing visual asset: scene_id=%s order=%s visual_url=%s",
                    scene.id,
                    scene.order,
                    scene.visual_url,
                )

                recovered = False
                ownership_valid = bool(scene.visual_selected_for_project_id == project_id and scene.visual_selected_for_scene_id == scene.id)
                source_url = None
                for candidate_source_url in (scene.visual_source_url, scene.on_screen_source):
                    if (candidate_source_url or "").startswith(("http://", "https://")):
                        source_url = candidate_source_url
                        break
                if source_url and ownership_valid:
                    redownloaded_path = await download_visual_asset(
                        url=source_url,
                        project_id=project_id,
                        scene_order=scene.order,
                        source="source",
                    )
                    if redownloaded_path:
                        scene.visual_url = redownloaded_path
                        recovered = True
                        logger.info(
                            "redownloaded visual asset: scene_id=%s order=%s visual_url=%s",
                            scene.id,
                            scene.order,
                            scene.visual_url,
                        )

                if source_url and not ownership_valid:
                    logger.error("asset_project_mismatch current_project_id=%s scene_id=%s scene_order=%s visual_selected_for_project_id=%s visual_selected_for_scene_id=%s", project_id, scene.id, scene.order, scene.visual_selected_for_project_id, scene.visual_selected_for_scene_id)
                    scene.visual_url = None
                    scene.visual_source_url = None
                    scene.visual_source = None
                    scene.visual_status = "pending"
                    scene.visual_metadata = {}
                if not recovered:
                    refilled = await refill_scene_visual(
                        project=project,
                        scene=scene,
                        project_id=project_id,
                        is_islamic_profile=is_islamic_profile,
                        used_asset_urls=set(s.visual_url for s in scenes if s.visual_url),
                    )
                    recovered = bool(refilled and scene.visual_url and os.path.exists(scene.visual_url))
                    if recovered:
                        logger.info(
                            "refilled missing scene visual: scene_id=%s order=%s visual_url=%s",
                            scene.id,
                            scene.order,
                            scene.visual_url,
                        )

                if recovered:
                    recovered_scene_count += 1
                else:
                    unrecovered_scene_count += 1

            logger.info(
                "missing visual recovery summary: project_id=%s recovered_scene_count=%s unrecovered_scene_count=%s",
                project_id,
                recovered_scene_count,
                unrecovered_scene_count,
            )
            await db.commit()

            visual_manifest = []
            for scene in scenes:
                path_valid = _validate_project_asset_path(project_id, scene.visual_url) if scene.visual_url else False
                if path_valid and scene.visual_selected_for_scene_id is None:
                    scene.visual_selected_for_project_id = project_id
                    scene.visual_selected_for_scene_id = scene.id
                    logger.info("repaired_visual_metadata=true current_project_id=%s scene_id=%s render_job_id=%s", project_id, scene.id, render_job_id)
                visual_valid_for_project = bool(
                    path_valid
                    and scene.visual_selected_for_project_id == project_id
                    and scene.visual_selected_for_scene_id == scene.id
                )
                visual_manifest.append({
                    "current_project_id": project_id,
                    "project_title": project.title,
                    "scene_id": scene.id,
                    "scene_order": scene.order,
                    "visual_url": scene.visual_url,
                    "visual_source_url": scene.visual_source_url,
                    "visual_selected_for_project_id": scene.visual_selected_for_project_id,
                    "visual_selected_for_scene_id": scene.visual_selected_for_scene_id,
                    "visual_valid_for_project": visual_valid_for_project,
                })
                logger.info("visual_manifest project_id=%s project_title=%s scene_id=%s scene_order=%s visual_url=%s visual_source_url=%s visual_selected_for_project_id=%s visual_selected_for_scene_id=%s visual_valid_for_project=%s", project_id, project.title, scene.id, scene.order, scene.visual_url, scene.visual_source_url, scene.visual_selected_for_project_id, scene.visual_selected_for_scene_id, visual_valid_for_project)

            invalid_manifest = [m for m in visual_manifest if not m["visual_valid_for_project"]]
            visual_project_id_valid = not invalid_manifest
            if invalid_manifest:
                raise RuntimeError(f"Render blocked: {len(invalid_manifest)} scene visuals invalid for current project")

            audio_valid = _validate_project_asset_path(project_id, project.audio_url) if project.audio_url else False
            logger.info("current_project_id=%s render_job_id=%s audio_project_id_valid=%s visual_project_id_valid=%s", project_id, render_job_id, audio_valid, visual_project_id_valid)
            if project.audio_url and not audio_valid:
                logger.info("narration_audio_valid_for_project=false regenerated_current_project_audio=true")
                project.audio_url = None
            if project.audio_url and not project.audio_url.startswith(("http://", "https://")) and not os.path.exists(project.audio_url):
                logger.warning("narration audio missing: project_id=%s audio_url=%s", project_id, project.audio_url)
                project.audio_url = None
            if not project.audio_url:
                scenes_audio_data = [{"id": s.id, "script_text": s.script_text or "", "duration": s.duration} for s in scenes]
                regenerated_audio = await assemble_project_audio(
                    scenes=scenes_audio_data,
                    voice_id=project.voice_id or "edge_en_default",
                    speed=project.audio_speed or 1.0,
                    project_id=project_id,
                    language=project.language or "en",
                )
                if regenerated_audio:
                    project.audio_url = regenerated_audio
                    await db.commit()
                    logger.info("narration_audio_valid_for_project=true regenerated_current_project_audio=true recovered_audio=true saved_audio_path=%s", regenerated_audio)
                else:
                    logger.warning("recovered_audio=false project_id=%s", project_id)

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
            if project.audio_url and os.path.exists(project.audio_url):
                timings = await generate_scene_timings(
                    [{"id": s.id, "script_text": s.script_text or "", "duration": s.duration, "order": s.order} for s in scenes],
                    project.voice_id or "",
                    project.audio_speed,
                    project_id,
                )
                timing_by_id = {t.get("id"): t for t in timings}
                for scene in scenes_data:
                    timing = timing_by_id.get(scene.get("id"))
                    if timing:
                        scene["audio_duration"] = float(timing.get("actual_duration", scene.get("duration", 5)) or 5)
                        scene["duration"] = scene["audio_duration"]
                    scene["project_video_type"] = project.video_type
            logger.info("rendering format=%s project_id=%s", aspect_ratio, project_id)
            logger.info("Sending %s scenes to compose_video for project %s", len(scenes_data), project_id)
            for scene in scenes_data:
                logger.info(
                    "render scene payload: id=%s order=%s visual_url=%s visual_status=%s",
                    scene.get("id"),
                    scene.get("order"),
                    scene.get("visual_url"),
                    scene.get("visual_status"),
                )

            total_scene_duration = float(sum(float(s.get("duration") or 0) for s in scenes_data))
            logger.info(
                "render metrics pre-compose: project_id=%s video_type=%s generated_scene_count=%s total_scene_duration=%.3f number_of_scenes_sent_to_render=%s",
                project_id,
                project.video_type,
                len(scenes),
                total_scene_duration,
                len(scenes_data),
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
            configure_storage_cleanup_callback(None)

            if ok:
                video_tmp_created_for_current_render = os.path.exists(output_path)
                logger.info("current_project_id=%s render_job_id=%s video_tmp_created_for_current_render=%s", project_id, render_job_id, video_tmp_created_for_current_render)
                if aspect_ratio == "16:9":
                    project.output_url = output_path
                    logger.info("output_url saved for format=%s field=output_url path=%s", aspect_ratio, output_path)
                elif aspect_ratio == "9:16":
                    project.output_9_16_url = output_path
                    logger.info("output_url saved for format=%s field=output_9_16_url path=%s", aspect_ratio, output_path)
                elif aspect_ratio == "1:1":
                    project.output_1_1_url = output_path
                    logger.info("output_url saved for format=%s field=output_1_1_url path=%s", aspect_ratio, output_path)
                project.status = "rendered"
                final_output_duration_seconds = probe_media_duration(output_path)
                logger.info(
                    "render metrics final: project_id=%s video_type=%s generated_scene_count=%s total_scene_duration=%.3f number_of_scenes_sent_to_render=%s final_output_duration_seconds=%.3f",
                    project_id,
                    project.video_type,
                    len(scenes),
                    total_scene_duration,
                    len(scenes_data),
                    final_output_duration_seconds,
                )
                logger.info("render format succeeded project_id=%s format=%s title=%s", project_id, aspect_ratio, project.title)
                logger.info("saved_render_path=%s", output_path)
                logger.info("render_output_saved=true project_id=%s format=%s", project_id, aspect_ratio)
                await db.commit()

                # Notify n8n
                await notify_video_ready(
                    project_id=project.id,
                    title=project.title,
                    channel_name=channel.name if channel else "",
                    output_url=output_path,
                )
            else:
                if consume_no_space_error_flag():
                    raise RuntimeError("Storage full. Please delete old projects/renders or increase Railway volume size.")
                if aspect_ratio == "16:9":
                    project.output_url = None
                elif aspect_ratio == "9:16":
                    project.output_9_16_url = None
                elif aspect_ratio == "1:1":
                    project.output_1_1_url = None
                project.status = "render_failed"
                await db.commit()
                logger.error(
                    "render format failed project_id=%s format=%s title=%s reason=final_composition_failed",
                    project_id,
                    aspect_ratio,
                    project.title,
                )

        except Exception as e:
            logger.error("render format failed project_id=%s format=%s exception=%s", project_id, aspect_ratio, e, exc_info=True)
            try:
                project = await db.get(Project, project_id)
                if project:
                    project.status = "render_failed"
                    await db.commit()
            except Exception:
                pass


@router.post("/render")
async def render_video(req: RenderRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.review1_approved or not project.review2_approved:
        raise HTTPException(status_code=400, detail="Reviews 1 and 2 must be approved before rendering")

    project.status = "rendering"
    render_job_id = str(uuid.uuid4())
    await db.commit()
    background_tasks.add_task(_do_render, req.project_id, req.aspect_ratio, req.burn_subtitles, render_job_id)
    return {"status": "rendering_started", "project_id": req.project_id, "aspect_ratio": req.aspect_ratio, "render_job_id": render_job_id}


@router.post("/render-all-formats")
async def render_all_formats(req: MultiFormatRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Render the video in multiple formats at once."""
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    project = await db.get(Project, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.review1_approved or not project.review2_approved:
        raise HTTPException(status_code=400, detail="Both reviews must be approved")

    allowed_formats = ["16:9", "9:16", "1:1"]
    default_formats = ["9:16"] if (project.video_type or "").lower() in SHORT_FORM_TYPES else ["16:9"]
    requested_formats = req.formats or default_formats
    valid_formats = [fmt for fmt in requested_formats if fmt in allowed_formats]
    invalid_formats = [fmt for fmt in requested_formats if fmt not in allowed_formats]

    if not valid_formats:
        raise HTTPException(status_code=400, detail=f"No valid formats requested. Allowed formats: {allowed_formats}")

    project.status = "rendering"
    render_job_id = str(uuid.uuid4())
    await db.commit()

    format_statuses = []
    for fmt in valid_formats:
        logger.info("queue render format=%s project_id=%s", fmt, req.project_id)
        background_tasks.add_task(_do_render, req.project_id, fmt, False, f"{render_job_id}:{fmt}")
        format_statuses.append({"format": fmt, "status": "queued"})

    return {
        "status": "rendering_started",
        "formats": valid_formats,
        "invalid_formats": invalid_formats,
        "format_statuses": format_statuses,
        "default_formats": default_formats,
        "message": "Formats are rendering independently; failures in one format will not stop others.",
    }


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
    if format not in path_map:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Supported values: 16:9, 9:16, 1:1",
        )
    path = path_map[format]
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
