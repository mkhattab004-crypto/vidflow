import os
import asyncio
import hashlib
import logging
from typing import Optional
from app.config import settings
from app.services.kokoro_tts import generate_speech

logger = logging.getLogger(__name__)

# Average spoken words per second at normal speed
_WPS = 2.5


def _estimate_duration(text: str, speed: float = 1.0) -> float:
    words = len(text.split())
    return max(1.0, words / (_WPS * max(speed, 0.5)))


async def assemble_project_audio(
    scenes: list[dict],
    voice_id: str,
    speed: float,
    project_id: str,
    bg_music_path: Optional[str] = None,
) -> str:
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(out_dir, exist_ok=True)
    final_path = os.path.join(out_dir, "narration.mp3")

    tasks = [
        _generate_scene_audio(scene["script_text"] or "", voice_id, speed, out_dir, scene.get("id", i))
        for i, scene in enumerate(scenes)
    ]
    scene_paths = await asyncio.gather(*tasks)

    valid_paths = [p for p in scene_paths if p and os.path.exists(p)]
    if not valid_paths:
        _create_silent_mp3(final_path)
        return final_path

    # Concatenate MP3 files at byte level — works for sequential playback
    with open(final_path, "wb") as out:
        for path in valid_paths:
            try:
                with open(path, "rb") as f:
                    out.write(f.read())
            except Exception as e:
                logger.warning(f"Could not read {path}: {e}")

    logger.info(f"Assembled {len(valid_paths)} scene audio files → {final_path}")
    return final_path


async def _generate_scene_audio(
    text: str,
    voice_id: str,
    speed: float,
    out_dir: str,
    scene_id,
) -> Optional[str]:
    if not text.strip():
        return None
    fname = f"scene_{scene_id}_{hashlib.md5(text[:50].encode()).hexdigest()[:8]}.mp3"
    path = os.path.join(out_dir, fname)
    if os.path.exists(path):
        return path
    try:
        return await generate_speech(text, voice_id, speed, out_dir)
    except Exception as e:
        logger.warning(f"Scene {scene_id} TTS failed: {e}")
        _create_silent_mp3(path)
        return path


def _create_silent_mp3(path: str) -> None:
    with open(path, "wb") as f:
        f.write(b"\xff\xfb\x90\x00" + b"\x00" * 413)


def get_audio_duration(path: str, text: str = "", speed: float = 1.0) -> float:
    """Estimate audio duration from text length (no binary parsing needed)."""
    if text:
        return _estimate_duration(text, speed)
    # Rough estimate from file size: ~16 kbps MP3 ≈ 2000 bytes/sec
    try:
        size = os.path.getsize(path)
        return max(1.0, size / 2000)
    except Exception:
        return 5.0


async def generate_scene_timings(scenes: list[dict], voice_id: str, speed: float, project_id: str) -> list[dict]:
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(out_dir, exist_ok=True)
    result = []
    current_time = 0.0
    for scene in scenes:
        text = scene.get("script_text") or ""
        duration = _estimate_duration(text, speed) if text.strip() else scene.get("duration", 5)
        result.append({**scene, "start_time": current_time, "actual_duration": duration})
        current_time += duration
    return result
