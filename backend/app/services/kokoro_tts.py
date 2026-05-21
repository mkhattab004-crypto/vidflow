import os
import hashlib
import logging
import subprocess
import json
import urllib.request
import urllib.error
from app.config import settings

logger = logging.getLogger(__name__)

VOICES = [
    {"id": "edge_ar_default", "name": "Shakir (AR Male)", "language": "ar"},
    {"id": "edge_en_default", "name": "Guy (EN Male)", "language": "en"},
    {"id": "edge_tr_default", "name": "Ahmet (TR Male)", "language": "tr"},
    {"id": "gtts-ar", "name": "Arabic gTTS", "language": "ar"},
    {"id": "gtts-en", "name": "English gTTS", "language": "en"},
    {"id": "gtts-tr", "name": "Turkish gTTS", "language": "tr"},
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


def _voice_gender(voice_name: str) -> str:
    lower_voice = (voice_name or "").lower()
    if any(name in lower_voice for name in ["shakir", "guy", "ahmet", "male"]):
        return "male"
    if any(name in lower_voice for name in ["salma", "jenny", "emel", "female"]):
        return "female"
    return "unknown"


def _select_edge_tts_voice(language: str | None) -> str:
    lang = _normalize_lang(language)
    if lang == "ar":
        return settings.EDGE_TTS_VOICE_AR or EDGE_DEFAULTS["ar"][0]
    if lang == "en":
        return settings.EDGE_TTS_VOICE_EN or EDGE_DEFAULTS["en"][0]
    if lang == "tr":
        return settings.EDGE_TTS_VOICE_TR or EDGE_DEFAULTS["tr"][0]
    return settings.EDGE_TTS_VOICE or settings.EDGE_TTS_VOICE_EN or EDGE_DEFAULTS["en"][0]


def _select_gtts_voice(language: str | None) -> str:
    lang = _normalize_lang(language)
    return f"gtts-{lang if lang in {'ar', 'en', 'tr'} else 'en'}"


def _generate_with_gtts(text: str, language: str, output_path: str) -> str:
    from gtts import gTTS

    lang = _normalize_lang(language)
    selected_lang = lang if lang in {"ar", "en", "tr"} else "en"
    tts = gTTS(text=text, lang=selected_lang)
    tts.save(output_path)
    if not _valid_audio_file(output_path):
        raise RuntimeError("gTTS output failed validation")
    return f"gtts-{selected_lang}"


def resolve_voice_for_project(language: str | None, selected_voice: str | None, user_selected: bool = False) -> tuple[str, str]:
    lang = _normalize_lang(language)
    lang_default_map = {"ar": "edge_ar_default", "en": "edge_en_default", "tr": "edge_tr_default"}
    default_voice_id = lang_default_map.get(lang, "edge_en_default")
    candidate = (selected_voice or "").strip()
    if not candidate:
        return default_voice_id, "language_default"
    if candidate.startswith("edge_") and candidate.endswith("_default"):
        return candidate, "requested_default"
    if lang != "unknown" and not candidate.lower().startswith(f"{lang}-"):
        return default_voice_id, "language_mismatch_override"
    if lang == "ar" and not user_selected and _voice_gender(candidate) == "female":
        return default_voice_id, "override_implicit_female_arabic"
    return candidate, "user_selected"


async def generate_speech(
    text: str,
    voice_id: str,
    speed: float = 1.0,
    output_dir: str = None,
    language: str = "en",
    provider_override: str | None = None,
) -> str:
    out_dir = output_dir or settings.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    selected_voice = _select_edge_tts_voice(language) if voice_id.startswith("edge_") else voice_id
    provider = (provider_override or settings.TTS_PROVIDER or "edge_tts").strip().lower()
    filename = hashlib.md5(f"{selected_voice}_{speed}_{text[:100]}".encode()).hexdigest() + ".mp3"
    output_path = os.path.join(out_dir, filename)

    if os.path.exists(output_path) and _valid_audio_file(output_path):
        return output_path

    log_prefix = (
        "project_language=%s selected_tts_provider=%s selected_tts_voice=%s voice_gender=%s "
        "tts_engine_function_called=%s fallback_used=%s"
    )

    if provider == "edge_tts":
        try:
            import edge_tts

            logger.info(
                log_prefix,
                language,
                provider,
                selected_voice,
                _voice_gender(selected_voice),
                "edge_tts.Communicate",
                "false",
            )
            communicate = edge_tts.Communicate(text=text, voice=selected_voice, rate=f"{int((speed - 1.0) * 100):+d}%")
            await communicate.save(output_path)
            logger.info(
                "provider_that_generated_audio=%s voice_that_generated_audio=%s audio_output_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f",
                "edge_tts",
                selected_voice,
                output_path,
                os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                _probe_duration(output_path),
            )
            if _valid_audio_file(output_path):
                return output_path
            raise RuntimeError("edge_tts output failed validation")
        except Exception as e:
            logger.error("edge_tts failed with error=%s", str(e), exc_info=True)
            if settings.TTS_FALLBACK_ENABLED:
                logger.info("edge_tts failed, attempting gtts fallback")
                selected_gtts_voice = _generate_with_gtts(text=text, language=language, output_path=output_path)
                logger.info(
                    "provider_that_generated_audio=%s voice_that_generated_audio=%s audio_output_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f fallback_used=true",
                    "gtts",
                    selected_gtts_voice,
                    output_path,
                    os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                    _probe_duration(output_path),
                )
                return output_path
            raise RuntimeError(f"Edge TTS failed: {e}") from e

    if provider == "gtts":
        logger.info(log_prefix, language, provider, _select_gtts_voice(language), "unknown", "gtts.gTTS", "false")
        selected_gtts_voice = _generate_with_gtts(text=text, language=language, output_path=output_path)
        logger.info(
            "provider_that_generated_audio=%s voice_that_generated_audio=%s audio_output_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f fallback_used=false",
            "gtts",
            selected_gtts_voice,
            output_path,
            os.path.getsize(output_path) if os.path.exists(output_path) else 0,
            _probe_duration(output_path),
        )
        return output_path

    if provider == "free_api":
        api_url = (settings.FREE_TTS_API_URL or "").strip()
        if not api_url:
            raise RuntimeError("FREE_TTS_API_URL is required when TTS_PROVIDER=free_api")
        provider_name = (settings.FREE_TTS_PROVIDER_NAME or "free_api").strip() or "free_api"
        headers = {"Content-Type": "application/json"}
        if settings.FREE_TTS_API_KEY:
            headers["Authorization"] = f"Bearer {settings.FREE_TTS_API_KEY}"

        logger.info(
            log_prefix,
            language,
            provider,
            selected_voice,
            _voice_gender(selected_voice),
            "external_free_tts_api",
            "false",
        )
        payload = json.dumps({"text": text, "language": _normalize_lang(language), "voice": selected_voice, "speed": speed}).encode("utf-8")
        req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status < 200 or resp.status >= 300:
                    raise RuntimeError(f"free api returned status={resp.status}")
                data = resp.read()
            if not data:
                raise RuntimeError("free api returned empty body")
            with open(output_path, "wb") as f:
                f.write(data)
            if not _valid_audio_file(output_path):
                raise RuntimeError("free api audio output failed validation")
            logger.info(
                "provider_that_generated_audio=%s voice_that_generated_audio=%s audio_output_path=%s audio_size_bytes=%s audio_duration_seconds=%.3f",
                provider_name,
                selected_voice,
                output_path,
                os.path.getsize(output_path),
                _probe_duration(output_path),
            )
            return output_path
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as e:
            logger.error("free_api tts failed provider=%s error=%s", provider_name, str(e), exc_info=True)
            raise RuntimeError(f"Free TTS API failed: {e}") from e

    raise RuntimeError(f"Unsupported TTS_PROVIDER '{provider}'. Allowed: edge_tts, gtts, free_api")
