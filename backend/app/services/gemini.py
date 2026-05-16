"""
Gemini AI service — script generation, idea suggestion, duplicate detection.
Uses gemini-2.5-flash. Includes exponential-backoff retry.
"""
import json
import re
import asyncio
import logging
from typing import Optional
import google.generativeai as genai
from app.config import settings

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-2.5-flash"
_MAX_RETRIES = 3


_GEMINI_CALL_TIMEOUT = 120  # seconds per Gemini call


def _get_model():
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured — set it as an environment variable on Railway")
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel(_MODEL_NAME)


def _clean_json(text: str) -> str:
    """Strip markdown code fences and whitespace."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return text.strip()


async def _generate(prompt: str, attempt: int = 0) -> str:
    """Call Gemini with retry on quota/server errors. Returns '' on final failure."""
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set — cannot call Gemini API")
        return ""
    try:
        logger.info(f"Gemini call attempt {attempt + 1}/{_MAX_RETRIES + 1} (prompt {len(prompt)} chars)")
        model = _get_model()
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt),
            timeout=_GEMINI_CALL_TIMEOUT,
        )
        text = response.text
        logger.info(f"Gemini responded with {len(text)} chars")
        return text
    except asyncio.TimeoutError:
        logger.error(f"Gemini call timed out after {_GEMINI_CALL_TIMEOUT}s")
        return ""
    except Exception as e:
        err = str(e)
        if attempt < _MAX_RETRIES and ("429" in err or "500" in err or "503" in err):
            wait = 2 ** attempt
            logger.warning(f"Gemini retryable error (attempt {attempt + 1}): {err[:120]} — retrying in {wait}s")
            await asyncio.sleep(wait)
            return await _generate(prompt, attempt + 1)
        logger.error(f"Gemini failed (attempt {attempt + 1}): {e}")
        return ""


# ---------------------------------------------------------------------------
# Idea generation
# ---------------------------------------------------------------------------

async def generate_ideas(niche: str, language: str, tone: str, count: int = 5) -> list[dict]:
    prompt = f"""You are a YouTube content strategist for a {niche} channel.
Language of channel: {language}. Script tone: {tone}.

Generate exactly {count} unique, high-performing YouTube video ideas.

Return a JSON array (no extra text) where each object has:
- "title": catchy, SEO-optimized video title in {language}
- "angle": unique perspective that makes this video stand out (1 sentence)
- "video_type": one of [story, explainer, listicle, quote, verse_tafsir, hadith, biography, mystery, comparison, countdown]
- "hook": first sentence to open the video (attention-grabbing)

