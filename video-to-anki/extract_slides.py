import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
BIG = int(sys.argv[3]) if len(sys.argv) > 3 else 32  # bits changed => new slide
SMALL = int(sys.argv[4]) if len(sys.argv) > 4 else 6  # bits changed => still same frame
MIN_SEG = 2  # seconds; shorter segments are transitions

OUT.mkdir(parents=True, exist_ok=True)
THUMBS = OUT / "thumbs"
THUMBS.mkdir(exist_ok=True)
FULL = OUT / "full"
FULL.mkdir(exist_ok=True)

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=width,height,r_frame_rate:format=duration",
     "-of", "json", str(SRC)],
    capture_output=True, text=True, check=True,
)
info = json.loads(probe.stdout)
w, h = info["streams"][0]["width"], info["streams"][0]["height"]
duration = float(info["format"]["duration"])
print(f"source: {w}x{h}, {info['streams'][0]['r_frame_rate']} fps, {duration:.1f}s")

if not any(THUMBS.glob("t*.png")):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(SRC),
         "-vf", "fps=1,scale=192:-1", str(THUMBS / "t%05d.png")],
        check=True,
    )
files = sorted(THUMBS.glob("t*.png"))
print(f"thumbnails: {len(files)}")


def dhash(path):
    g = Image.open(path).convert("L").resize((17, 16), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


hashes = [dhash(f) for f in files]
dists = [int(np.count_nonzero(hashes[i] != hashes[i - 1])) for i in range(1, len(hashes))]
hist = np.bincount(np.minimum(dists, 64), minlength=65)
print("consecutive-frame distance histogram (bits changed -> count):")
print(" ".join(f"{d}:{c}" for d, c in enumerate(hist) if c))

# segments: [start_idx, end_idx] inclusive, 0-based thumbnail index == second
segments = []
start = 0
for i, d in enumerate(dists, start=1):
    if d > BIG:
        segments.append((start, i - 1))
        start = i
segments.append((start, len(hashes) - 1))

chosen = []
for s, e in segments:
    if e - s + 1 < MIN_SEG:
        continue
    rep = e
    while rep > s and int(np.count_nonzero(hashes[rep] != hashes[rep - 1])) > SMALL:
        rep -= 1
    chosen.append({"start": s, "end": e, "rep": rep})

# merge near-duplicate representatives (same slide re-shown)
deduped = []
for c in chosen:
    dup = next((d for d in deduped if int(np.count_nonzero(hashes[c["rep"]] != hashes[d["rep"]])) <= SMALL), None)
    if dup:
        dup["also"] = dup.get("also", []) + [(c["start"], c["end"])]
    else:
        deduped.append(c)
print(f"segments: {len(segments)}, kept: {len(chosen)}, unique slides: {len(deduped)}")

for n, c in enumerate(deduped, start=1):
    c["n"] = n
    dst = FULL / f"slide_{n:03d}_t{c['rep']:04d}.png"
    c["file"] = dst.name
    if not dst.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(c["rep"]), "-i", str(SRC),
             "-frames:v", "1", str(dst)],
            check=True,
        )

(OUT / "slides.json").write_text(json.dumps(deduped, indent=1))

# contact sheets, 12 per sheet
COLS, TW = 3, 480
TH = round(TW * h / w)
for page in range(0, len(deduped), 12):
    batch = deduped[page:page + 12]
    rows = (len(batch) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TW, rows * (TH + 24)), "white")
    draw = ImageDraw.Draw(sheet)
    for k, c in enumerate(batch):
        im = Image.open(FULL / c["file"]).resize((TW, TH), Image.LANCZOS)
        x, y = (k % COLS) * TW, (k // COLS) * (TH + 24)
        sheet.paste(im, (x, y + 24))
        m, s = divmod(c["rep"], 60)
        draw.text((x + 4, y + 4), f"#{c['n']}  {m}:{s:02d}  ({c['start']}-{c['end']}s)", fill="black")
    sheet.save(OUT / f"sheet_{page // 12 + 1:02d}.png")
print("sheets:", sorted(p.name for p in OUT.glob("sheet_*.png")))
