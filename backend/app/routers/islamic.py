from fastapi import APIRouter, Query
from app.services.quran_api import get_verse, get_chapter, search_verses, get_daily_verse
from app.services.sunnah_api import get_hadith, get_random_hadith, COLLECTIONS

router = APIRouter(prefix="/islamic", tags=["islamic"])


@router.get("/quran/verse/{surah}/{ayah}")
async def quran_verse(surah: int, ayah: int, lang: str = Query("en")):
    translation_map = {"en": 131, "tr": 77, "ar": 0}
    return await get_verse(surah, ayah, translation_map.get(lang, 131))


@router.get("/quran/chapter/{surah}")
async def quran_chapter(surah: int):
    return await get_chapter(surah)


@router.get("/quran/search")
async def quran_search(q: str = Query(...), size: int = Query(10)):
    return await search_verses(q, size)


@router.get("/quran/daily")
async def daily_verse(lang: str = Query("en")):
    translation_map = {"en": 131, "tr": 77}
    return await get_daily_verse(translation_map.get(lang, 131))


@router.get("/hadith/collections")
async def hadith_collections():
    return COLLECTIONS


@router.get("/hadith/{collection}/{book}/{number}")
async def hadith(collection: str, book: int, number: int):
    return await get_hadith(collection, book, number)


@router.get("/hadith/random/{collection}")
async def random_hadith(collection: str = "bukhari"):
    return await get_random_hadith(collection)


ISLAMIC_CONTENT_TYPES = [
    {"id": "verse_of_day", "label": "Verse of the Day + Tafsir", "label_ar": "آية اليوم وتفسيرها"},
    {"id": "hadith_of_day", "label": "Hadith of the Day + Explanation", "label_ar": "حديث اليوم وشرحه"},
    {"id": "prophet_story", "label": "Stories of Prophets", "label_ar": "قصص الأنبياء"},
    {"id": "companion_story", "label": "Stories of Companions", "label_ar": "قصص الصحابة"},
    {"id": "seerah", "label": "Prophetic Biography", "label_ar": "السيرة النبوية"},
    {"id": "asma_husna", "label": "Names of Allah", "label_ar": "أسماء الله الحسنى"},
    {"id": "surah_virtues", "label": "Virtues of Surahs", "label_ar": "فضائل السور"},
    {"id": "adhkar_morning", "label": "Morning Adhkar", "label_ar": "أذكار الصباح"},
    {"id": "adhkar_evening", "label": "Evening Adhkar", "label_ar": "أذكار المساء"},
    {"id": "seasonal", "label": "Seasonal Content", "label_ar": "محتوى المناسبات"},
]


@router.get("/content-types")
async def islamic_content_types():
    return ISLAMIC_CONTENT_TYPES


ISLAMIC_BOOKS = [
    {"id": "quran", "title": "القرآن الكريم", "type": "quran"},
    {"id": "bukhari", "title": "صحيح البخاري", "type": "hadith", "hadith_count": 7563},
    {"id": "muslim", "title": "صحيح مسلم", "type": "hadith", "hadith_count": 7470},
    {"id": "prophets_stories", "title": "قصص الأنبياء - ابن كثير", "type": "book"},
    {"id": "sealed_nectar", "title": "الرحيق المختوم", "type": "book"},
    {"id": "riyad_salihin", "title": "رياض الصالحين", "type": "hadith"},
    {"id": "adhkar_nawawi", "title": "الأذكار للنووي", "type": "book"},
    {"id": "tafsir_ibn_kathir", "title": "تفسير ابن كثير", "type": "tafsir"},
    {"id": "tafsir_saadi", "title": "تفسير السعدي", "type": "tafsir"},
]


@router.get("/library")
async def islamic_library():
    return ISLAMIC_BOOKS
