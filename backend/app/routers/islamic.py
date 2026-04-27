from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.services.quran_api import get_verse, get_chapter, search_verses, get_daily_verse
from app.services.sunnah_api import get_hadith, get_random_hadith, COLLECTIONS
from app.services.islamic_content import (
    get_verse_with_tafsir,
    get_hadith_with_explanation,
    get_asma_al_husna,
    get_daily_adhkar,
    get_surah_virtues,
    SURAH_VIRTUES,
    ADHKAR_MORNING,
    ADHKAR_EVENING,
    ASMA_AL_HUSNA,
)

router = APIRouter(prefix="/islamic", tags=["islamic"])


# ---------------------------------------------------------------------------
# Quran
# ---------------------------------------------------------------------------

@router.get("/quran/verse/{surah}/{ayah}")
async def quran_verse(surah: int, ayah: int, lang: str = Query("en")):
    lang_map = {"en": 131, "tr": 77, "ar": None}
    tid = lang_map.get(lang, 131)
    result = await get_verse(surah, ayah, tid) if tid else await get_verse(surah, ayah)
    if not result:
        raise HTTPException(status_code=404, detail="Verse not found")
    return result


@router.get("/quran/verse-with-tafsir/{surah}/{ayah}")
async def quran_verse_tafsir(surah: int, ayah: int, lang: str = Query("en")):
    result = await get_verse_with_tafsir(surah, ayah, lang)
    if not result:
        raise HTTPException(status_code=404, detail="Verse not found")
    return result


@router.get("/quran/chapter/{surah}")
async def quran_chapter(surah: int):
    result = await get_chapter(surah)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result


@router.get("/quran/search")
async def quran_search(q: str = Query(..., min_length=2), size: int = Query(10, le=50)):
    return {"results": await search_verses(q, size)}


@router.get("/quran/daily")
async def daily_verse(lang: str = Query("en")):
    lang_map = {"en": 131, "tr": 77}
    tid = lang_map.get(lang, 131)
    return await get_daily_verse(tid)


# ---------------------------------------------------------------------------
# Hadith
# ---------------------------------------------------------------------------

@router.get("/hadith/collections")
async def hadith_collections():
    return COLLECTIONS


@router.get("/hadith/{collection}/{book}/{number}")
async def hadith(collection: str, book: int, number: int):
    result = await get_hadith(collection, book, number)
    if not result:
        raise HTTPException(status_code=404, detail="Hadith not found")
    return result


@router.get("/hadith/random/{collection}")
async def random_hadith(collection: str = "bukhari"):
    return await get_random_hadith(collection)


@router.get("/hadith/random-with-explanation/{collection}")
async def random_hadith_explained(collection: str = "bukhari", lang: str = Query("en")):
    return await get_hadith_with_explanation(collection, lang)


# ---------------------------------------------------------------------------
# Asma ul-Husna
# ---------------------------------------------------------------------------

@router.get("/asma-al-husna")
async def asma_al_husna(number: Optional[int] = Query(None)):
    return get_asma_al_husna(number)


# ---------------------------------------------------------------------------
# Adhkar
# ---------------------------------------------------------------------------

@router.get("/adhkar/morning")
async def morning_adhkar():
    return ADHKAR_MORNING


@router.get("/adhkar/evening")
async def evening_adhkar():
    return ADHKAR_EVENING


@router.get("/adhkar/{time}")
async def adhkar_by_time(time: str):
    if time not in ("morning", "evening"):
        raise HTTPException(status_code=400, detail="time must be 'morning' or 'evening'")
    return get_daily_adhkar(time)


# ---------------------------------------------------------------------------
# Surah Virtues
# ---------------------------------------------------------------------------

@router.get("/surah-virtues")
async def surah_virtues(surah: Optional[int] = Query(None)):
    return get_surah_virtues(surah)


# ---------------------------------------------------------------------------
# Library & content types
# ---------------------------------------------------------------------------

