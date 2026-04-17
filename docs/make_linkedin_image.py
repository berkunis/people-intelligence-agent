"""Generate a LinkedIn-ready project image (1200x627 PNG).

Run:
  uv run --with pillow python docs/make_linkedin_image.py

Outputs:
  docs/linkedin_cover.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "linkedin_cover.png"
W, H = 1200, 627

# System fonts (macOS)
FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"
FONT_MONO = "/System/Library/Fonts/Menlo.ttc"


def _load(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _gradient_bg(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        base.putpixel((0, y), (r, g, b))
    return base.resize((w, h))


def _rounded_badge(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    text_color: tuple = (255, 255, 255),
    pad: tuple[int, int] = (16, 8),
    radius: int = 12,
) -> tuple[int, int]:
    x, y = xy
    tw = draw.textlength(text, font=font)
    ascent, descent = font.getmetrics()
    th = ascent + descent
    w = int(tw + pad[0] * 2)
    h = int(th + pad[1] * 2)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
    draw.text((x + pad[0], y + pad[1] - 2), text, font=font, fill=text_color)
    return (w, h)


def make() -> Path:
    # Background gradient — dark navy to deep purple
    bg = _gradient_bg((W, H), top=(13, 17, 35), bottom=(37, 20, 68))

    # Soft radial glow at top-left
    glow = Image.new("RGB", (W, H), (13, 17, 35))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -240, 700, 480], fill=(79, 70, 229))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=180))
    bg = Image.blend(bg, glow, 0.35)

    # Accent glow bottom-right
    glow2 = Image.new("RGB", (W, H), (13, 17, 35))
    g2 = ImageDraw.Draw(glow2)
    g2.ellipse([700, 300, 1500, 900], fill=(16, 185, 129))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(radius=180))
    bg = Image.blend(bg, glow2, 0.20)

    img = bg.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Fonts
    f_kicker = _load(FONT_BOLD, 22)
    f_title = _load(FONT_BOLD, 64)
    f_tagline = _load(FONT_BOLD, 28)
    f_badge = _load(FONT_BOLD, 18)
    f_stat_label = _load(FONT_BOLD, 18)
    f_stat_value = _load(FONT_BOLD, 36)
    f_url = _load(FONT_MONO, 22)
    f_author = _load(FONT_BOLD, 20)

    PAD_X = 72
    y = 78

    # Kicker (subtle top label)
    draw.text(
        (PAD_X, y),
        "REFERENCE IMPLEMENTATION · STAFF AI ENGINEER PORTFOLIO",
        font=f_kicker,
        fill=(167, 139, 250),
    )
    y += 44

    # Title
    draw.text((PAD_X, y), "people-intelligence-agent", font=f_title, fill=(255, 255, 255))
    y += 82

    # Tagline (two lines)
    draw.text(
        (PAD_X, y),
        "A governable AI agent over People data.",
        font=f_tagline,
        fill=(226, 232, 240),
    )
    y += 40
    draw.text(
        (PAD_X, y),
        "Natural-language in · cited answers out · every call observable.",
        font=f_tagline,
        fill=(148, 163, 184),
    )
    y += 72

    # Tech badges row
    badges = [
        ("Python 3.11+", (55, 65, 81)),
        ("Claude Haiku 4.5", (217, 119, 87)),
        ("Gemini 2.0", (66, 133, 244)),
        ("DuckDB", (255, 210, 0)),
        ("BigQuery", (102, 157, 246)),
        ("Grafana", (244, 104, 0)),
        ("Prometheus", (229, 62, 62)),
    ]
    bx = PAD_X
    for text, color in badges:
        # Choose text color for contrast
        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        tc = (0, 0, 0) if luminance > 170 else (255, 255, 255)
        bw, bh = _rounded_badge(
            draw, (bx, y), text, f_badge, fill=color, text_color=tc, pad=(14, 6), radius=10
        )
        bx += bw + 10

    y += 68

    # Stat cards row
    stats = [
        ("Evals", "9 / 9", (16, 185, 129)),
        ("$ / query", "$0.004", (96, 165, 250)),
        ("Latency", "2.6s", (251, 191, 36)),
        ("Governance", "RBAC + k-anon", (244, 114, 182)),
    ]
    card_w = 248
    card_h = 112
    gap = 16
    total_w = card_w * len(stats) + gap * (len(stats) - 1)
    cx = (W - total_w) // 2
    cy = y + 8
    for label, value, accent in stats:
        # Card body
        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=14,
            fill=(24, 29, 54),
            outline=(59, 66, 101),
            width=1,
        )
        # Accent bar on left
        draw.rounded_rectangle([cx, cy, cx + 6, cy + card_h], radius=4, fill=accent)
        # Label
        draw.text((cx + 22, cy + 18), label.upper(), font=f_stat_label, fill=(148, 163, 184))
        # Value
        draw.text((cx + 22, cy + 46), value, font=f_stat_value, fill=(255, 255, 255))
        cx += card_w + gap

    # Footer: URL left, author right
    draw.line(
        [(PAD_X, H - 72), (W - PAD_X, H - 72)], fill=(59, 66, 101), width=1
    )
    draw.text(
        (PAD_X, H - 56),
        "github.com/berkunis/people-intelligence-agent",
        font=f_url,
        fill=(148, 163, 184),
    )
    author_text = "Dr. Isil Berkun · @berkunis"
    aw = draw.textlength(author_text, font=f_author)
    draw.text(
        (W - PAD_X - aw, H - 53),
        author_text,
        font=f_author,
        fill=(226, 232, 240),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    return OUT


if __name__ == "__main__":
    path = make()
    print(f"wrote {path}  ({path.stat().st_size / 1024:.1f} KB)")
