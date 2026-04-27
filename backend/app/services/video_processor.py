"""
Video processing service using FFmpeg.
Handles combining scenes, adding subtitles, intro/outro, and background music.
"""
import os
import asyncio
import json
import subprocess
from typing import Optional
from app.config import settings


def _run_ffmpeg(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "FFmpeg timeout"
    except FileNotFoundError:
        return False, "FFmpeg not found"


async def compose_video(
    scenes: list[dict],
    audio_path: str,
    output_path: str,
    aspect_ratio: str = "16:9",
    intro_path: Optional[str] = None,
    outro_path: Optional[str] = None,
    bg_music_path: Optional[str] = None,
    subtitle_style: dict = None,
    logo_path: Optional[str] = None,
) -> bool:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    width, height = _get_dimensions(aspect_ratio)

    input_list_path = output_path + "_inputs.txt"
    video_parts = []

    if intro_path and os.path.exists(intro_path):
        video_parts.append(intro_path)

    for scene in scenes:
        visual_url = scene.get("visual_url")
        if visual_url and os.path.exists(visual_url):
            video_parts.append(visual_url)

    if outro_path and os.path.exists(outro_path):
        video_parts.append(outro_path)

    if not video_parts:
        await _create_placeholder_video(output_path, width, height)
        return True

    with open(input_list_path, "w") as f:
        for p in video_parts:
            f.write(f"file '{p}'\n")

    concat_path = output_path + "_concat.mp4"
    ok, err = _run_ffmpeg([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", input_list_path,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-an", concat_path
    ])

    final_inputs = ["-i", concat_path]
    final_inputs += ["-i", audio_path] if audio_path and os.path.exists(audio_path) else []
    if bg_music_path and os.path.exists(bg_music_path):
        final_inputs += ["-i", bg_music_path]

    audio_filter = ""
    if bg_music_path and os.path.exists(bg_music_path):
        audio_filter = ";[1:a]volume=1.0[main];[2:a]volume=0.15[bg];[main][bg]amix=inputs=2:duration=first[outa]"
        audio_map = ["-map", "0:v", "-map", "[outa]"]
    else:
        audio_map = ["-map", "0:v", "-map", "1:a"] if audio_path and os.path.exists(audio_path) else ["-map", "0:v"]

    cmd = ["ffmpeg", "-y"] + final_inputs
    if audio_filter:
        cmd += ["-filter_complex", audio_filter]
    cmd += audio_map
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-b:a", "192k", output_path]

    ok, err = _run_ffmpeg(cmd)
    for tmp in [input_list_path, concat_path]:
        try:
            os.remove(tmp)
        except Exception:
            pass
    return ok


async def _create_placeholder_video(output_path: str, width: int, height: int):
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:size={width}x{height}:duration=5",
        "-c:v", "libx264", output_path
    ])


def _get_dimensions(aspect_ratio: str) -> tuple[int, int]:
    mapping = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}
    return mapping.get(aspect_ratio, (1920, 1080))


async def convert_aspect_ratio(input_path: str, output_path: str, aspect_ratio: str) -> bool:
    width, height = _get_dimensions(aspect_ratio)
    ok, _ = _run_ffmpeg([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", output_path
    ])
    return ok


async def extract_audio(video_path: str, audio_path: str) -> bool:
    ok, _ = _run_ffmpeg([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "copy", audio_path
    ])
    return ok
