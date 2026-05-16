import os
import hashlib
import logging
import subprocess
from app.config import settings

logger = logging.getLogger(__name__)

VOICES = [
    {"id": "edge_ar_default", "name": "Shakir (AR Male)", "language": "ar"},
    {"id": "edge_en_default", "name": "Guy (EN Male)", "language": "en"},
    {"id": "edge_tr_default", "name": "Ahmet (TR Male)", "language": "tr"},
]

EDGE_DEFAULTS = {
    "ar": ("ar-EG-ShakirNeural", "ar-EG-SalmaNeural"),
    "en": ("en-US-GuyNeural", "en-US-JennyNeural"),
    "tr": ("tr-TR-AhmetNeural", "tr-TR-EmelNeural"),
}


def _normalize_lang(language: str | None) -> str:
    value = (language or "").strip().lower()
    if value in {"arabic", "ar"}:
        return "ar"
    if value in {"english", "en"}:
        return "en"
    if value in {"turkish", "tr", "türkçe", "turkce"}:
        return "tr"
    return "unknown"


def _probe_duration(path: str) -> float:
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
        return float((r.stdout or "0").strip() or 0)
    except Exception:
        return 0.0


def _valid_audio_file(path: str) -> bool:
    if not path or not os.path.exists(path):
        return False
    if os.path.getsize(path) <= 5_000:
        return False
    return _probe_duration(path) > 0.5


def _select_edge_tts_voice(language: str | None) -> str:
    lang = _normalize_lang(language)
    if lang == "ar":
        return settings.EDGE_TTS_VOICE_AR or EDGE_DEFAULTS["ar"][0]
    if lang == "en":
        return settings.EDGE_TTS_VOICE_EN or EDGE_DEFAULTS["en"][0]
    if lang == "tr":
        return settings.EDGE_TTS_VOICE_TR or EDGE_DEFAULTS["tr"][0]
    return settings.EDGE_TTS_VOICE or settings.EDGE_TTS_VOICE_EN or EDGE_DEFAULTS["en"][0]


async def generate_speech(text: str, voice_id: str, speed: float = 1.0, output_dir: str = None, language: str = "en") -> str:
    out_dir = output_dir or settings.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    selected_voice = _select_edge_tts_voice(language) if voice_id.startswith("edge_") else voice_id
    provider = (settings.TTS_PROVIDER or "edge_tts").strip().lower()
    filename = hashlib.md5(f"{selected_voice}_{speed}_{text[:100]}".encode()).hexdigest() + ".mp3"
    output_path = os.path.join(out_dir, filename)

    if os.path.exists(output_path) and _valid_audio_file(output_path):
        return output_path

    if provider == "edge_tts":
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text=text, voice=selected_voice, rate=f"{int((speed - 1.0) * 100):+d}%")
            await communicate.save(output_path)
            logger.info(
                "tts generated provider=%s project_language=%s selected_tts_voice=%s generated_audio_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f",
                provider,
                language,
                selected_voice,
                output_path,
                os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                _probe_duration(output_path),
            )
            if _valid_audio_file(output_path):
                return output_path
            raise RuntimeError("edge_tts output failed validation")
        except Exception as e:
            logger.error("edge_tts failed, falling back provider=fallback error=%s", str(e), exc_info=True)

    try:
        from gtts import gTTS

        lang = _normalize_lang(language)
        tts = gTTS(text=text, lang=(lang if lang in {"ar", "en", "tr"} else "en"), slow=(speed < 0.8))
        tts.save(output_path)
        logger.info(
            "tts generated provider=fallback project_language=%s selected_tts_voice=%s generated_audio_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f",
            language,
            selected_voice,
            output_path,
            os.path.getsize(output_path) if os.path.exists(output_path) else 0,
            _probe_duration(output_path),
        )
        return output_path
    except Exception as e:
        logger.error("fallback tts failed: %s", str(e), exc_info=True)
        return ""
