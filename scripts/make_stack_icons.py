#!/usr/bin/env python3
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Literal, Optional

import requests
from PIL import Image, ImageDraw, ImageFont
import cairosvg


@dataclass(frozen=True)
class IconSpec:
    kind: Literal["simpleicons", "text"]
    slug: str
    filename: str
    icon_color: str  # hex without '#'
    bg_hex: str      # hex without '#'
    text: Optional[str] = None

    size: int = 256
    logo_px: int = 150  # bigger = closer to your screenshot


# These are tuned to match your screenshot as closely as possible.
# (Opaque circles, no chunky shadow, TS is text not the TS-square logo.)
ICONS = [
    IconSpec("simpleicons", "nextdotjs",  "nextjs.png",     "ffffff", "000000", logo_px=150),
    IconSpec("text",        "typescript", "typescript.png", "ffffff", "3178C6", text="TS", logo_px=150),
    IconSpec("simpleicons", "react",      "react.png",      "61DAFB", "111827", logo_px=165),  # darker circle, slightly larger logo
    IconSpec("simpleicons", "postgresql", "postgresql.png", "336791", "E2E8F0", logo_px=155),  # classic pg blue + light grey bg
    IconSpec("simpleicons", "supabase",   "supabase.png",   "3FCF8E", "475569", logo_px=160),  # mid grey bg like screenshot
]

OUT_DIR = "assets/stack"


# Styling knobs
SUPERSAMPLE = 2            # crisp circles/icons
ADD_SHADOW = False         # screenshot looks flat/clean
CIRCLE_SHADOW = (0, 0, 0, 40)
SHADOW_OFFSET = 5


def hex_to_rgba(hex_str: str, alpha: int = 255) -> tuple[int, int, int, int]:
    s = hex_str.strip().lstrip("#")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b, alpha)


def fetch_svg(slug: str, color: str) -> str:
    url = f"https://cdn.simpleicons.org/{slug}/{color}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text


def svg_to_png_bytes(svg: str, px: int) -> bytes:
    return cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=px,
        output_height=px,
    )


def make_text_icon(text: str, px: int, color_rgba: tuple[int, int, int, int]) -> Image.Image:
    """
    Render 'TS' as real text (matches screenshot better than Simple Icons TS-square).
    """
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # DejaVu is present on most Linux systems (Ubuntu etc.)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = int(px * 0.78)  # tuned to look like your screenshot
    font = ImageFont.truetype(font_path, font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    x = (px - tw) // 2
    y = (px - th) // 2 - int(px * 0.04)  # tiny optical centering tweak

    draw.text((x, y), text, font=font, fill=color_rgba)
    return img


def make_chip(
    icon_png: Image.Image,
    size: int,
    bg_rgba: tuple[int, int, int, int],
    *,
    add_shadow: bool = False,
    supersample: int = 2,
) -> Image.Image:
    """
    Create a circular chip background + centered icon.
    Built at higher res then downscaled for smooth edges.
    """
    S = max(1, supersample)
    big = size * S
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    r = big // 2
    cx = cy = r

    if add_shadow:
        draw.ellipse(
            (cx - r + SHADOW_OFFSET * S, cy - r + SHADOW_OFFSET * S, cx + r + SHADOW_OFFSET * S, cy + r + SHADOW_OFFSET * S),
            fill=CIRCLE_SHADOW,
        )

    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg_rgba)

    # Center icon
    x = cx - icon_png.width // 2
    y = cy - icon_png.height // 2
    canvas.alpha_composite(icon_png, (x, y))

    if S > 1:
        canvas = canvas.resize((size, size), resample=Image.LANCZOS)

    return canvas


def save_strip(images: list[Image.Image], out_path: str, gap: int = 18) -> None:
    h = max(img.height for img in images)
    w = sum(img.width for img in images) + gap * (len(images) - 1)
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    x = 0
    for img in images:
        y = (h - img.height) // 2
        strip.alpha_composite(img, (x, y))
        x += img.width + gap

    strip.save(out_path)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    chips: list[Image.Image] = []

    for spec in ICONS:
        bg = hex_to_rgba(spec.bg_hex, alpha=255)

        if spec.kind == "simpleicons":
            svg = fetch_svg(spec.slug, spec.icon_color)
            png_bytes = svg_to_png_bytes(svg, spec.logo_px * SUPERSAMPLE)
            icon = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

        elif spec.kind == "text":
            icon = make_text_icon(
                spec.text or "TS",
                spec.logo_px * SUPERSAMPLE,
                hex_to_rgba(spec.icon_color, 255),
            )

        else:
            raise ValueError(f"Unknown kind: {spec.kind}")

        chip = make_chip(
            icon,
            spec.size,
            bg,
            add_shadow=ADD_SHADOW,
            supersample=SUPERSAMPLE,
        )

        out_path = os.path.join(OUT_DIR, spec.filename)
        chip.save(out_path)
        chips.append(chip)
        print(f"✅ wrote {out_path}")

    strip_path = os.path.join(OUT_DIR, "stack-strip.png")
    save_strip(chips, strip_path)
    print(f"✅ wrote {strip_path}")


if __name__ == "__main__":
    main()
