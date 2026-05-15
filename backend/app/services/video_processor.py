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
MIN_NORMALIZED_CLIP_SIZE_BYTES = 50_000
MIN_FINAL_OUTPUT_SIZE_BYTES = 1_000_000


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
    return await asyncio.to_thread(_run, cmd, timeout)


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


def _scale_filter(w: int, h: int) -> str:
    """Return an FFmpeg scale+pad filter that fills the frame without distortion."""
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1"
    )


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

    # 1. Build ordered list of video clips with their target durations
    clips = []
    clip_durations = []

    if intro_path and os.path.exists(intro_path):
        clips.append(intro_path)
        clip_durations.append(5)

    for scene in scenes:
        vurl = scene.get("visual_url", "")
        scene_duration = float(scene.get("duration", 10) or 10)

        if not vurl or not os.path.exists(vurl):
            continue

        scene_clips = []

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

    if outro_path and os.path.exists(outro_path):
        clips.append(outro_path)
        clip_durations.append(5)

    if not clips:
        logger.warning("No video clips available — creating placeholder")
        await _create_placeholder(output_path, w, h)
        return True

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
                f"{_scale_filter(w, h)},format=yuv420p",
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
                        f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,format=rgba[img];"
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
            continue

        clip_actual_duration = _probe_duration(clip)
        if clip_actual_duration < MIN_VALID_CLIP_PROBE_SECONDS:
            logger.warning(
                f"Skipping clip with invalid/too-short probed duration: {clip} "
                f"(duration={clip_actual_duration:.3f}s)"
            )
            continue
        if clip_actual_duration > 0:
            duration = min(duration, clip_actual_duration)

        if duration < MIN_VALID_CLIP_PROBE_SECONDS:
            logger.warning(
                f"Skipping clip due to normalization duration too short: {clip} "
                f"(target={duration:.3f}s)"
            )
            continue

        normal_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            clip,
            "-t",
            str(duration),
            "-vf",
            _scale_filter(w, h),
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
            _scale_filter(w, h),
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
    if not ok:
        logger.error("Failed to concatenate normalized clips.")
        return False
    if not os.path.exists(concat_path) or os.path.getsize(concat_path) < MIN_FINAL_OUTPUT_SIZE_BYTES:
        logger.error(
            f"Concatenated video file missing or too small ({MIN_FINAL_OUTPUT_SIZE_BYTES} bytes min): "
            f"{concat_path}"
        )
        return False

    # 4. Build final command with audio, subtitles, logo
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

    # Audio mix
    audio_map = []
    if audio_ok and bg_ok:
        a_idx = inputs.index(audio_path) // 2
        bg_idx = inputs.index(bg_music_path) // 2
        filter_parts.append(
            f"[{a_idx}:a]volume=1.0[main];"
            f"[{bg_idx}:a]volume=0.12,aloop=loop=-1:size=2e+09[bg];"
            f"[main][bg]amix=inputs=2:duration=first[aout]"
        )
        audio_map = ["-map", "[aout]"]
    elif audio_ok:
        a_idx = inputs.index(audio_path) // 2
        audio_map = ["-map", f"{a_idx}:a"]

    cmd = ["ffmpeg", "-y"] + inputs

    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts)]
        cmd += ["-map", video_stream]
    else:
        cmd += ["-map", "0:v"]

    cmd += audio_map

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

    if audio_ok or bg_ok:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

    cmd += ["-movflags", "+faststart", output_path]

    ok, err = await _run_async(cmd)

    # Cleanup temp files
    for f in normalized + [concat_file, concat_path]:
        try:
            os.remove(f)
        except Exception:
            pass

    if not ok:
        logger.error(f"Final composition failed: {err[-300:]}")
        return False

    if not os.path.exists(output_path) or os.path.getsize(output_path) < MIN_FINAL_OUTPUT_SIZE_BYTES:
        logger.error(f"Final video file missing or too small: {output_path}")
        return False

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
        "-c:v",
        "libx264",
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
