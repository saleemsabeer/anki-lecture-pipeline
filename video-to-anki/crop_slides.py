import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SLIDES = Path(sys.argv[1])
MAX_T = float(sys.argv[2]) if len(sys.argv) > 2 else float("inf")  # lesson end; later frames are the next lesson
slides = [s for s in json.loads((SLIDES / "slides.json").read_text()) if s["rep"] <= MAX_T]
frames = [np.asarray(Image.open(SLIDES / "full" / s["file"]).convert("L"), dtype=np.float32) for s in slides]
stack = np.stack(frames)
print(f"frames: {stack.shape}")

std = stack.std(axis=0)
mask = std > 20
rows = mask.sum(axis=1)
cols = mask.sum(axis=0)
r_idx = np.where(rows > 0.10 * rows.max())[0]
c_idx = np.where(cols > 0.10 * cols.max())[0]
top, bottom = int(r_idx.min()), int(r_idx.max()) + 1
left, right = int(c_idx.min()), int(c_idx.max()) + 1
w, h = right - left, bottom - top
print(f"player bbox: x={left}..{right} y={top}..{bottom}  ->  {w}x{h}  (aspect {w / h:.3f})")

if len(sys.argv) > 3:  # manual override: left,top,right,bottom (e.g. to cut off a player control bar)
    left, top, right, bottom = map(int, sys.argv[3].split(","))
    w, h = right - left, bottom - top
    print(f"override bbox: x={left}..{right} y={top}..{bottom} -> {w}x{h}")

OUT = SLIDES / "cropped"
OUT.mkdir(exist_ok=True)
for s in slides:
    im = Image.open(SLIDES / "full" / s["file"]).crop((left, top, right, bottom))
    s["cropped"] = f"slide_{s['n']:03d}.png"
    im.save(OUT / s["cropped"], optimize=True)
(SLIDES / "slides_cropped.json").write_text(json.dumps({"bbox": [left, top, right, bottom], "slides": slides}, indent=1))

COLS, TW = 2, 720
TH = round(TW * h / w)
PER = 6
for page in range(0, len(slides), PER):
    batch = slides[page:page + PER]
    nrows = (len(batch) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW, nrows * (TH + 28)), "white")
    draw = ImageDraw.Draw(sheet)
    for k, s in enumerate(batch):
        im = Image.open(OUT / s["cropped"]).resize((TW, TH), Image.LANCZOS)
        x, y = (k % COLS) * TW, (k // COLS) * (TH + 28)
        sheet.paste(im, (x, y + 28))
        m, sec = divmod(s["rep"], 60)
        draw.text((x + 6, y + 8), f"#{s['n']}   t={m}:{sec:02d}   shown {s['start']}-{s['end']}s", fill="black")
    sheet.save(SLIDES / f"csheet_{page // PER + 1:02d}.png")
print("sheets:", sorted(p.name for p in SLIDES.glob("csheet_*.png")))
