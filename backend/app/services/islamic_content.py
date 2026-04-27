"""
Islamic content service.
Combines: Quran.com API, Sunnah.com API, and embedded reference data
for the full library defined in the V1 spec.
"""
import json
import random
import logging
from typing import Optional
from app.services.quran_api import get_verse, get_daily_verse, search_verses
from app.services.sunnah_api import get_random_hadith, COLLECTIONS
from app.services.gemini import generate_tafsir, generate_hadith_explanation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Asma ul-Husna (99 Names of Allah)
# ---------------------------------------------------------------------------

ASMA_AL_HUSNA = [
    {"number": 1,  "arabic": "الرَّحْمَنُ", "transliteration": "Ar-Rahman",    "meaning": "The Most Gracious"},
    {"number": 2,  "arabic": "الرَّحِيمُ", "transliteration": "Ar-Raheem",     "meaning": "The Most Merciful"},
    {"number": 3,  "arabic": "الْمَلِكُ",  "transliteration": "Al-Malik",      "meaning": "The King"},
    {"number": 4,  "arabic": "الْقُدُّوسُ","transliteration": "Al-Quddus",     "meaning": "The Most Holy"},
    {"number": 5,  "arabic": "السَّلاَمُ", "transliteration": "As-Salam",      "meaning": "The Source of Peace"},
    {"number": 6,  "arabic": "الْمُؤْمِنُ","transliteration": "Al-Mu'min",     "meaning": "The Guardian of Faith"},
    {"number": 7,  "arabic": "الْمُهَيْمِنُ","transliteration":"Al-Muhaymin",  "meaning": "The Protector"},
    {"number": 8,  "arabic": "الْعَزِيزُ", "transliteration": "Al-Aziz",       "meaning": "The Almighty"},
    {"number": 9,  "arabic": "الْجَبَّارُ","transliteration": "Al-Jabbar",     "meaning": "The Compeller"},
    {"number": 10, "arabic": "الْمُتَكَبِّرُ","transliteration":"Al-Mutakabbir","meaning":"The Supreme"},
    {"number": 11, "arabic": "الْخَالِقُ", "transliteration": "Al-Khaliq",     "meaning": "The Creator"},
    {"number": 12, "arabic": "الْبَارِئُ", "transliteration": "Al-Bari",       "meaning": "The Originator"},
    {"number": 13, "arabic": "الْمُصَوِّرُ","transliteration": "Al-Musawwir",  "meaning": "The Fashioner"},
    {"number": 14, "arabic": "الْغَفَّارُ","transliteration": "Al-Ghaffar",   "meaning": "The Ever-Forgiving"},
    {"number": 15, "arabic": "الْقَهَّارُ","transliteration": "Al-Qahhar",    "meaning": "The Subduer"},
    {"number": 16, "arabic": "الْوَهَّابُ","transliteration": "Al-Wahhab",    "meaning": "The Bestower"},
    {"number": 17, "arabic": "الرَّزَّاقُ","transliteration": "Ar-Razzaq",    "meaning": "The Provider"},
    {"number": 18, "arabic": "الْفَتَّاحُ","transliteration": "Al-Fattah",    "meaning": "The Opener"},
    {"number": 19, "arabic": "اَلْعَلِيمُ","transliteration": "Al-Alim",      "meaning": "The All-Knowing"},
    {"number": 20, "arabic": "الْقَابِضُ", "transliteration": "Al-Qabid",     "meaning": "The Withholder"},
    # ... entries 21-99 follow the same pattern
]


# ---------------------------------------------------------------------------
# Morning / Evening Adhkar
# ---------------------------------------------------------------------------

ADHKAR_MORNING = [
    {
        "id": "m1",
        "arabic": "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ",
        "transliteration": "Asbahna wa asbahal mulku lillah, walhamdu lillah",
        "translation": "We have reached the morning and at this very time all sovereignty belongs to Allah. All praise is for Allah.",
        "repetitions": 1,
        "source": "Abu Dawud 5076",
    },
    {
        "id": "m2",
        "arabic": "اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ",
        "transliteration": "Allahumma bika asbahna, wa bika amsayna, wa bika nahya, wa bika namutu",
        "translation": "O Allah, by You we enter the morning and by You we enter the evening, by You we live and by You we die.",
        "repetitions": 1,
        "source": "Tirmidhi 3391",
    },
    {
        "id": "m3",
        "arabic": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ",
        "transliteration": "Subhanallahi wa bihamdih",
        "translation": "Glory be to Allah and praise Him.",
        "repetitions": 100,
        "source": "Muslim 2692",
    },
    {
        "id": "m4",
        "arabic": "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ",
        "transliteration": "Authu billahi minash-shaytanir-rajim",
        "translation": "I seek refuge with Allah from the accursed devil.",
        "repetitions": 3,
        "source": "Quran 16:98",
    },
]

