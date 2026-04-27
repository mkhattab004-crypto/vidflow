"""
Audio assembly service.
Generates per-scene TTS audio, then concatenates into one final narration file.
Optionally mixes background music at low volume.
"""
import os
import asyncio
import struct
import hashlib
import logging
from typing import Optional
from app.config import settings
from app.services.kokoro_tts import generate_speech

logger = logging.getLogger(__name__)


async def assemble_project_audio(
    scenes: list[dict],
    voice_id: str,
    speed: float,
    project_id: str,
    bg_music_path: Optional[str] = None,
) -> str:
    """
    Generate TTS for every scene, concatenate WAV files, and return the final audio path.
    scenes: list of {"id": int, "script_text": str, "duration": float}
    """
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(out_dir, exist_ok=True)
    final_path = os.path.join(out_dir, "narration.wav")

    # Generate per-scene audio in parallel
    tasks = [
        _generate_scene_audio(
            scene["script_text"] or "",
            voice_id,
            speed,
            out_dir,
            scene.get("id", i),
        )
        for i, scene in enumerate(scenes)
    ]
    scene_paths = await asyncio.gather(*tasks)

    valid_paths = [p for p in scene_paths if p and os.path.exists(p)]
    if not valid_paths:
        _create_silent_wav(final_path, 3)
        return final_path

    _concat_wav_files(valid_paths, final_path)
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
    fname = f"scene_{scene_id}_{hashlib.md5(text[:50].encode()).hexdigest()[:8]}.wav"
    path = os.path.join(out_dir, fname)
    if os.path.exists(path):
        return path
    try:
        return await generate_speech(text, voice_id, speed, out_dir)
    except Exception as e:
        logger.warning(f"Scene {scene_id} TTS failed: {e}")
        _create_silent_wav(path, max(2, len(text) // 15))
        return path


def _concat_wav_files(paths: list[str], output_path: str) -> None:
    """Concatenate multiple WAV files (same sample rate) into one."""
    audio_data = bytearray()
    sample_rate = 22050
    for p in paths:
        try:
            with open(p, "rb") as f:
                data = f.read()
            # Skip 44-byte WAV header, take PCM samples
            if len(data) > 44 and data[:4] == b"RIFF":
                audio_data += data[44:]
            elif len(data) > 44:
                audio_data += data[44:]
        except Exception as e:
            logger.warning(f"Could not read {p}: {e}")
            continue

    _write_wav(output_path, bytes(audio_data), sample_rate)


def _write_wav(path: str, pcm_data: bytes, sample_rate: int = 22050) -> None:
    num_samples = len(pcm_data) // 2
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + len(pcm_data)))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", len(pcm_data)))
        f.write(pcm_data)


def _create_silent_wav(path: str, duration: int = 5, sample_rate: int = 22050) -> None:
    pcm = b"\x00" * sample_rate * duration * 2
    _write_wav(path, pcm, sample_rate)


def get_audio_duration(path: str) -> float:
    """Read WAV header and return duration in seconds."""
    try:
        with open(path, "rb") as f:
            f.seek(24)
            sample_rate = struct.unpack("<I", f.read(4))[0]
            f.seek(40)
            data_size = struct.unpack("<I", f.read(4))[0]
            return data_size / (sample_rate * 2)
    except Exception:
        return 0.0


async def generate_scene_timings(scenes: list[dict], voice_id: str, speed: float, project_id: str) -> list[dict]:
    """
    Returns scenes enriched with actual audio durations for accurate SRT generation.
    """
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(out_dir, exist_ok=True)
    result = []
    current_time = 0.0
    for scene in scenes:
        text = scene.get("script_text") or ""
        if text.strip():
            audio_path = await _generate_scene_audio(text, voice_id, speed, out_dir, scene.get("id", 0))
            duration = get_audio_duration(audio_path) if audio_path else scene.get("duration", 5)
        else:
            duration = scene.get("duration", 5)
        result.append({**scene, "start_time": current_time, "actual_duration": duration})
        current_time += duration
    return result
