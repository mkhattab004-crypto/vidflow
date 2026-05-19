"""
Video processing service using FFmpeg.
Handles: scene stitching, subtitle burn-in, logo overlay, audio mix,
intro/outro injection, and multi-format export (16:9 / 9:16 / 1:1).
"""
import os
import asyncio
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}

MIN_NORMALIZED_DURATION_SECONDS = 2.0
MIN_VALID_CLIP_PROBE_SECONDS = 0.25
MIN_NORMALIZED_CLIP_SIZE_BYTES = 5_000
MIN_FINAL_OUTPUT_SIZE_BYTES = 20_000
_storage_cleanup_callback = None
_last_no_space_error = False


def configure_storage_cleanup_callback(callback):
    global _storage_cleanup_callback
    _storage_cleanup_callback = callback


def consume_no_space_error_flag() -> bool:
    global _last_no_space_error
    had_error = _last_no_space_error
    _last_no_space_error = False
    return had_error


def _run(cmd: list[str], timeout: int = 600) -> tuple[bool, str]:
    """Run an FFmpeg command synchronously (use _run_async from async contexts)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            logger.warning(f"FFmpeg stderr: {r.stderr[-500:]}")
        return r.returncode == 0, r.stderr
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timeout"
    except FileNotFoundError:
        return False, "FFmpeg not installed"


async def _run_async(cmd: list[str], timeout: int = 600) -> tuple[bool, str]:
    """Run FFmpeg in a thread pool so it doesn't block the async event loop."""
    global _last_no_space_error
    ok, err = await asyncio.to_thread(_run, cmd, timeout)
    if ok:
        return ok, err
    stderr = err or ""
    if "No space left on device" in stderr and _storage_cleanup_callback is not None:
        logger.warning("ffmpeg_no_space_detected retrying_once=true cmd=%s", " ".join(cmd[:8]))
        try:
            await _storage_cleanup_callback()
        except Exception as cleanup_err:
            logger.error("storage_cleanup_callback_failed: %s", cleanup_err)
        retry_ok, retry_err = await asyncio.to_thread(_run, cmd, timeout)
        if not retry_ok and "No space left on device" in (retry_err or ""):
            _last_no_space_error = True
        return retry_ok, retry_err
    return ok, err


async def run_ffmpeg_diagnostic(cmd: list[str]) -> tuple[bool, str]:
    """Run an FFmpeg diagnostic command and return success plus stderr output."""
    ok, stderr = await _run_async(cmd, timeout=120)
    return ok, stderr or ""


async def render_diagnostic_video(output_path: str, aspect_ratio: str = "16:9") -> dict:
    """Render a self-contained diagnostic MP4 using simple lavfi fallbacks."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    w, h = DIMENSIONS.get(aspect_ratio, DIMENSIONS["16:9"])

    commands: list[tuple[str, list[str]]] = [
        (
            "A_color_libx264",
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30:d=5",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path,
            ],
        ),
        (
            "B_testsrc_libx264",
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=30:duration=5",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path,
            ],
        ),
        (
            "C_color_mpeg4",
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30:d=5",
                "-an", "-c:v", "mpeg4", "-q:v", "5", output_path,
            ],
        ),
    ]

    last_stderr = ""
    last_command_name = ""

    for command_name, cmd in commands:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass

        ok, stderr = await run_ffmpeg_diagnostic(cmd)
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        last_stderr = stderr
        last_command_name = command_name

        logger.info(
            "Diagnostic command %s finished: return_ok=%s exists=%s size=%s stderr_tail=%s",
            command_name,
            ok,
            exists,
            size,
            (stderr or "")[-1000:],
        )

        if ok and exists and size > 10_000:
            return {
                "ok": True,
                "output_path": output_path,
                "size": size,
                "stderr": stderr,
                "command_name": command_name,
            }

    exists = os.path.exists(output_path)
    size = os.path.getsize(output_path) if exists else 0
    logger.error(
        "Diagnostic render failed after all commands. last_command=%s exists=%s size=%s stderr_tail=%s",
        last_command_name,
        exists,
        size,
        (last_stderr or "")[-1000:],
    )
    return {
        "ok": False,
        "output_path": output_path,
        "size": size,
        "stderr": last_stderr,
        "command_name": last_command_name,
    }


def _probe_duration(path: str) -> float:
    """Read media duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode != 0:
            return 0.0
        return max(float((r.stdout or "0").strip() or 0), 0.0)
    except Exception:
        return 0.0


