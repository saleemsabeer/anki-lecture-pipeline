#!/usr/bin/env python3
"""Build Anki decks from cards/*.yaml: renders Mermaid diagrams (mermaid-cli, Graphviz fallback), generates
offline TTS audio (macOS `say`), and emits dist/*.apkg with deterministic IDs so rebuilds update in place.

  python build.py [--deck <yaml-name-prefix>] [--no-audio] [--check] [--report --samples N]
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import genanki
import yaml

STUDY = Path(__file__).resolve().parent
CARDS, DIAGRAMS, MEDIA, DIST, CACHE = STUDY / "cards", STUDY / "diagrams", STUDY / "media", STUDY / "dist", STUDY / "build-cache"
VOICE = os.environ.get("ANKI_TTS_VOICE", "Samantha")
GUID_NS = os.environ.get("ANKI_GUID_NS", "yaml-deck-builder")  # note-GUID namespace: keep it constant per collection

CSS = """
.card { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 18px; line-height: 1.45;
        color: #1f2933; background: #fafafa; padding: 10px; text-align: center; }
.card.nightMode, .card.night_mode { color: #e6edf3; background: #14161a; }
.q { font-weight: 600; font-size: 1.05em; }
.a { text-align: left; display: inline-block; max-width: 760px; margin-top: 8px; }
.scenario .q { text-align: left; display: inline-block; max-width: 760px; background: rgba(99,102,241,0.12);
               border-left: 4px solid #6366f1; padding: 10px 14px; border-radius: 6px; font-weight: 500; }
.scenario .q::before { content: "scenario"; display: block; font-size: 0.8em; color: #6366f1; margin-bottom: 4px; }
.extra { font-size: 0.9em; color: #6b7280; margin-top: 12px; text-align: left; display: inline-block; max-width: 760px; }
.src { display: block; font-size: 0.78em; color: #9ca3af; margin-top: 10px; }
code, pre { font-family: Menlo, Consolas, "SF Mono", monospace; }
code { font-size: 0.92em; background: rgba(127,127,127,0.18); padding: 1px 5px; border-radius: 4px; }
pre { text-align: left; font-size: 0.88em; background: rgba(127,127,127,0.14); padding: 10px 12px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
img { max-width: 100%; height: auto; border-radius: 6px; margin-top: 12px; }
hr#answer { margin: 14px 0; border: 0; border-top: 1px solid rgba(127,127,127,0.4); }
.cloze { font-weight: bold; color: #2563eb; }
"""

FIELDS = ["Front", "Back", "Extra", "Diagram", "DiagramFront", "Audio", "AudioBack", "Source", "Tags"]
FRONT = '{{Audio}}<div class="q">{{Front}}</div>{{DiagramFront}}'
BACK = ('{{FrontSide}}<hr id="answer">{{AudioBack}}<div class="a">{{Back}}</div>{{Diagram}}'
        '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}<span class="src">{{Source}}</span>')
BACK_REV = ('{{AudioBack}}<div class="q">{{Back}}</div><hr id="answer">{{Audio}}<div class="a">{{Front}}</div>{{Diagram}}'
            '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}<span class="src">{{Source}}</span>')
CLOZE_FRONT = '{{Audio}}<div class="q">{{cloze:Text}}</div>{{DiagramFront}}'
CLOZE_BACK = ('{{AudioBack}}<div class="q">{{cloze:Text}}</div>{{Diagram}}'
              '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}<span class="src">{{Source}}</span>')


def stable_id(name):
    return int(hashlib.sha1(name.encode()).hexdigest()[:8], 16)


def model(name, templates, cloze=False):
    fields = ["Text" if cloze and f == "Front" else f for f in FIELDS if not (cloze and f == "Back")]
    return genanki.Model(stable_id("model:" + name), name, fields=[{"name": f} for f in fields], templates=templates,
                         css=CSS, model_type=genanki.Model.CLOZE if cloze else genanki.Model.FRONT_BACK)


MODELS = {
    "basic": model("YAML Deck Basic", [{"name": "Card 1", "qfmt": FRONT, "afmt": BACK}]),
    "basic_reversed": model("YAML Deck Basic (reversed)",
                            [{"name": "Card 1", "qfmt": FRONT, "afmt": BACK},
                             {"name": "Card 2", "qfmt": '{{AudioBack}}<div class="q">{{Back}}</div>', "afmt": BACK_REV}]),
    "cloze": model("YAML Deck Cloze", [{"name": "Cloze", "qfmt": CLOZE_FRONT, "afmt": CLOZE_BACK}], cloze=True),
    "scenario": model("YAML Deck Scenario",
                      [{"name": "Card 1", "qfmt": '<div class="scenario">' + FRONT + '</div>', "afmt": BACK}]),
}
TYPE_TO_MODEL = {"basic": "basic", "why": "basic", "command": "basic", "rego": "basic", "basic_reversed": "basic_reversed",
                 "cloze": "cloze", "scenario": "scenario"}


# ---------------------------------------------------------------- diagrams
def render_diagram(name):
    """Mermaid -> SVG via mermaid-cli (npx), Graphviz fallback for <name>.dot. Cached by source hash."""
    MEDIA.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    mmd, dot = DIAGRAMS / f"{name}.mmd", DIAGRAMS / f"{name}.dot"
    src = mmd if mmd.exists() else dot
    if not src.exists():
        raise FileNotFoundError(f"diagram source missing: {name}.mmd / .dot")
    out = MEDIA / f"ydb-{name}.svg"
    digest = hashlib.sha1(src.read_bytes()).hexdigest()[:12]
    stamp = CACHE / f"{name}.svg.hash"
    if out.exists() and stamp.exists() and stamp.read_text() == digest:
        return out
    if src.suffix == ".mmd":
        env = dict(os.environ, PUPPETEER_SKIP_DOWNLOAD="1", PUPPETEER_SKIP_CHROMIUM_DOWNLOAD="1")
        cmd = ["npx", "-y", "-p", "@mermaid-js/mermaid-cli", "mmdc", "-i", str(src), "-o", str(out),
               "-p", str(STUDY / "puppeteer.json"), "-t", "dark", "-b", "#0f1b2d"]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
        if r.returncode != 0 or not out.exists():
            if dot.exists() and shutil.which("dot"):
                subprocess.run(["dot", "-Tsvg", str(dot), "-o", str(out)], check=True)
            else:
                raise RuntimeError(f"mermaid-cli failed for {name}: {r.stderr[-400:]}")
    else:
        subprocess.run(["dot", "-Tsvg", str(dot), "-o", str(out)], check=True)
    stamp.write_text(digest)
    return out


# ---------------------------------------------------------------- audio
LITERAL = {"--": " dash dash ", "-": " dash ", "/": " slash ", ".": " dot ", "_": " underscore ", ":": " colon ",
           "|": " pipe ", "*": " star ", "<": " open angle ", ">": " close angle ", '"': " quote ", "=": " equals ",
           "#": " hash ", "[": " open bracket ", "]": " close bracket ", "{": " open brace ", "}": " close brace ",
           "(": " open paren ", ")": " close paren ", ",": " comma ", ";": " semicolon ", "@": " at ", "$": " dollar ",
           "%": " percent ", "&": " ampersand ", "~": " tilde ", "`": " backtick ", "\\": " backslash "}


def strip_html(s):
    s = re.sub(r"\{\{c\d+::(.*?)(::.*?)?\}\}", r"\1", s or "")
    s = re.sub(r"<br\s*/?>", ". ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def cloze_question(s):
    return strip_html(re.sub(r"\{\{c\d+::(.*?)(::.*?)?\}\}", " blank ", s or ""))


def literal(cmd):
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", cmd)  # split CamelCase identifiers
    out = words.replace("--", LITERAL["--"])
    for k, v in LITERAL.items():
        if k != "--":
            out = out.replace(k, v)
    return re.sub(r"\s+", " ", out).strip()


def speech_for(card, side):
    """Return the text to speak for a side, honouring the audio rules (None = no audio)."""
    mode = card.get("audio", "full")
    if mode == "none":
        return None
    if mode == "summary":
        return card.get("spoken_summary") if side == "front" else None
    if card["type"] == "cloze":
        return cloze_question(card["text"]) if side == "front" else strip_html(card["text"])
    text = strip_html(card["front"] if side == "front" else card["back"])
    if card["type"] == "command" and side == "back" and card.get("command"):
        text = f"[[rate 135]] {literal(card['command'])} [[rate 175]] — that is, {card.get('command_plain', '')}. {strip_html(card['back'])}"
    codes = re.findall(r"<code>(.*?)</code>", card["front"] if side == "front" else card["back"])
    if card["type"] != "command" and codes:
        text += " " + " ".join(f"[[rate 135]] {literal(html.unescape(c))} [[rate 175]]" for c in codes if len(c) < 80)
    return text


def tts(text):
    MEDIA.mkdir(exist_ok=True)
    digest = hashlib.sha1((VOICE + "|" + text).encode()).hexdigest()[:16]
    mp3 = MEDIA / f"ydb-audio-{digest}.mp3"
    if mp3.exists():
        return mp3
    aiff = CACHE / f"{digest}.aiff"
    # `say` writes AIFF (LEF32@22050 is rejected for .aiff); ffmpeg resamples to 22.05 kHz mono MP3.
    # Text goes in on stdin (-f -): passed as an argument, a card starting with "--" (e.g. "--force-with-lease vs
    # --force") is parsed by `say` as an option and the build aborts.
    subprocess.run(["say", "-v", VOICE, "-o", str(aiff), "-f", "-"], input=text, text=True, check=True, timeout=120)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "22050", "-ac", "1",
                    "-c:a", "libmp3lame", "-b:a", "64k", str(mp3)], check=True)
    aiff.unlink(missing_ok=True)
    return mp3


# ---------------------------------------------------------------- build
def load_decks(only=None):
    """Load cards/*.yaml. Card ids must be unique across ALL decks (they seed the note GUIDs), so the check runs
    over every file even when only a subset is built."""
    decks, owner = [], {}
    for f in sorted(CARDS.glob("*.yaml")):
        d = yaml.safe_load(f.read_text())
        d["file"] = f
        for c in d["cards"]:
            if c["id"] in owner:
                raise SystemExit(f"duplicate card id {c['id']!r} in {f.name} and {owner[c['id']]}")
            owner[c["id"]] = f.name
            bad = [t for t in c.get("tags", []) if not isinstance(t, str)]
            if bad:  # YAML turns an unquoted 4.10 into the float 4.1 -> wrong section tag; quote such tags
                raise SystemExit(f"card {c['id']!r} ({f.name}): quote numeric tags {bad}")
        if not only or f.name.startswith(only):
            decks.append(d)
    return decks


def build_deck(d, no_audio=False):
    deck = genanki.Deck(stable_id("deck:" + d["deck"]), d["deck"], description=d.get("description", ""))
    media, stats = set(), {"notes": 0, "cards": 0, "diagrams": 0, "audio": 0}
    for c in d["cards"]:
        mkey = TYPE_TO_MODEL[c["type"]]
        m = MODELS[mkey]
        tags = [t for t in (d.get("base_tag"), d.get("phase_tag")) if t] + ["type-" + c["type"]] + [str(t) for t in c.get("tags", [])]
        if c.get("confidence") == "low":
            tags.append("needs-review")
        diag = diag_front = ""
        for key, field in (("diagram", "diagram"), ("diagram_front", "diagram_front")):
            if c.get(key):
                p = render_diagram(c[key]); media.add(p)
                tag = f'<img src="{p.name}">'
                if key == "diagram": diag = tag
                else: diag_front = tag
        if diag or diag_front:
            tags.append("has-diagram"); stats["diagrams"] += 1
        audio = audio_back = ""
        if not no_audio:
            for side in ("front", "back"):
                text = speech_for(c, side)
                if text:
                    p = tts(text); media.add(p)
                    if side == "front": audio = f"[sound:{p.name}]"
                    else: audio_back = f"[sound:{p.name}]"
            if audio or audio_back:
                tags.append("has-audio"); stats["audio"] += 1
        tag_str = " ".join(sorted(set(tags)))
        if mkey == "cloze":
            fields = [c["text"], c.get("extra", ""), diag, diag_front, audio, audio_back, c["source"], tag_str]
        else:
            fields = [c["front"], c["back"], c.get("extra", ""), diag, diag_front, audio, audio_back, c["source"], tag_str]
        note = genanki.Note(model=m, fields=fields, tags=sorted(set(tags)), guid=genanki.guid_for(GUID_NS, c["id"]))
        deck.add_note(note); stats["notes"] += 1
        stats["cards"] += (2 if mkey == "basic_reversed" else len(set(re.findall(r"\{\{c(\d+)::", c["text"]))) if mkey == "cloze" else 1)
    return deck, media, stats


def check_checkpoints(decks):
    cp_file = STUDY / "checkpoints.yaml"  # optional: {checkpoint-id: text}; decks claim ids via `checkpoint_prefix`
    wanted = (yaml.safe_load(cp_file.read_text()) or {}) if cp_file.exists() else {}
    covered = {}
    for d in decks:
        for c in d["cards"]:
            for cp in c.get("checkpoints", []):
                covered.setdefault(cp, []).append(c["id"])
    prefixes = [d["checkpoint_prefix"] for d in decks if d.get("checkpoint_prefix")]
    relevant = [k for k in wanted if any(k.startswith(p) for p in prefixes)]
    missing = [k for k in relevant if k not in covered]
    unknown = sorted(k for k in covered if k not in wanted)
    if unknown:  # a typo in a card's checkpoints list would otherwise pass silently
        raise SystemExit(f"cards reference checkpoint ids not in checkpoints.yaml: {unknown}")
    return relevant, covered, missing


def check_criteria(decks):
    """A deck may declare `criteria: {ac-1: text, ...}` and `min_per_criterion: N` in its header; each criterion must
    then be tagged on at least N cards. Returns rows (deck, id, text, count, ok)."""
    rows = []
    for d in decks:
        need = int(d.get("min_per_criterion", 1))
        for cid, text in (d.get("criteria") or {}).items():
            n = sum(1 for c in d["cards"] if cid in [str(t) for t in c.get("tags", [])])
            rows.append((d["deck"], cid, text, n, n >= need))
    return rows


def report(apkg, samples=3):
    """Independent verification: open the .apkg's sqlite collection and count notes/cards/diagrams/audio per deck,
    then print the first `samples` notes of each deck (model name, question side, answer side)."""
    with zipfile.ZipFile(apkg) as z:
        db = "collection.anki21" if "collection.anki21" in z.namelist() else "collection.anki2"
        tmp = Path(tempfile.mkdtemp()); z.extract(db, tmp); media = json.loads(z.read("media"))
    con = sqlite3.connect(tmp / db)
    col = con.execute("select decks, models from col").fetchone()
    names = {int(k): v["name"] for k, v in json.loads(col[0]).items()}
    models = {int(k): v["name"] for k, v in json.loads(col[1]).items()}
    rows = con.execute("select n.id, n.mid, n.flds, n.tags, (select did from cards where nid=n.id limit 1) from notes n "
                       "order by n.id").fetchall()
    per = {}
    for nid, mid, flds, tags, did in rows:
        name = names.get(did, "?"); s = per.setdefault(name, {"notes": 0, "cards": 0, "diagram": 0, "audio": 0, "samples": []})
        s["notes"] += 1; s["cards"] += con.execute("select count(*) from cards where nid=?", (nid,)).fetchone()[0]
        s["diagram"] += "<img" in flds; s["audio"] += "[sound:" in flds
        if len(s["samples"]) < samples:
            f = flds.split("\x1f")
            s["samples"].append((models.get(mid, "?"), strip_html(f[0]), strip_html(f[1]) if len(f) > 8 else "(cloze)"))
    print(f"== {apkg.name}: media files {len(media)}")
    for name in sorted(per):
        s = per[name]
        print(f"  {name}: notes {s['notes']}, cards {s['cards']}, with diagram {s['diagram']}, with audio {s['audio']}")
        for model_name, q, a in s["samples"]:
            print(f"    - [{model_name.replace('YAML Deck ', '')}] Q: {q[:120]}")
            if a != "(cloze)":
                print(f"        A: {a[:120]}")
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", help="build only YAML files starting with this prefix, e.g. 02")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--check", action="store_true", help="checkpoint coverage only")
    ap.add_argument("--report", action="store_true", help="print sqlite-based stats and samples after building")
    ap.add_argument("--samples", type=int, default=0, help="print N sample cards per deck")
    a = ap.parse_args()
    decks = load_decks(a.deck)
    relevant, covered, missing = check_checkpoints(decks)
    print(f"checkpoints: {len(relevant) - len(missing)}/{len(relevant)} covered" + (f"; MISSING: {missing}" if missing else ""))
    crit = check_criteria(decks)
    if crit:
        print("criteria coverage (cards per criterion):")
        for _, cid, text, n, ok in crit:
            print(f"  {cid:6s} {n:3d} {'ok ' if ok else 'LOW'}  {text[:90]}")
    short = [cid for _, cid, _, _, ok in crit if not ok]
    if a.check:
        sys.exit(1 if (missing or short) else 0)
    DIST.mkdir(exist_ok=True)
    all_decks, all_media, outputs = [], set(), []
    for d in decks:
        deck, media, stats = build_deck(d, a.no_audio)
        slug = d.get("apkg") or re.sub(r"[^A-Za-z0-9]+", "-", d["deck"].split("::")[-1]).strip("-")
        out = DIST / (slug if slug.endswith(".apkg") else f"{slug}.apkg")
        pkg = genanki.Package(deck); pkg.media_files = sorted(str(p) for p in media); pkg.write_to_file(str(out))
        print(f"built {out.name}: notes {stats['notes']}, cards {stats['cards']}, with diagram {stats['diagrams']}, with audio {stats['audio']}")
        all_decks.append(deck); all_media |= media; outputs.append(out)
    if len(all_decks) > 1:
        combo = DIST / "all-decks.apkg"
        pkg = genanki.Package(all_decks); pkg.media_files = sorted(str(p) for p in all_media); pkg.write_to_file(str(combo))
        print(f"built {combo.name} (all decks)")
        outputs = [combo]  # the combined package contains every deck built in this run
    if a.report:
        for f in outputs:
            report(f, a.samples or 3)


if __name__ == "__main__":
    main()
