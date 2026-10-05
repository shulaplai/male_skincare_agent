"""Generate the home-screen / favicon PNGs into `frontend/public/`.

Run from the repo root with the backend venv (it has Pillow):

    ./backend/.venv/bin/python frontend/scripts/generate_icons.py

Why a script instead of hand-drawn binaries: the icons must match the design tokens
(`--accent-deep` #b04e6d on `--bg` cream #faf3f0), and colours move when tokens move.
Regenerate after changing those, and keep the PNGs committed — `frontend/public/` is
served at the site root (Vite copies it verbatim; it is NOT part of the bundle).

Icon shape: full-bleed square (no rounding of our own — iOS masks the apple-touch-icon
itself, and Android masks `purpose: maskable`), droplet at ~52 % of the width so the
maskable safe zone (centre 80 %) can never clip it.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "public"
BG = (176, 78, 109)  # --accent-deep
BG_DARK = (143, 59, 87)  # --accent-ink, only for a subtle vertical gradient
FG = (250, 243, 240)  # --bg cream


def icon(size: int, pad_ratio: float = 0.21) -> Image.Image:
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)

    # Very subtle top-to-bottom shade so a flat square does not look like a bug.
    for y in range(size):
        t = y / max(size - 1, 1)
        d.line(
            [(0, y), (size, y)],
            fill=tuple(round(BG[i] + (BG_DARK[i] - BG[i]) * t) for i in range(3)),
        )

    cx = size / 2
    pad = size * pad_ratio
    body_top = size * 0.30
    body_bottom = size - pad
    r = (body_bottom - body_top) / 2
    cy = body_top + r

    # Droplet = circle + triangle apex above it (classic teardrop, reads at 48 px).
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FG)
    apex_y = size * 0.165
    d.polygon(
        [(cx, apex_y), (cx - r * 0.985, cy + r * 0.12), (cx + r * 0.985, cy + r * 0.12)],
        fill=FG,
    )

    # A cream-on-cream highlight would vanish, so the highlight is a *hole* punched in
    # the accent colour instead — keeps two colours only.
    hr = r * 0.30
    hx, hy = cx + r * 0.34, cy + r * 0.30
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(176, 78, 109))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        icon(size).save(OUT / f"icon-{size}.png")
    # iOS home-screen icon. Opaque and square: iOS applies its own mask + rounding.
    icon(180).save(OUT / "apple-touch-icon.png")
    icon(64).save(OUT / "favicon.png")
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
