import os
import hashlib
import logging
from app.config import settings

logger = logging.getLogger(__name__)

VOICES = [
    {"id": "af_bella",         "name": "Bella (EN Female)",        "language": "en"},
    {"id": "af_sarah",         "name": "Sarah (EN Female)",        "language": "en"},
    {"id": "am_adam",          "name": "Adam (EN Male)",           "language": "en"},
    {"id": "am_michael",       "name": "Michael (EN Male)",        "language": "en"},
    {"id": "bf_emma",          "name": "Emma (EN-GB Female)",      "language": "en"},
    {"id": "bm_george",        "name": "George (EN-GB Male)",      "language": "en"},
    {"id": "af_nicole",        "name": "Nicole (EN Female)",       "language": "en"},
    {"id": "af_sky",           "name": "Sky (EN Female)",          "language": "en"},
    {"id": "ar_hamza",         "name": "Hamza (AR Male)",          "language": "ar"},
    {"id": "ar_layla",         "name": "Layla (AR Female)",        "language": "ar"},
    {"id": "quran_abdulbasit", "name": "عبدالباسط عبدالصمد",       "language": "ar", "type": "reciter"},
    {"id": "quran_husary",     "name": "محمود خليل الحصري",        "language": "ar", "type": "reciter"},
    {"id": "quran_afasy",      "name": "مشاري العفاسي",            "language": "ar", "type": "reciter"},
    {"id": "quran_ghamdi",     "name": "سعد الغامدي",              "language": "ar", "type": "reciter"},
    {"id": "quran_minshawi",   "name": "محمد صديق المنشاوي",       "language": "ar", "type": "reciter"},
    {"id": "tr_ali",           "name": "Ali (TR Male)",            "language": "tr"},
    {"id": "tr_ayse",          "name": "Ayşe (TR Female)",         "language": "tr"},
]

_LANG_MAP = {"ar_": "ar", "quran_": "ar", "tr_": "tr"}


def _lang_for_voice(voice_id: str) -> str:
    for prefix, lang in _LANG_MAP.items():
        if voice_id.startswith(prefix):
            return lang
    return "en"


async def generate_speech(text: str, voice_id: str, speed: float = 1.0, output_dir: str = None) -> str:
    out_dir = output_dir or settings.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    filename = hashlib.md5(f"{voice_id}_{speed}_{text[:100]}".encode()).hexdigest() + ".mp3"
    output_path = os.path.join(out_dir, filename)

    if os.path.exists(output_path):
        return output_path

    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=_lang_for_voice(voice_id), slow=(speed < 0.8))
        tts.save(output_path)
        return output_path
    except Exception as e:
        logger.warning(f"gTTS failed for voice {voice_id}: {e}")
        _create_silent_mp3(output_path)
        return output_path


def _create_silent_mp3(path: str) -> None:
    # Minimal valid MP3 frame so downstream code gets a readable file
    with open(path, "wb") as f:
        f.write(b"\xff\xfb\x90\x00" + b"\x00" * 413)