def probe_media_duration(path: str) -> float:
    """Public wrapper for probing media duration."""
    return _probe_duration(path)


def _valid_final_output(path: str) -> bool:
    """Validate final render output by existence, size threshold, and duration."""
    if not os.path.exists(path):
        logger.error("output missing: candidate_path=%s", path)
        return False

    size = os.path.getsize(path)
    if size < MIN_FINAL_OUTPUT_SIZE_BYTES:
        logger.error("output too small: candidate_path=%s size_bytes=%s", path, size)
        return False

    duration = _probe_duration(path)
    if duration <= 0.5:
        logger.error(
            "output duration invalid: candidate_path=%s size_bytes=%s duration_seconds=%.3f",
            path,
            size,
            duration,
        )
        return False

    return True


def _scale_filter(w: int, h: int, aspect_ratio: str) -> tuple[str, str, bool]:
    """Return FFmpeg scaling filter and metadata for target output format."""
    crop_fill = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    if aspect_ratio in {"9:16", "1:1"}:
        return crop_fill, "crop_fill", False
    return crop_fill, "crop_fill", False


async def compose_video(
    scenes: list[dict],
    audio_path: str,
    output_path: str,
    aspect_ratio: str = "16:9",
    intro_path: Optional[str] = None,
    outro_path: Optional[str] = None,
    bg_music_path: Optional[str] = None,
    subtitle_config: Optional[dict] = None,
    logo_path: Optional[str] = None,
    logo_position: str = "top-right",
) -> bool:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    w, h = DIMENSIONS.get(aspect_ratio, (1920, 1080))
    allow_placeholder_render = bool(subtitle_config and subtitle_config.get("diagnostic_render"))

    scale_filter, scale_mode, black_bars_allowed = _scale_filter(w, h, aspect_ratio)
    logger.info(
        "compose_video received %s scenes project_video_type=%s output_format=%s target_format_size=%sx%s scale_mode=%s black_bars_allowed=%s",
        len(scenes),
        scenes[0].get("project_video_type") if scenes else None,
        aspect_ratio,
        w,
        h,
        scale_mode,
        black_bars_allowed,
    )
    for idx, scene in enumerate(scenes, start=1):
        logger.info(
            "compose_video scene[%s]: order=%s visual_url=%s visual_status=%s duration=%s",
            idx,
            scene.get("order"),
            scene.get("visual_url"),
            scene.get("visual_status"),
            scene.get("duration"),
        )

    # 1. Build ordered list of video clips with their target durations
    clips = []
    clip_durations = []

    if intro_path and os.path.exists(intro_path):
        clips.append(intro_path)
        clip_durations.append(5)

    for scene in scenes:
        vurl = scene.get("visual_url", "")
        scene_duration = float(scene.get("audio_duration", scene.get("duration", 10)) or 10)
        scene_id = scene.get("id")
        scene_order = scene.get("order")

        if not vurl:
            logger.warning(
                "scene visual missing: scene_id=%s order=%s visual_url=%s exists=%s",
                scene_id,
                scene_order,
                vurl,
                False,
            )
            continue

        visual_exists = os.path.exists(vurl)
        visual_size = os.path.getsize(vurl) if visual_exists else 0
        if not visual_exists:
            logger.warning(
                "scene visual missing: scene_id=%s order=%s visual_url=%s exists=%s",
                scene_id,
                scene_order,
                vurl,
                visual_exists,
            )
            continue

        scene_clips = []
        logger.info(
            "scene visual found: scene_id=%s order=%s path=%s exists=%s size_bytes=%s",
            scene_id,
            scene_order,
            vurl,
            visual_exists,
            visual_size,
        )

        folder = os.path.dirname(vurl)
        filename = os.path.basename(vurl)

        # Expected filename pattern:
        # scene_001_pexels_12345.mp4
        parts = filename.split("_")
        if len(parts) >= 2:
            scene_prefix = f"{parts[0]}_{parts[1]}_"

            try:
                scene_clips = [
                    os.path.join(folder, f)
                    for f in sorted(os.listdir(folder))
                    if f.startswith(scene_prefix)
                    and f.lower().endswith((".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"))
                    and os.path.exists(os.path.join(folder, f))
                ]
            except Exception as e:
                logger.warning(f"Could not list scene visual files for {vurl}: {e}")

        if not scene_clips:
            scene_clips = [vurl]

        clip_count = max(len(scene_clips), 1)
        per_clip_duration = scene_duration / clip_count
        for idx, clip in enumerate(scene_clips):
            clip_exists = os.path.exists(clip)
            clip_size = os.path.getsize(clip) if clip_exists else 0
            if clip_exists:
                logger.info(
                    "scene visual found: scene_id=%s order=%s path=%s exists=%s size_bytes=%s",
                    scene_id,
                    scene_order,
                    clip,
                    clip_exists,
                    clip_size,
                )
            else:
                logger.warning(
                    "scene visual missing: scene_id=%s order=%s visual_url=%s exists=%s",
                    scene_id,
                    scene_order,
                    clip,
                    clip_exists,
                )
            # Keep exact scene timing by distributing rounding remainder to final clip.
            if idx == clip_count - 1:
                duration = max(
                    scene_duration - (per_clip_duration * (clip_count - 1)),
                    MIN_NORMALIZED_DURATION_SECONDS,
                )
            else:
                duration = max(per_clip_duration, MIN_NORMALIZED_DURATION_SECONDS)
            clips.append(clip)
            clip_durations.append(duration)
            logger.info(
                "scene_duration_allocated scene_id=%s scene_order=%s scene_audio_duration_seconds=%.3f scene_visual_duration_seconds=%.3f",
                scene_id,
                scene_order,
                scene_duration,
                duration,
            )

    if outro_path and os.path.exists(outro_path):
        clips.append(outro_path)
        clip_durations.append(5)

    if not clips:
        logger.error("No valid scene visual clips found — refusing placeholder render")
        if allow_placeholder_render:
            logger.warning("Diagnostic placeholder render enabled; generating placeholder output")
            await _create_placeholder(output_path, w, h)
            return True
        return False

    # 2. Normalize each clip to the target resolution
    normalized = []
    image_exts = (".jpg", ".jpeg", ".png", ".webp")
    for i, clip in enumerate(clips):
        norm = output_path + f"_norm_{i}.mp4"
        duration = max(float(clip_durations[i] or 5), MIN_NORMALIZED_DURATION_SECONDS)
        clip_is_image = clip.lower().endswith(image_exts)

        if clip_is_image:
            normal_cmd = [
                "ffmpeg",
                "-y",
                "-framerate",
                "30",
                "-loop",
                "1",
                "-i",
                clip,
                "-t",
                str(duration),
                "-vf",
                f"{scale_filter},format=yuv420p",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                norm,
            ]
            ok, err = await _run_async(normal_cmd)

            if ok and os.path.exists(norm) and os.path.getsize(norm) > MIN_NORMALIZED_CLIP_SIZE_BYTES:
                normalized.append(norm)
            else:
                if os.path.exists(norm):
                    try:
                        os.remove(norm)
                    except OSError:
                        pass
                logger.error(f"Image normalization failed for clip {clip}: {err[-300:]}")

                fallback_cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:s={w}x{h}:r=30:d={duration}",
                    "-loop",
                    "1",
                    "-i",
                    clip,
                    "-filter_complex",
                    (
                        f"[1:v]{scale_filter},format=rgba[img];"
                        f"[0:v][img]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]"
                    ),
                    "-map",
                    "[v]",
                    "-t",
                    str(duration),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    norm,
                ]
                fallback_ok, fallback_err = await _run_async(fallback_cmd)
                if (
                    fallback_ok
                    and os.path.exists(norm)
                    and os.path.getsize(norm) > MIN_NORMALIZED_CLIP_SIZE_BYTES
                ):
                    normalized.append(norm)
                    logger.info(f"Fallback image normalization succeeded for clip {clip}")
                else:
                    if os.path.exists(norm):
                        try:
                            os.remove(norm)
                        except OSError:
                            pass
                    logger.error(
                        f"Fallback image normalization failed for clip {clip}: {fallback_err[-300:]}"
                    )
                    logger.info("trying mpeg4 image fallback")
                    mpeg4_fallback_cmd = [
                        "ffmpeg",
                        "-y",
                        "-framerate",
                        "30",
                        "-loop",
                        "1",
                        "-i",
                        clip,
                        "-t",
                        str(duration),
                        "-vf",
                        f"{scale_filter},format=yuv420p",
                        "-an",
                        "-c:v",
                        "mpeg4",
                        "-q:v",
                        "5",
                        "-r",
                        "30",
                        norm,
                    ]
                    mpeg4_ok, mpeg4_err = await _run_async(mpeg4_fallback_cmd)
                    if (
                        mpeg4_ok
                        and os.path.exists(norm)
                        and os.path.getsize(norm) > MIN_NORMALIZED_CLIP_SIZE_BYTES
                    ):
                        normalized.append(norm)
                        logger.info("mpeg4 image fallback succeeded")
                    else:
                        if os.path.exists(norm):
                            try:
                                os.remove(norm)
                            except OSError:
                                pass
                        logger.error(f"mpeg4 image fallback failed: {mpeg4_err[-300:]}")
            continue

        clip_actual_duration = _probe_duration(clip)
        if clip_actual_duration < MIN_VALID_CLIP_PROBE_SECONDS:
            logger.warning(
                f"Skipping clip with invalid/too-short probed duration: {clip} "
                f"(duration={clip_actual_duration:.3f}s)"
            )
            continue
        normal_cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            clip,
            "-t",
            str(duration),
            "-vf",
            scale_filter,
            "-r",
            "30",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            norm,
        ]
        ok, err = await _run_async(normal_cmd)

        if ok and os.path.exists(norm) and os.path.getsize(norm) > MIN_NORMALIZED_CLIP_SIZE_BYTES:
            normalized.append(norm)
            continue

        if os.path.exists(norm):
            try:
                os.remove(norm)
            except OSError:
                pass

        logger.warning(f"Normal normalization failed for clip {clip}: {err[-300:]}")

        fallback_cmd = [
            "ffmpeg",
            "-y",
            "-fflags",
            "+genpts",
            "-err_detect",
            "ignore_err",
            "-avoid_negative_ts",
            "make_zero",
            "-i",
            clip,
            "-t",
            str(duration),
            "-vf",
            scale_filter,
            "-r",
            "30",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            norm,
        ]
        fallback_ok, fallback_err = await _run_async(fallback_cmd)
        if (
            fallback_ok
            and os.path.exists(norm)
            and os.path.getsize(norm) > MIN_NORMALIZED_CLIP_SIZE_BYTES
        ):
            normalized.append(norm)
            logger.info(f"Fallback normalization succeeded for clip {clip}")
        else:
            logger.error(f"Fallback normalization failed for clip {clip}: {fallback_err[-300:]}")
            if os.path.exists(norm):
                try:
                    os.remove(norm)
                except OSError:
                    pass
            logger.info("trying mpeg4 video fallback")
            mpeg4_video_fallback_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                clip,
                "-t",
                str(duration),
                "-vf",
                scale_filter,
                "-r",
                "30",
                "-an",
                "-c:v",
                "mpeg4",
                "-q:v",
                "5",
                norm,
            ]
            mpeg4_video_ok, mpeg4_video_err = await _run_async(mpeg4_video_fallback_cmd)
            if (
                mpeg4_video_ok
                and os.path.exists(norm)
                and os.path.getsize(norm) > MIN_NORMALIZED_CLIP_SIZE_BYTES
            ):
                normalized.append(norm)
                logger.info("mpeg4 video fallback succeeded")
            else:
                if os.path.exists(norm):
                    try:
                        os.remove(norm)
                    except OSError:
                        pass
                logger.error(f"mpeg4 video fallback failed: {mpeg4_video_err[-300:]}")

    if not normalized:
        logger.error("No normalized clips were produced.")
        return False

    # 3. Concatenate all normalized clips
    concat_file = output_path + "_concat.txt"
    with open(concat_file, "w") as f:
        for p in normalized:
            f.write(f"file '{p}'\n")

    concat_path = output_path + "_concat.mp4"
    ok, _ = await _run_async([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c",
        "copy",
        "-an",
        concat_path,
    ])

    concat_valid = os.path.exists(concat_path) and os.path.getsize(concat_path) >= MIN_FINAL_OUTPUT_SIZE_BYTES
    if not ok or not concat_valid:
        logger.warning("concat copy failed or too small")
        logger.info("trying mpeg4 concat fallback")
        mpeg4_concat_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-an",
            "-r",
            "30",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            concat_path,
        ]
        mpeg4_concat_ok, _ = await _run_async(mpeg4_concat_cmd)
        concat_valid = os.path.exists(concat_path) and os.path.getsize(concat_path) >= MIN_FINAL_OUTPUT_SIZE_BYTES
        if mpeg4_concat_ok and concat_valid:
            logger.info("mpeg4 concat fallback succeeded")
            ok = True
        else:
            logger.error("mpeg4 concat fallback failed")
            return False

    # 4. Build final video-only command with subtitles/logo, then mux audio
    inputs = ["-i", concat_path]
    filter_parts = []
    audio_ok = audio_path and os.path.exists(audio_path)
    bg_ok = bg_music_path and os.path.exists(bg_music_path)

    if audio_ok:
        inputs += ["-i", audio_path]
    if bg_ok:
        inputs += ["-i", bg_music_path]

    video_stream = "[0:v]"

    # Logo overlay
    if logo_path and os.path.exists(logo_path):
        inputs += ["-i", logo_path]
        logo_idx = inputs.count("-i") - 1
        overlay_pos = _logo_overlay_pos(logo_position, w, h)
        filter_parts.append(f"{video_stream}[{logo_idx}:v]overlay={overlay_pos}[vlogo]")
        video_stream = "[vlogo]"

    # Subtitle burn-in (from SRT file)
    srt_path = output_path.replace(".mp4", ".srt")
    if subtitle_config and os.path.exists(srt_path):
        sub_style = _build_subtitle_style(subtitle_config, h)
        filter_parts.append(f"{video_stream}subtitles={srt_path}:force_style='{sub_style}'[vsub]")
        video_stream = "[vsub]"

    cmd = ["ffmpeg", "-y"] + inputs

    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts)]
        cmd += ["-map", video_stream]
    else:
        cmd += ["-map", "0:v"]

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
    ]

    final_candidate_path = output_path + ".tmp.mp4"
    cmd += ["-movflags", "+faststart", final_candidate_path]

    ok, err = await _run_async(cmd)
    candidate_exists = os.path.exists(final_candidate_path)
    candidate_size = os.path.getsize(final_candidate_path) if candidate_exists else 0
    candidate_duration = _probe_duration(final_candidate_path) if candidate_exists else 0.0
    logger.info(
        "libx264 final render output stats: candidate_path=%s exists=%s size_bytes=%s duration_seconds=%.3f return_ok=%s",
        final_candidate_path,
        candidate_exists,
        candidate_size,
        candidate_duration,
        ok,
    )
    final_valid = _valid_final_output(final_candidate_path)
    if final_valid:
        try:
            os.replace(final_candidate_path, output_path)
        except OSError as move_err:
            logger.error(f"failed moving validated final output candidate: {move_err}")
            final_valid = False
        else:
            logger.info("final output candidate validated and moved to output_path")
    else:
        if candidate_exists:
            try:
                os.remove(final_candidate_path)
            except OSError:
                pass

    if not ok or not final_valid:
        logger.info("trying mpeg4 final render fallback")
        if os.path.exists(final_candidate_path):
            try:
                os.remove(final_candidate_path)
            except OSError:
                pass

        mpeg4_cmd = ["ffmpeg", "-y"] + inputs

        if filter_parts:
            mpeg4_cmd += ["-filter_complex", ";".join(filter_parts)]
            mpeg4_cmd += ["-map", video_stream]
        else:
            mpeg4_cmd += ["-map", "0:v"]

        mpeg4_cmd += [
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
        ]

        mpeg4_cmd += [final_candidate_path]

        ok, err = await _run_async(mpeg4_cmd)
        fallback_exists = os.path.exists(final_candidate_path)
        fallback_size = os.path.getsize(final_candidate_path) if fallback_exists else 0
        fallback_duration = _probe_duration(final_candidate_path) if fallback_exists else 0.0
        logger.info(
            "mpeg4 final fallback output stats: candidate_path=%s exists=%s size_bytes=%s duration_seconds=%.3f return_ok=%s",
            final_candidate_path,
            fallback_exists,
            fallback_size,
            fallback_duration,
            ok,
        )
        fallback_valid = _valid_final_output(final_candidate_path)
        if fallback_valid and not ok:
            logger.info("final output exists and passed validation despite ffmpeg return code")
        if fallback_valid:
            try:
                os.replace(final_candidate_path, output_path)
            except OSError as move_err:
                logger.error(f"failed moving validated final output candidate: {move_err}")
                fallback_valid = False
            else:
                logger.info("final output candidate validated and moved to output_path")
        else:
            if fallback_exists:
                try:
                    os.remove(final_candidate_path)
                except OSError:
                    pass
        ok = fallback_valid
        if fallback_valid:
            logger.info("mpeg4 final render fallback succeeded")
        else:
            logger.error(f"mpeg4 final render fallback failed: {(err or '')[-500:]}")

    if not ok:
        logger.info("trying video-only final render fallback")
        if os.path.exists(final_candidate_path):
            try:
                os.remove(final_candidate_path)
            except OSError:
                pass

        video_only_cmd = ["ffmpeg", "-y", "-i", concat_path]
        if filter_parts:
            video_only_cmd += ["-filter_complex", ";".join(filter_parts)]
            video_only_cmd += ["-map", video_stream]
        else:
            video_only_cmd += ["-map", "0:v"]
        video_only_cmd += [
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            final_candidate_path,
        ]

        video_only_ok, video_only_err = await _run_async(video_only_cmd)
        vo_exists = os.path.exists(final_candidate_path)
        vo_size = os.path.getsize(final_candidate_path) if vo_exists else 0
        vo_duration = _probe_duration(final_candidate_path) if vo_exists else 0.0
        logger.info(
            "video-only final fallback output stats: candidate_path=%s exists=%s size_bytes=%s duration_seconds=%.3f return_ok=%s",
            final_candidate_path,
            vo_exists,
            vo_size,
            vo_duration,
            video_only_ok,
        )

        video_only_valid = _valid_final_output(final_candidate_path)
        if video_only_valid:
            try:
                os.replace(final_candidate_path, output_path)
            except OSError as move_err:
                logger.error(f"failed moving validated final output candidate: {move_err}")
                video_only_valid = False
            else:
                logger.info("final output candidate validated and moved to output_path")
                logger.info("video-only final render fallback succeeded")
        else:
            if vo_exists:
                try:
                    os.remove(final_candidate_path)
                except OSError:
                    pass
            logger.error(f"video-only final render fallback failed: {(video_only_err or '')[-500:]}")
            logger.info("video-only final render fallback failed")

        ok = video_only_valid

    # Cleanup temp files
    for f in normalized + [concat_file, concat_path]:
        try:
            os.remove(f)
        except Exception:
            pass

    if not ok:
        logger.error(f"Final composition failed: {err[-300:]}")
        return False

    if not _valid_final_output(output_path):
        logger.error(f"Final video file invalid: {output_path}")
        return False

    final_visual_duration = _probe_duration(output_path)
    final_audio_duration = _probe_duration(audio_path) if audio_ok and os.path.exists(audio_path) else 0.0
    duration_delta = abs(final_visual_duration - final_audio_duration) if final_audio_duration > 0 else 0.0
    logger.info(
        "duration metrics total_visual_duration_seconds=%.3f combined_narration_duration_seconds=%.3f final_visual_duration_seconds=%.3f final_audio_duration_seconds=%.3f duration_sync_status=%s",
        sum(clip_durations),
        final_audio_duration,
        final_visual_duration,
        final_audio_duration,
        "in_sync" if duration_delta <= 0.5 else "out_of_sync",
    )

    if final_audio_duration > 0 and duration_delta > 0.5:
        sync_path = output_path + ".sync.mp4"
        sync_cmd = ["ffmpeg", "-y", "-i", output_path, "-t", str(final_audio_duration), "-c:v", "copy", sync_path]
        sync_ok, _ = await _run_async(sync_cmd)
        if sync_ok and _valid_final_output(sync_path):
            os.replace(sync_path, output_path)
            final_visual_duration = _probe_duration(output_path)
            logger.info("duration sync corrected final_visual_duration_seconds=%.3f", final_visual_duration)

    if audio_ok and os.path.exists(audio_path):
        mux_ok = await _mux_audio_into_video(output_path, audio_path, output_path)
        if not mux_ok:
            logger.warning("audio mux failed, keeping video-only output")

    return True




