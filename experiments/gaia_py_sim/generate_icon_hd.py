from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "assets" / "gaia_icon.png"
TARGET = ROOT / "assets" / "gaia_icon_hd.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]

for favicon in (ROOT / "favicon.ico", ROOT / "assets" / "favicon.ico"):
    favicon.unlink(missing_ok=True)

with Image.open(SOURCE) as image:
    image.convert("RGBA").save(TARGET, format="ICO", sizes=SIZES)

print(f"Created {TARGET} with sizes: {SIZES}")
