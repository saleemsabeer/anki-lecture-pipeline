import json
import subprocess
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
SLIDES = Path(sys.argv[2])
times = [int(t) for t in sys.argv[3:]]

slides = json.loads((SLIDES / "slides.json").read_text())
n = max(s["n"] for s in slides)
for t in times:
    n += 1
    dst = SLIDES / "full" / f"slide_{n:03d}_t{t:04d}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(SRC), "-frames:v", "1", str(dst)],
                   check=True)
    slides.append({"start": t, "end": t, "rep": t, "n": n, "file": dst.name})
slides.sort(key=lambda s: s["rep"])
(SLIDES / "slides.json").write_text(json.dumps(slides, indent=1))
print("added:", times, "->", " ".join(f"#{s['n']}@{s['rep']}s" for s in slides))