ISLAMIC_CONTENT_TYPES = [
    {"id": "verse_of_day",    "label": "Verse of the Day + Tafsir",  "label_ar": "آية اليوم وتفسيرها"},
    {"id": "hadith_of_day",   "label": "Hadith of the Day",          "label_ar": "حديث اليوم وشرحه"},
    {"id": "prophet_story",   "label": "Stories of the Prophets",    "label_ar": "قصص الأنبياء"},
    {"id": "companion_story", "label": "Stories of the Companions",  "label_ar": "قصص الصحابة"},
    {"id": "seerah",          "label": "Prophetic Biography",        "label_ar": "السيرة النبوية"},
    {"id": "asma_husna",      "label": "Names of Allah",             "label_ar": "أسماء الله الحسنى"},
    {"id": "surah_virtues",   "label": "Virtues of Surahs",          "label_ar": "فضائل السور"},
    {"id": "adhkar_morning",  "label": "Morning Adhkar",             "label_ar": "أذكار الصباح"},
    {"id": "adhkar_evening",  "label": "Evening Adhkar",             "label_ar": "أذكار المساء"},
    {"id": "seasonal",        "label": "Seasonal Content",           "label_ar": "محتوى المناسبات"},
]

ISLAMIC_BOOKS = [
    {"id": "quran",           "title": "القرآن الكريم",              "type": "quran",   "source": "online"},
    {"id": "bukhari",         "title": "صحيح البخاري",               "type": "hadith",  "hadith_count": 7563, "source": "api"},
    {"id": "muslim",          "title": "صحيح مسلم",                  "type": "hadith",  "hadith_count": 7470, "source": "api"},
    {"id": "abudawud",        "title": "سنن أبي داود",               "type": "hadith",  "hadith_count": 5274, "source": "api"},
    {"id": "tirmidhi",        "title": "جامع الترمذي",               "type": "hadith",  "hadith_count": 3956, "source": "api"},
    {"id": "nasai",           "title": "سنن النسائي",                "type": "hadith",  "hadith_count": 5761, "source": "api"},
    {"id": "ibnmajah",        "title": "سنن ابن ماجه",               "type": "hadith",  "hadith_count": 4341, "source": "api"},
    {"id": "riyadussalihin",  "title": "رياض الصالحين",              "type": "hadith",  "hadith_count": 1906, "source": "api"},
    {"id": "prophets_stories","title": "قصص الأنبياء - ابن كثير",   "type": "book",    "source": "embedded"},
    {"id": "sealed_nectar",   "title": "الرحيق المختوم",             "type": "book",    "source": "embedded"},
    {"id": "adhkar_nawawi",   "title": "الأذكار للنووي",             "type": "book",    "source": "embedded"},
    {"id": "tafsir_ibn_kathir","title": "تفسير ابن كثير",           "type": "tafsir",  "source": "ai_augmented"},
    {"id": "tafsir_saadi",    "title": "تفسير السعدي",              "type": "tafsir",  "source": "ai_augmented"},
]

IMAGE_SAFETY_RULES = {
    "forbidden": [
        "Faces of Prophets (peace be upon them)",
        "Faces of Companions (may Allah be pleased with them)",
        "Faces of Angels",
        "Any depiction implying a specific appearance for divine beings",
    ],
    "allowed": [
        "Silhouettes",
        "Hands and robes (no face)",
        "View from behind",
        "Symbolic representations (light, scales, etc.)",
        "Ordinary Muslims in historical clothing (no recognized faces)",
        "Nature: mountains, deserts, skies, oceans",
        "Architecture: mosques, minarets, Islamic geometric patterns",
        "Calligraphy: Quranic text, Arabic script",
        "Historical Islamic locations: Mecca, Medina, Jerusalem",
    ],
    "stable_diffusion_negative_prompt": "human face, portrait, person face, detailed face, realistic face, celebrity face",
}


@router.get("/content-types")
async def islamic_content_types():
    return ISLAMIC_CONTENT_TYPES


@router.get("/library")
async def islamic_library():
    return ISLAMIC_BOOKS


@router.get("/image-safety-rules")
async def image_safety_rules():
    return IMAGE_SAFETY_RULES
