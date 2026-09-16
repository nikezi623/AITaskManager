"""Generate PWA icons for the ATM habit tracker.

Source artwork is the 1024x1024 PNG in the repo's photo/ folder -- NOT the .ico,
whose largest frame is only 256px and would have to be upscaled.

Icons are saved opaque (composited onto white): iOS renders any alpha in a
home-screen icon against black, which looks broken on light artwork.

Usage:  python tools/make_icons.py
"""

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# 180 is the only size iOS actually reads (apple-touch-icon).
# 192/512 feed the web manifest; 32 is the browser favicon.
SIZES = {"icon-180.png": 180, "icon-192.png": 192, "icon-512.png": 512, "favicon-32.png": 32}

SOURCE_CANDIDATES = [
    REPO / "photo" / "ganyu5201314.png",
    REPO.parent / "photo" / "ganyu5201314.png",
]

OUT_DIR = REPO / "docs" / "icons"


def find_source() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.exists():
            return path
    tried = "\n  ".join(str(p) for p in SOURCE_CANDIDATES)
    sys.exit(f"Source artwork not found. Tried:\n  {tried}")


def flatten(img: Image.Image) -> Image.Image:
    """Composite onto white so the saved PNG has no alpha channel."""
    if img.mode == "RGB":
        return img
    img = img.convert("RGBA")
    canvas = Image.new("RGB", img.size, (255, 255, 255))
    canvas.paste(img, mask=img.split()[3])
    return canvas


def main() -> None:
    source = find_source()
    print(f"Source: {source}")
    with Image.open(source) as raw:
        print(f"  {raw.width}x{raw.height} {raw.mode}")
        base = flatten(raw)
    if base.width < 512:
        print(f"  warning: source is only {base.width}px, 512 will be upscaled")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, size in SIZES.items():
        out = OUT_DIR / name
        base.resize((size, size), Image.LANCZOS).save(out, optimize=True)
        print(f"  wrote {out.relative_to(REPO)}  ({size}x{size})")

    # Sanity check: the manifest declares these, and an accidental alpha channel
    # is invisible until it shows up as a black square on the home screen.
    for name in SIZES:
        with Image.open(OUT_DIR / name) as check:
            assert check.mode == "RGB", f"{name} is {check.mode}, expected RGB"
    print("All icons opaque RGB.")


if __name__ == "__main__":
    main()
