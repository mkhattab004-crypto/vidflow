import os
import asyncio
import hashlib
import logging
import subprocess
from typing import Optional
from app.config import settings
from app.services.kokoro_tts import generate_speech

logger = logging.getLogger(__name__)
_WPS = 2.5


def _estimate_duration(text: str, speed: float = 1.0) -> float:
    words = len(text.split())
    return max(1.0, words / (_WPS * max(speed, 0.5)))


def _probe_duration(path: str) -> float:
    try:
        r = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path
        ], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return 0.0
        return float((r.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def _valid_audio_file(path: str) -> bool:
    return bool(path and os.path.exists(path) and os.path.getsize(path) > 5_000 and _probe_duration(path) > 0.5)


async def assemble_project_audio(scenes: list[dict], voice_id: str, speed: float, project_id: str, language: str = "en", bg_music_path: Optional[str] = None) -> str:
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(out_dir, exist_ok=True)
    final_path = os.path.join(out_dir, "narration.mp3")

    tasks = [_generate_scene_audio(scene["script_text"] or "", voice_id, speed, out_dir, scene.get("id", i), language) for i, scene in enumerate(scenes)]
    scene_paths = await asyncio.gather(*tasks)
    valid_paths = [p for p in scene_paths if _valid_audio_file(p)]
    if not valid_paths:
        return ""

    concat_list = os.path.join(out_dir, "narration_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in valid_paths:
            f.write(f"file '{path}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c:a", "libmp3lame", "-b:a", "192k", final_path]
    proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        logger.error("audio concat failed: %s", (proc.stderr or "")[-500:])
        return ""

    duration = _probe_duration(final_path)
    logger.info(
        "combined_narration_path=%s combined_narration_duration_seconds=%.3f project_language=%s",
        final_path,
        duration,
        language,
    )
    return final_path if _valid_audio_file(final_path) else ""


async def _generate_scene_audio(text: str, voice_id: str, speed: float, out_dir: str, scene_id, language: str) -> Optional[str]:
    if not text.strip():
        return None
    fname = f"scene_{scene_id}_{hashlib.md5(text[:50].encode()).hexdigest()[:8]}.mp3"
    path = os.path.join(out_dir, fname)
    generated = await generate_speech(text, voice_id, speed, out_dir, language=language)
    if generated and _valid_audio_file(generated):
        logger.info(
            "scene_id=%s generated_audio_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f",
            scene_id,
            generated,
            os.path.getsize(generated),
            _probe_duration(generated),
        )
    return generated


def get_audio_duration(path: str, text: str = "", speed: float = 1.0) -> float:
    if text:
        return _estimate_duration(text, speed)
    try:
        size = os.path.getsize(path)
        return max(1.0, size / 2000)
    except Exception:
        return 5.0


async def generate_scene_timings(scenes: list[dict], voice_id: str, speed: float, project_id: str) -> list[dict]:
    result = []
    current_time = 0.0
    for scene in scenes:
        text = scene.get("script_text") or ""
        duration = _estimate_duration(text, speed) if text.strip() else scene.get("duration", 5)
        result.append({**scene, "start_time": current_time, "actual_duration": duration})
        current_time += duration
    return result
