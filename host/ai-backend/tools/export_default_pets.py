"""Rebuild preview and PNG resource set from the original SVGs, entirely offline."""
from pathlib import Path
import io
import json
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from velapet_backend.default_pets import PETS, SOURCE, SIZES, render_pet, pet_catalog


def main():
    output = SOURCE.parents[1] / "generated" / "default-pets"
    output.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (900, 330), "#F4F5FB")
    draw = ImageDraw.Draw(sheet)
    for i, pid in enumerate(PETS):
        target = output / pid
        target.mkdir(exist_ok=True)
        for kind in SIZES:
            (target / (kind + ".png")).write_bytes(render_pet(pid, kind))
        with Image.open(io.BytesIO(render_pet(pid, "home"))) as image:
            sheet.paste(image, (i * 300 + 30, 20), image)
        draw.text((i * 300 + 80, 280), pid, fill="#413A68")
    sheet.save(output / "preview.png")
    (output / "manifest.json").write_text(json.dumps({"default_pet_id": "nova-cat", "pets": pet_catalog()},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(output / "preview.png")


if __name__ == "__main__":
    main()
