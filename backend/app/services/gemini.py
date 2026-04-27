import json
import re
import google.generativeai as genai
from app.config import settings


def _get_model():
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-1.5-flash")


def _clean_json(text: str) -> str:
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return text.strip()


async def generate_ideas(niche: str, language: str, tone: str, count: int = 5) -> list[dict]:
    model = _get_model()
    prompt = f"""Generate {count} unique YouTube video ideas for a {niche} channel.
Language: {language}, Tone: {tone}
Return JSON array with objects: {{title, angle, video_type (story/explainer/listicle/quote), hook}}
Only return valid JSON, no extra text."""
    response = model.generate_content(prompt)
    try:
        return json.loads(_clean_json(response.text))
    except Exception:
        return [{"title": f"Idea {i+1}", "angle": "General", "video_type": "explainer", "hook": ""} for i in range(count)]


async def generate_script(
    idea: str,
    video_type: str,
    language: str,
    tone: str,
    niche: str,
    channel_name: str,
    is_islamic: bool = False,
) -> dict:
    islamic_note = """
IMPORTANT Islamic Content Rules:
- Never depict faces of Prophets or Companions
- All claims must be sourced (Quran surah:ayah or Hadith book:number)
- Use authentic sources only (Quran, Bukhari, Muslim, Abu Dawud, Tirmidhi)
- Include sharia_reference field
""" if is_islamic else ""

    model = _get_model()
    prompt = f"""Create a complete YouTube {video_type} video script.
Channel: {channel_name} | Niche: {niche} | Language: {language} | Tone: {tone}
Topic: {idea}
{islamic_note}
Return JSON with:
{{
  "title": "SEO optimized title",
  "description": "YouTube description with hashtags",
  "pinned_comment": "Engagement comment",
  "thumbnail_prompt": "Stable Diffusion prompt for thumbnail",
  "tags": ["tag1", "tag2"],
  "sharia_reference": "source if islamic else null",
  "trust_level": "verified/probable/weak if islamic else null",
  "scenes": [
    {{
      "order": 1,
      "script_text": "narration text",
      "script_ar": "arabic translation if non-arabic else null",
      "duration": 6,
      "visual_query": "stock footage search query",
      "visual_type": "stock",
      "transition": "fade",
      "effects": ["zoom_in"]
    }}
  ]
}}
Include 8-15 scenes. Only return valid JSON."""
    response = model.generate_content(prompt)
    try:
        return json.loads(_clean_json(response.text))
    except Exception:
        return {
            "title": idea,
            "description": f"Video about {idea}",
            "pinned_comment": "What do you think?",
            "thumbnail_prompt": f"cinematic {idea}",
            "tags": [niche],
            "sharia_reference": None,
            "trust_level": None,
            "scenes": [{"order": 1, "script_text": idea, "duration": 10, "visual_query": idea, "visual_type": "stock", "transition": "fade", "effects": []}],
        }


async def check_duplicate(idea: str, existing_titles: list[str]) -> dict:
    if not existing_titles:
        return {"is_duplicate": False, "similarity": 0.0, "suggested_angle": None}
    model = _get_model()
    titles_str = "\n".join(f"- {t}" for t in existing_titles[:50])
    prompt = f"""Check if this idea is too similar to existing videos.
New idea: "{idea}"
Existing videos:
{titles_str}
Return JSON: {{is_duplicate: bool, similarity: 0-100, most_similar_title: str or null, suggested_angle: str or null}}
Only return valid JSON."""
    response = model.generate_content(prompt)
    try:
        data = json.loads(_clean_json(response.text))
        data["similarity"] = data.get("similarity", 0) / 100
        return data
    except Exception:
        return {"is_duplicate": False, "similarity": 0.0, "suggested_angle": None}


async def suggest_alternative_angle(idea: str, niche: str) -> str:
    model = _get_model()
    response = model.generate_content(
        f"Suggest a unique angle for '{idea}' in {niche} niche. One sentence only."
    )
    return response.text.strip()
