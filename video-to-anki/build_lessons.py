#!/usr/bin/env python3
"""Build one or more lesson decks from lesson config modules, optionally writing a combined package.

  python build_lessons.py example_lesson other_lesson [--combined all.apkg] [--scratch build-cache]

Each module must expose a CFG dict (see example_lesson.py). Exit status is non-zero if any package references media
that is missing or packages media that no card uses.
"""
import argparse
import importlib
import sys
from pathlib import Path

import anki_builder as ab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modules", nargs="+", help="lesson config module names (importable from this directory)")
    ap.add_argument("--combined", help="also write one .apkg containing every deck built")
    ap.add_argument("--scratch", default=str(Path(__file__).resolve().parent / "build-cache"))
    a = ap.parse_args()
    scratch = Path(a.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    decks, media, ok = [], [], True
    for name in a.modules:
        mod = importlib.import_module(name)
        deck, med, report, _apkg = ab.build_lesson(mod.CFG, scratch)
        decks.append(deck)
        media.extend(med)
        ok = ok and not (report["missing"] or report["unused"])

    if a.combined:
        out = Path(a.combined)
        ab.write_combined(decks, media, out)
        report = ab.verify(out, scratch / "verify_combined")
        print(f"combined: {out} ({out.stat().st_size // 1024} KB)  notes: {report['notes']}  cards: {report['cards']}  "
              f"media: {report['media']}  missing: {report['missing'] or 'none'}")
        ok = ok and not report["missing"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