def _has_audio_stream(path: str) -> bool:
    try:
        r = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path
        ], capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and "audio" in (r.stdout or "")
    except Exception:
        return False


async def _mux_audio_into_video(video_path: str, audio_path: str, output_path: str) -> bool:
    temp_out = output_path + ".mux.tmp.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", temp_out
    ]
    ok, err = await _run_async(cmd)
    if not ok:
        logger.error("audio mux ffmpeg failed: %s", (err or "")[-500:])
        return False
    if not _valid_final_output(temp_out) or not _has_audio_stream(temp_out):
        logger.error("audio mux output invalid or missing audio stream: %s", temp_out)
        return False
    os.replace(temp_out, output_path)
    logger.info("final video with audio mux succeeded")
    return True
def _logo_overlay_pos(position: str, w: int, h: int) -> str:
    pad = 20
    positions = {
        "top-right": f"{w}-overlay_w-{pad}:{pad}",
        "top-left": f"{pad}:{pad}",
        "bottom-right": f"{w}-overlay_w-{pad}:{h}-overlay_h-{pad}",
        "bottom-left": f"{pad}:{h}-overlay_h-{pad}",
    }
    return positions.get(position, positions["top-right"])


def _build_subtitle_style(config: dict, frame_height: int) -> str:
    size_map = {"small": 18, "medium": 24, "large": 32}
    font_size = size_map.get(config.get("subtitle_size", "large"), 28)
    color = _color_to_ass(config.get("subtitle_color", "#ffffff"))
    position_map = {"bottom": 2, "top": 8, "center": 5}
    alignment = position_map.get(config.get("subtitle_position", "bottom"), 2)
    margin_v = int(frame_height * 0.05)
    return (
        f"FontSize={font_size},PrimaryColour={color},"
        f"Alignment={alignment},MarginV={margin_v},"
        f"BorderStyle=3,Outline=1,Shadow=0.5,"
        f"Bold=1"
    )


