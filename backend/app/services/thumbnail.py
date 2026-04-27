"""
Thumbnail generation service.
Primary: Stable Diffusion (local, via diffusers or A1111 API).
Fallback: PIL-based text-on-gradient thumbnail.
"""
import os
import hashlib
import logging
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from app.config import settings

logger = logging.getLogger(__name__)

THUMB_SIZE = (1280, 720)


async def generate_thumbnail(
    prompt: str,
    title: str,
    project_id: str,
    primary_color: str = "#0ea5e9",
    logo_path: Optional[str] = None,
    use_sd: bool = False,
) -> str:
    """
    Generate a YouTube thumbnail (1280×720).
    Tries Stable Diffusion if use_sd=True and available, else falls back to PIL.
    """
    out_dir = os.path.join(settings.OUTPUT_DIR, project_id)
    os.makedirs(out_dir, exist_ok=True)
    thumb_hash = hashlib.md5(f"{prompt}{title}".encode()).hexdigest()[:12]
    output_path = os.path.join(out_dir, f"thumbnail_{thumb_hash}.jpg")

    if os.path.exists(output_path):
        return output_path

    if use_sd:
        sd_path = await _generate_sd(prompt, output_path)
        if sd_path:
            img = Image.open(sd_path).resize(THUMB_SIZE)
            _add_title_overlay(img, title, primary_color)
            if logo_path and os.path.exists(logo_path):
                _add_logo(img, logo_path)
            img.save(output_path, "JPEG", quality=92)
            return output_path

    # PIL fallback
    img = _create_gradient_thumbnail(title, primary_color, prompt)
    if logo_path and os.path.exists(logo_path):
        _add_logo(img, logo_path)
    img.save(output_path, "JPEG", quality=92)
    return output_path


async def _generate_sd(prompt: str, output_path: str) -> Optional[str]:
    """Try Stable Diffusion — local diffusers or A1111 API."""
    # Try A1111 API (localhost:7860)
    try:
        import httpx
        payload = {
            "prompt": f"{prompt}, cinematic, 4k, professional photography, dramatic lighting",
            "negative_prompt": "text, watermark, logo, blurry, faces (if islamic)",
            "width": 1280,
            "height": 720,
            "steps": 20,
            "cfg_scale": 7,
            "sampler_name": "DPM++ 2M Karras",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post("http://localhost:7860/sdapi/v1/txt2img", json=payload)
            if r.status_code == 200:
                import base64
                img_data = base64.b64decode(r.json()["images"][0])
                with open(output_path, "wb") as f:
                    f.write(img_data)
                return output_path
    except Exception:
        pass

    # Try local diffusers
    try:
        from diffusers import StableDiffusionPipeline
        import torch
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        if torch.cuda.is_available():
            pipe = pipe.to("cuda")
        image = pipe(prompt, width=1280, height=720, num_inference_steps=20).images[0]
        image.save(output_path)
        return output_path
    except Exception:
        pass

    return None


def _create_gradient_thumbnail(title: str, primary_color: str, subtitle: str = "") -> Image.Image:
    """Create a professional gradient thumbnail with title text."""
    img = Image.new("RGB", THUMB_SIZE)
    draw = ImageDraw.Draw(img)

    r, g, b = _hex_to_rgb(primary_color)
    dark_r, dark_g, dark_b = max(0, r - 60), max(0, g - 60), max(0, b - 60)

    # Gradient background
    for y in range(THUMB_SIZE[1]):
        ratio = y / THUMB_SIZE[1]
        cr = int(dark_r + (r - dark_r) * ratio)
        cg = int(dark_g + (g - dark_g) * ratio)
        cb = int(dark_b + (b - dark_b) * ratio)
        draw.line([(0, y), (THUMB_SIZE[0], y)], fill=(cr, cg, cb))

    # Decorative accent bar
    bar_h = 8
    draw.rectangle([(0, 0), (THUMB_SIZE[0], bar_h)], fill=(255, 255, 255, 180))

    # Title text
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = font_large

    # Wrap title
    words = title.split()
    lines, line = [], []
    for word in words:
        line.append(word)
        if len(" ".join(line)) > 22:
            lines.append(" ".join(line[:-1]))
            line = [word]
    lines.append(" ".join(line))
    lines = lines[:3]

    y_start = THUMB_SIZE[1] // 2 - len(lines) * 80 // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_large)
        text_w = bbox[2] - bbox[0]
        x = (THUMB_SIZE[0] - text_w) // 2
        # Shadow
        draw.text((x + 3, y_start + i * 85 + 3), line, fill=(0, 0, 0, 160), font=font_large)
        draw.text((x, y_start + i * 85), line, fill=(255, 255, 255), font=font_large)

    return img


def _add_title_overlay(img: Image.Image, title: str, primary_color: str) -> None:
    """Add semi-transparent title bar at bottom of image."""
    draw = ImageDraw.Draw(img)
    bar_y = THUMB_SIZE[1] - 120
    draw.rectangle([(0, bar_y), (THUMB_SIZE[0], THUMB_SIZE[1])], fill=(0, 0, 0, 180))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except Exception:
        font = ImageFont.load_default()
    words = title[:50]
    bbox = draw.textbbox((0, 0), words, font=font)
    text_w = bbox[2] - bbox[0]
    x = (THUMB_SIZE[0] - text_w) // 2
    draw.text((x, bar_y + 30), words, fill=(255, 255, 255), font=font)


def _add_logo(img: Image.Image, logo_path: str, position: str = "top-right", size: int = 80) -> None:
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((size, size))
        lw, lh = logo.size
        pad = 20
        positions = {
            "top-right": (THUMB_SIZE[0] - lw - pad, pad),
            "top-left": (pad, pad),
            "bottom-right": (THUMB_SIZE[0] - lw - pad, THUMB_SIZE[1] - lh - pad),
            "bottom-left": (pad, THUMB_SIZE[1] - lh - pad),
        }
        pos = positions.get(position, positions["top-right"])
        img.paste(logo, pos, logo)
    except Exception as e:
        logger.warning(f"Could not add logo: {e}")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
