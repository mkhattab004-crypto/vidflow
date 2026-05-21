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

EDGE_STATIC_SAFE_LIST = {
    "ar": [
        {"ShortName": "ar-EG-ShakirNeural", "Gender": "Male", "Locale": "ar-EG"},
        {"ShortName": "ar-EG-SalmaNeural", "Gender": "Female", "Locale": "ar-EG"},
        {"ShortName": "ar-SA-HamedNeural", "Gender": "Male", "Locale": "ar-SA"},
        {"ShortName": "ar-SA-ZariyahNeural", "Gender": "Female", "Locale": "ar-SA"},
    ],
    "en": [
        {"ShortName": "en-US-GuyNeural", "Gender": "Male", "Locale": "en-US"},
        {"ShortName": "en-US-JennyNeural", "Gender": "Female", "Locale": "en-US"},
        {"ShortName": "en-US-AriaNeural", "Gender": "Female", "Locale": "en-US"},
        {"ShortName": "en-US-DavisNeural", "Gender": "Male", "Locale": "en-US"},
        {"ShortName": "en-GB-RyanNeural", "Gender": "Male", "Locale": "en-GB"},
        {"ShortName": "en-GB-SoniaNeural", "Gender": "Female", "Locale": "en-GB"},
    ],
    "tr": [
        {"ShortName": "tr-TR-AhmetNeural", "Gender": "Male", "Locale": "tr-TR"},
        {"ShortName": "tr-TR-EmelNeural", "Gender": "Female", "Locale": "tr-TR"},
    ],
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
    if any(name in lower_voice for name in ["shakir", "guy", "ahmet", "hamed", "davis", "ryan", "male"]):
        return "male"
    if any(name in lower_voice for name in ["salma", "jenny", "emel", "zariyah", "sonia", "aria", "female"]):
        return "female"
    return "unknown"


def _build_edge_voice_object(short_name: str, gender: str, locale: str, language: str) -> dict:
    spoken = {"ar": "Arabic", "en": "English", "tr": "Turkish"}.get(language, language.upper())
    region = locale.split("-", 1)[1] if "-" in locale else locale
    friendly_name = short_name.replace(f"{locale}-", "").replace("Neural", "")
    return {
        "provider": "edge_tts",
        "language": language,
        "name": short_name,
        "display_name": f"{friendly_name} - {spoken} {region} - {gender}",
        "gender": gender,
        "locale": locale,
    }


async def get_edge_voice_catalog() -> tuple[dict, bool]:
    languages = {"ar": [], "en": [], "tr": []}
    fallback_used = False
    try:
        import edge_tts

        raw = await edge_tts.list_voices()
        filtered = []
        for voice in raw:
            locale = (voice.get("Locale") or "").strip()
            short_name = (voice.get("ShortName") or "").strip()
            gender = (voice.get("Gender") or "Unknown").strip().title()
            if not locale or not short_name:
                continue
            if locale.startswith("ar-"):
                lang = "ar"
            elif locale.startswith("en-"):
                lang = "en"
            elif locale.startswith("tr-"):
                lang = "tr"
            else:
                continue
            filtered.append((lang, locale, gender, short_name))

        filtered.sort(key=lambda v: (v[0], v[1], v[2], v[3]))
        for lang, locale, gender, short_name in filtered:
            languages[lang].append(_build_edge_voice_object(short_name, gender, locale, lang))

        if any(len(v) == 0 for v in languages.values()):
            raise RuntimeError("Missing one or more language buckets from dynamic Edge voice list")
    except Exception as e:
        fallback_used = True
        logger.warning("edge_tts.list_voices failed, using static fallback list error=%s", str(e), exc_info=True)
        for lang, items in EDGE_STATIC_SAFE_LIST.items():
            for voice in items:
                languages[lang].append(_build_edge_voice_object(voice["ShortName"], voice["Gender"], voice["Locale"], lang))

    return languages, fallback_used


def _flatten_voice_catalog(catalog: dict) -> dict:
    flattened = {}
    for lang, voices in catalog.items():
        for voice in voices:
            flattened[voice["name"]] = voice
    return flattened


async def validate_edge_voice(selected_voice: str) -> dict | None:
    catalog, _ = await get_edge_voice_catalog()
    return _flatten_voice_catalog(catalog).get((selected_voice or "").strip())


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


async def resolve_voice_for_project(language: str | None, selected_voice: str | None, user_selected: bool = False) -> tuple[str, str, dict | None, bool]:
    lang = _normalize_lang(language)
    candidate = (selected_voice or "").strip()
    if not candidate:
        default_voice = _select_edge_tts_voice(language)
        info = await validate_edge_voice(default_voice)
        return default_voice, "language_default", info, False

    matched = await validate_edge_voice(candidate)
    if not matched:
        raise ValueError("INVALID_TTS_VOICE")

    mismatch = matched["language"] != lang and lang in {"ar", "en", "tr"}
    return candidate, "user_selected", matched, mismatch


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

    selected_voice = voice_id
    provider = (provider_override or settings.TTS_PROVIDER or "edge_tts").strip().lower()
    filename = hashlib.md5(f"{selected_voice}_{speed}_{text[:100]}".encode()).hexdigest() + ".mp3"
    output_path = os.path.join(out_dir, filename)

    if os.path.exists(output_path) and _valid_audio_file(output_path):
        return output_path

    if provider == "edge_tts":
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text=text, voice=selected_voice, rate=f"{int((speed - 1.0) * 100):+d}%")
            await communicate.save(output_path)
            if _valid_audio_file(output_path):
                return output_path
            raise RuntimeError("edge_tts output failed validation")
        except Exception as e:
            message = str(e).lower()
            if "403" in message:
                if settings.TTS_FALLBACK_ENABLED and (settings.TTS_FALLBACK_PROVIDER or "").strip().lower() == "gtts":
                    _generate_with_gtts(text=text, language=language, output_path=output_path)
                    return output_path
                raise RuntimeError("EDGE_TTS_FORBIDDEN") from e
            if settings.TTS_FALLBACK_ENABLED and (settings.TTS_FALLBACK_PROVIDER or "").strip().lower() == "gtts":
                _generate_with_gtts(text=text, language=language, output_path=output_path)
                return output_path
            raise RuntimeError(f"Edge TTS failed: {e}") from e

    if provider == "gtts":
        _generate_with_gtts(text=text, language=language, output_path=output_path)
        return output_path

    raise RuntimeError(f"Unsupported TTS_PROVIDER '{provider}'. Allowed: edge_tts, gtts")
