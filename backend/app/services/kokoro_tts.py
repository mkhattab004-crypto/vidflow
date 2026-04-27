"""
Kokoro TTS integration.
Kokoro is a local TTS engine. If not installed, falls back to a placeholder.
"""
import os
import asyncio
import hashlib
from app.config import settings

VOICES = [
    {"id": "af_bella", "name": "Bella (EN Female)", "language": "en"},
    {"id": "af_sarah", "name": "Sarah (EN Female)", "language": "en"},
    {"id": "am_adam", "name": "Adam (EN Male)", "language": "en"},
    {"id": "am_michael", "name": "Michael (EN Male)", "language": "en"},
    {"id": "bf_emma", "name": "Emma (EN-GB Female)", "language": "en"},
    {"id": "bm_george", "name": "George (EN-GB Male)", "language": "en"},
    {"id": "af_nicole", "name": "Nicole (EN Female)", "language": "en"},
    {"id": "af_sky", "name": "Sky (EN Female)", "language": "en"},
    # Arabic voices
    {"id": "ar_hamza", "name": "Hamza (AR Male)", "language": "ar"},
    {"id": "ar_layla", "name": "Layla (AR Female)", "language": "ar"},
    # Quran reciters (special)
    {"id": "quran_abdulbasit", "name": "عبدالباسط عبدالصمد", "language": "ar", "type": "reciter"},
    {"id": "quran_husary", "name": "محمود خليل الحصري", "language": "ar", "type": "reciter"},
    {"id": "quran_afasy", "name": "مشاري العفاسي", "language": "ar", "type": "reciter"},
    {"id": "quran_ghamdi", "name": "سعد الغامدي", "language": "ar", "type": "reciter"},
    {"id": "quran_minshawi", "name": "محمد صديق المنشاوي", "language": "ar", "type": "reciter"},
    # Turkish
    {"id": "tr_ali", "name": "Ali (TR Male)", "language": "tr"},
    {"id": "tr_ayse", "name": "Ayşe (TR Female)", "language": "tr"},
]


async def generate_speech(text: str, voice_id: str, speed: float = 1.0, output_dir: str = None) -> str:
    out_dir = output_dir or settings.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    filename = hashlib.md5(f"{voice_id}_{speed}_{text[:100]}".encode()).hexdigest() + ".wav"
    output_path = os.path.join(out_dir, filename)
    if os.path.exists(output_path):
        return output_path
    try:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
        samples, sample_rate = kokoro.create(text, voice=voice_id, speed=speed, lang="en-us")
        import soundfile as sf
        sf.write(output_path, samples, sample_rate)
        return output_path
    except ImportError:
        # Kokoro not installed — create a silent placeholder
        _create_silent_wav(output_path, duration=max(3, len(text) // 15))
        return output_path
    except Exception:
        _create_silent_wav(output_path, duration=max(3, len(text) // 15))
        return output_path


def _create_silent_wav(path: str, duration: int = 5):
    import struct
    sample_rate = 22050
    num_samples = sample_rate * duration
    with open(path, "wb") as f:
        # WAV header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + num_samples * 2))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", num_samples * 2))
        f.write(b"\x00" * num_samples * 2)