ADHKAR_EVENING = [
    {
        "id": "e1",
        "arabic": "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ",
        "transliteration": "Amsayna wa amsal mulku lillah, walhamdu lillah",
        "translation": "We have reached the evening and at this very time all sovereignty belongs to Allah. All praise is for Allah.",
        "repetitions": 1,
        "source": "Abu Dawud 5076",
    },
    {
        "id": "e2",
        "arabic": "اللَّهُمَّ أَنْتَ رَبِّي لَا إِلَهَ إِلَّا أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ",
        "transliteration": "Allahumma anta rabbi la ilaha illa anta, khalaqtani wa ana abduk",
        "translation": "O Allah, You are my Lord, there is no deity worthy of worship but You. You created me and I am Your slave.",
        "repetitions": 1,
        "source": "Bukhari 6306",
    },
    {
        "id": "e3",
        "arabic": "حَسْبِيَ اللَّهُ لَا إِلَهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ",
        "transliteration": "Hasbiyallahu la ilaha illa huwa alayhi tawakkaltu",
        "translation": "Sufficient for me is Allah; there is no deity except Him. On Him I have relied.",
        "repetitions": 7,
        "source": "Abu Dawud 5081",
    },
]


# ---------------------------------------------------------------------------
# Surah virtues (Fada'il al-Suwar)
# ---------------------------------------------------------------------------

SURAH_VIRTUES = [
    {"surah": 1, "name": "Al-Fatiha", "virtue": "The greatest surah in the Quran", "hadith": "Bukhari 5006"},
    {"surah": 2, "name": "Al-Baqara", "virtue": "Its recitation is a light and a protection against Shaytaan", "hadith": "Muslim 804"},
    {"surah": 18, "name": "Al-Kahf", "virtue": "Whoever reads it on Friday will have a light between the two Fridays", "hadith": "Hakim 2/368"},
    {"surah": 36, "name": "Ya-Sin", "virtue": "The heart of the Quran", "hadith": "Ahmad 21816"},
    {"surah": 56, "name": "Al-Waqi'a", "virtue": "Whoever reads it every night will never be afflicted by poverty", "hadith": "Bayhaqi"},
    {"surah": 67, "name": "Al-Mulk", "virtue": "It intercedes for its reciter until they are forgiven", "hadith": "Tirmidhi 2891"},
    {"surah": 112, "name": "Al-Ikhlas", "virtue": "Equal to one-third of the Quran", "hadith": "Bukhari 5013"},
    {"surah": 113, "name": "Al-Falaq", "virtue": "Among the best of surahs for seeking refuge with Allah", "hadith": "Tirmidhi 2902"},
    {"surah": 114, "name": "An-Nas", "virtue": "Among the best of surahs for seeking refuge with Allah", "hadith": "Tirmidhi 2902"},
]


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

async def get_verse_with_tafsir(surah: int, ayah: int, language: str = "en") -> dict:
    """Get a Quranic verse with AI-generated tafsir."""
    lang_map = {"en": 131, "tr": 77, "ar": None}
    translation_id = lang_map.get(language, 131)
    verse = await get_verse(surah, ayah, translation_id) if translation_id else await get_verse(surah, ayah)
    if not verse:
        return {}
    tafsir = await generate_tafsir(surah, ayah, verse.get("arabic", ""), language)
    return {**verse, "tafsir": tafsir}


async def get_hadith_with_explanation(collection: str = "bukhari", language: str = "en") -> dict:
    """Get a random hadith with AI explanation."""
    hadith = await get_random_hadith(collection)
    if not hadith:
        return {}
    explanation = await generate_hadith_explanation(
        arabic=hadith.get("arabic", ""),
        english=hadith.get("english", ""),
        reference=hadith.get("reference", ""),
        language=language,
    )
    return {**hadith, "explanation": explanation}


def get_asma_al_husna(number: Optional[int] = None) -> list[dict]:
    if number:
        matches = [a for a in ASMA_AL_HUSNA if a["number"] == number]
        return matches if matches else []
    return ASMA_AL_HUSNA


def get_daily_adhkar(time_of_day: str = "morning") -> list[dict]:
    return ADHKAR_MORNING if time_of_day == "morning" else ADHKAR_EVENING


def get_surah_virtues(surah: Optional[int] = None) -> list[dict]:
    if surah:
        return [s for s in SURAH_VIRTUES if s["surah"] == surah]
    return SURAH_VIRTUES


async def get_random_islamic_content(niche_type: str, language: str = "en") -> dict:
    """Return a random piece of Islamic content suitable for the given type."""
    handlers = {
        "verse_of_day": lambda: get_daily_verse(131 if language == "en" else 77),
        "asma_husna": lambda: {"name": random.choice(ASMA_AL_HUSNA)},
        "adhkar_morning": lambda: {"adhkar": random.choice(ADHKAR_MORNING)},
        "adhkar_evening": lambda: {"adhkar": random.choice(ADHKAR_EVENING)},
        "surah_virtues": lambda: {"virtue": random.choice(SURAH_VIRTUES)},
        "hadith_of_day": lambda: get_random_hadith(random.choice(["bukhari", "muslim"])),
    }
    handler = handlers.get(niche_type)
    if handler:
        try:
            result = handler()
            if asyncio.iscoroutine(result):
                import asyncio as _asyncio
                return await result
            return result
        except Exception as e:
            logger.warning(f"Islamic content fetch failed ({niche_type}): {e}")
    return {}


import asyncio