Only return valid JSON array."""

    text = await _generate(prompt)
    try:
        ideas = json.loads(_clean_json(text))
        if isinstance(ideas, list):
            return ideas[:count]
    except json.JSONDecodeError:
        logger.warning("Gemini ideas response was not valid JSON")
    return [
        {"title": f"Video Idea {i+1}", "angle": "General angle", "video_type": "explainer", "hook": "Did you know..."}
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

_ISLAMIC_RULES = """
CRITICAL ISLAMIC CONTENT RULES:
1. Every factual claim MUST cite its source (Quran surah:ayah or Hadith collection:book:number)
2. Use ONLY authentic sources: Quran, Sahih Bukhari, Sahih Muslim, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah
3. NEVER depict faces of Prophets, Companions, or Angels — use silhouette/nature/architecture instead
4. Identify trust level: "verified" (Quran/Mutawatir), "probable" (Sahih hadith), "weak" (Da'if — must flag)
5. For stories: describe settings, not faces. Use "a man" / "the Prophet ﷺ" without physical description
6. Include sharia_reference field with exact citation
"""

_NICHE_VISUAL_NOTES = {
    "curiobuzz": "Prefer aerial shots, world maps, strange landscapes, time-lapses",
    "islamic": "Mosques, calligraphy, natural light, geometry, Mecca/Medina, stars",
    "finance": "Charts, city skylines, gold/money, clean corporate visuals",
    "history": "Old maps, historical illustrations, architecture ruins",
    "science": "Lab equipment, space, nature macro shots, data visualizations",
    "motivation": "Nature, people succeeding, sunrise, mountains, running",
}


async def generate_script(
    idea: str,
    video_type: str,
    language: str,
    tone: str,
    niche: str,
    channel_name: str,
    is_islamic: bool = False,
    duration_minutes: int = 8,
) -> dict:
    visual_note = _NICHE_VISUAL_NOTES.get(niche, "Relevant stock footage")
    islamic_section = _ISLAMIC_RULES if is_islamic else ""
    ar_translation_note = (
        'Include "script_ar" (Arabic translation) for every scene if language is not Arabic.'
        if language in ("en", "tr") else ""
    )

    prompt = f"""You are a professional YouTube scriptwriter.
Channel: {channel_name} | Niche: {niche} | Type: {video_type} | Language: {language} | Tone: {tone}
Video topic: {idea}
{islamic_section}

Create a complete, publish-ready YouTube {video_type} script.
{ar_translation_note}

Video type pacing rules:
- If video_type is "short_form": create a short-form script under 60 seconds total. Use dynamic scene count (usually 8-12), short scene durations (usually 3-6 seconds), and keep summed scene durations under 60 seconds.
- If video_type is "long_form": create a complete long-form script. Use as many scenes as needed based on topic complexity, narration length, and pacing. Do not limit the output to 15 scenes. Use longer scene durations (usually 8-20 seconds) and allow total duration to scale naturally from scene durations.
- For any other video_type: choose scene count and durations dynamically from narration and pacing.

Scene planning requirements:
- Decide scene count dynamically from: video_type, topic complexity, narration length, pacing.
- Every scene must have a unique visual_query that matches that exact scene (avoid repeating visual_query text).
- Do not force equal duration across scenes.

Return ONLY a valid JSON object with this exact structure:
{{
  "title": "SEO-optimized YouTube title (max 70 chars)",
  "description": "YouTube video description (150-300 words) with relevant hashtags",
  "pinned_comment": "Engaging pinned comment to boost interaction",
  "thumbnail_prompt": "Stable Diffusion prompt for thumbnail image (cinematic, high detail)",
  "tags": ["tag1", "tag2", ...],
  "sharia_reference": "Full citation if Islamic, else null",
  "trust_level": "verified|probable|weak if Islamic, else null",
  "scenes": [
    {{
      "order": 1,
      "script_text": "Narration text for this scene in {language}",
      "script_ar": "Arabic translation (or null if already Arabic)",
      "duration": 8,
      "visual_query": "Specific Pexels/Pixabay search query for this scene",
      "visual_type": "stock|wikimedia|ai|text_motion",
      "transition": "fade|zoom_in|zoom_out|slide_left|slide_right",
      "effects": ["ken_burns", "zoom"],
      "on_screen_source": "Citation shown on screen (for Islamic content)"
    }}
  ]
}}

Scenes must: start with a hook, build narrative, include CTA near end, end with outro.
Visual queries must be specific (e.g. "ancient mosque aerial view sunset" not just "mosque") and unique per scene.
Visual note for this niche: {visual_note}"""

    logger.info(f"generate_script: idea={idea!r:.60} type={video_type} lang={language} niche={niche} islamic={is_islamic}")

    text = await _generate(prompt)

    if not text:
        logger.warning("generate_script: Gemini returned empty — using fallback script")
        return _fallback_script(idea, language, video_type)

    try:
        data = json.loads(_clean_json(text))
        if "scenes" in data and isinstance(data["scenes"], list):
            logger.info(f"generate_script: success — {len(data['scenes'])} scenes, title={data.get('title', '')!r:.60}")
            return data
        logger.warning(f"generate_script: Gemini JSON missing 'scenes' key — using fallback. Keys: {list(data.keys())}")
    except json.JSONDecodeError as exc:
        logger.warning(f"generate_script: Gemini response not valid JSON ({exc}) — using fallback. First 200 chars: {text[:200]!r}")

    return _fallback_script(idea, language, video_type)


def _fallback_script(idea: str, language: str, video_type: str = "explainer") -> dict:
    fallback_scene_count = 10 if video_type == "short_form" else 28 if video_type == "long_form" else 8
    fallback_scene_duration = 5 if video_type == "short_form" else 12 if video_type == "long_form" else 8
    return {
        "title": idea[:70],
        "description": f"Explore the fascinating topic of {idea}.",
        "pinned_comment": "What did you find most interesting? Comment below!",
        "thumbnail_prompt": f"cinematic thumbnail for '{idea}', dramatic lighting, 4K",
        "tags": ["youtube", "educational"],
        "sharia_reference": None,
        "trust_level": None,
        "scenes": [
            {
                "order": i + 1,
                "script_text": f"Scene {i+1} narration about {idea}.",
                "script_ar": None,
                "duration": fallback_scene_duration,
                "visual_query": f"{idea} scene {i+1} visual",
                "visual_type": "stock",
                "transition": "fade",
                "effects": [],
                "on_screen_source": None,
            }
            for i in range(fallback_scene_count)
        ],
    }


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

async def check_duplicate(idea: str, existing_titles: list[str]) -> dict:
    if not existing_titles:
        return {"is_duplicate": False, "similarity": 0.0, "most_similar_title": None, "suggested_angle": None}

    sample = existing_titles[:60]
    titles_block = "\n".join(f"- {t}" for t in sample)

    prompt = f"""Analyze if this new YouTube video idea is too similar to existing videos.

New idea: "{idea}"

Existing videos:
{titles_block}

Rules:
- "duplicate" means same topic + same angle (not just similar topic)
- Different angles on same topic = NOT duplicate

Return ONLY valid JSON:
{{
  "is_duplicate": true/false,
  "similarity": 0-100,
  "most_similar_title": "exact title from list or null",
  "suggested_angle": "one-sentence alternative angle if duplicate, else null"
}}"""

    text = await _generate(prompt)
    try:
        data = json.loads(_clean_json(text))
        data["similarity"] = float(data.get("similarity", 0)) / 100.0
        return data
    except Exception:
        return {"is_duplicate": False, "similarity": 0.0, "most_similar_title": None, "suggested_angle": None}


# ---------------------------------------------------------------------------
# Tafsir / explanation generation
# ---------------------------------------------------------------------------

async def generate_tafsir(surah: int, ayah: int, arabic_text: str, language: str = "en") -> dict:
    prompt = f"""Provide a scholarly but accessible tafsir (explanation) of this Quranic verse.

Verse: Surah {surah}, Ayah {ayah}
Arabic: {arabic_text}
Output language: {language}

Return ONLY valid JSON:
{{
  "brief_meaning": "1-2 sentence translation/meaning",
  "context": "Historical/revelation context (2-3 sentences)",
  "lessons": ["lesson 1", "lesson 2", "lesson 3"],
  "tafsir_source": "Ibn Kathir / As-Sa'di (specify which you're drawing from)",
  "script_paragraph": "A 60-90 second narration paragraph suitable for YouTube"
}}"""

    text = await _generate(prompt)
    try:
        return json.loads(_clean_json(text))
    except Exception:
        return {"brief_meaning": "", "context": "", "lessons": [], "tafsir_source": "", "script_paragraph": ""}


# ---------------------------------------------------------------------------
# Hadith explanation
# ---------------------------------------------------------------------------

async def generate_hadith_explanation(arabic: str, english: str, reference: str, language: str = "en") -> dict:
    prompt = f"""Explain this hadith for a YouTube video audience.

Hadith: {english}
Reference: {reference}
Output language: {language}

Return ONLY valid JSON:
{{
  "brief_explanation": "Simple explanation of the hadith (2-3 sentences)",
  "context": "When and why this was said (2-3 sentences)",
  "practical_lessons": ["lesson 1", "lesson 2", "lesson 3"],
  "script_paragraph": "60-90 second narration for YouTube",
  "grade_explanation": "What the hadith grade means for this specific narration"
}}"""

    text = await _generate(prompt)
    try:
        return json.loads(_clean_json(text))
    except Exception:
        return {"brief_explanation": "", "context": "", "practical_lessons": [], "script_paragraph": "", "grade_explanation": ""}


# ---------------------------------------------------------------------------
# SEO optimization
# ---------------------------------------------------------------------------

async def optimize_metadata(title: str, description: str, niche: str, language: str) -> dict:
    prompt = f"""Optimize this YouTube video metadata for maximum reach and SEO.

Title: {title}
Description: {description}
Niche: {niche}
Language: {language}

Return ONLY valid JSON:
{{
  "optimized_title": "improved title (max 70 chars)",
  "optimized_description": "improved description with keywords",
  "tags": ["tag1", ...] (20-30 tags),
  "chapters": ["00:00 Intro", "01:30 Section 1", ...],
  "pinned_comment": "engagement-boosting comment"
}}"""

    text = await _generate(prompt)
    try:
        return json.loads(_clean_json(text))
    except Exception:
        return {"optimized_title": title, "optimized_description": description, "tags": [], "chapters": [], "pinned_comment": ""}