def _color_to_ass(hex_color: str) -> str:
    """Convert #RRGGBB to ASS &H00BBGGRR format."""
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H00{b}{g}{r}"


async def _create_placeholder(output_path: str, w: int, h: int) -> None:
    await _run_async([
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:size={w}x{h}:duration=3:rate=25",
        "-an",
        "-c:v",
        "mpeg4",
        "-q:v",
        "5",
        output_path,
    ])


async def generate_srt(scenes: list[dict], output_path: str) -> str:
    """
    Write an SRT subtitle file from scene timings.
    scenes must have: script_text, start_time, actual_duration
    """
    lines = []
    for i, scene in enumerate(scenes, 1):
        start = scene.get("start_time", 0)
        dur = scene.get("actual_duration", scene.get("duration", 5))
        text = scene.get("script_text", "")
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{_srt_time(start)} --> {_srt_time(start + dur)}")
        lines.append(text.strip())
        lines.append("")
    srt_path = output_path.replace(".mp4", ".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return srt_path


def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def convert_aspect_ratio(input_path: str, output_path: str, aspect_ratio: str) -> bool:
    w, h = DIMENSIONS.get(aspect_ratio, (1920, 1080))
    ok, _ = await _run_async([
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        _scale_filter(w, h),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "21",
        "-c:a",
        "copy",
        output_path,
    ])
    return ok
