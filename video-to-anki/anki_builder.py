import json
import re
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import genanki
from PIL import Image

CSS = """
.card { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 20px; line-height: 1.4;
        text-align: center; color: #1f2933; background: #fafafa; padding: 8px; }
.card.nightMode, .card.night_mode { color: #e6e6e6; background: #1e1e1e; }
.q { font-weight: 600; }
.a { text-align: left; display: inline-block; max-width: 720px; }
.a ol, .a ul { margin: 8px 0 0 0; padding-left: 26px; }
.a li { margin: 4px 0; }
img { max-width: 100%; height: auto; border-radius: 6px; margin-top: 14px; }
code { font-family: Menlo, Consolas, monospace; font-size: 0.88em; background: rgba(127,127,127,0.18);
       padding: 1px 5px; border-radius: 4px; }
hr#answer { margin: 16px 0; border: 0; border-top: 1px solid rgba(127,127,127,0.4); }
.audio { margin-top: 10px; }
.extra { font-size: 15px; color: #6b7280; margin-top: 16px; text-align: left; display: inline-block; max-width: 720px; }
.extra .src { display: block; margin-top: 6px; font-size: 13px; color: #9ca3af; }
.cloze { font-weight: bold; color: #2563eb; }
"""


def make_models(qa_id, cloze_id):
    qa = genanki.Model(
        qa_id,
        "Lecture Q/A (image + audio)",
        fields=[{"name": "Question"}, {"name": "Answer"}, {"name": "QuestionImage"},
                {"name": "AnswerImage"}, {"name": "Audio"}, {"name": "Extra"}],
        templates=[{
            "name": "Card 1",
            "qfmt": '<div class="q">{{Question}}</div>{{#QuestionImage}}<div>{{QuestionImage}}</div>{{/QuestionImage}}',
            "afmt": '{{FrontSide}}<hr id="answer"><div class="a">{{Answer}}</div>'
                    '{{#AnswerImage}}<div>{{AnswerImage}}</div>{{/AnswerImage}}'
                    '{{#Audio}}<div class="audio">{{Audio}}</div>{{/Audio}}'
                    '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}',
        }],
        css=CSS,
    )
    cloze = genanki.Model(
        cloze_id,
        "Lecture Cloze (image + audio)",
        fields=[{"name": "Text"}, {"name": "Image"}, {"name": "Audio"}, {"name": "Extra"}],
        templates=[{
            "name": "Cloze",
            "qfmt": '<div class="q">{{cloze:Text}}</div>',
            "afmt": '<div class="q">{{cloze:Text}}</div>{{#Image}}<div>{{Image}}</div>{{/Image}}'
                    '{{#Audio}}<div class="audio">{{Audio}}</div>{{/Audio}}'
                    '{{#Extra}}<div class="extra">{{Extra}}</div>{{/Extra}}',
        }],
        css=CSS,
        model_type=genanki.Model.CLOZE,
    )
    return qa, cloze


def normalize(text, fixes):
    for pat, rep in fixes:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    return text


def _srt_seconds(ts):
    h, m, s = ts.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _truncate_after(text, phrases):
    low = text.lower()
    for p in phrases:
        i = low.find(p.lower())
        if i != -1:
            return text[: i + len(p)], True
    return text, False


def _srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_transcripts(rec_dir, out_dir, fixes, lesson_end, end_phrases, lesson_start=0.0):
    """Per-lesson transcript from the recording's SRT; cue times are re-based to the lesson start."""
    cues, texts = [], []
    for block in (rec_dir / "transcript.srt").read_text().strip().split("\n\n"):
        lines = block.split("\n")
        start_s, end_s = (_srt_seconds(t) for t in lines[1].split(" --> "))
        if start_s < lesson_start or start_s >= lesson_end:
            continue
        body, hit = _truncate_after(normalize("\n".join(lines[2:]), fixes), end_phrases)
        timing = f"{_srt_time(start_s - lesson_start)} --> {_srt_time(min(end_s, lesson_end) - lesson_start)}"
        cues.append("\n".join([str(len(cues) + 1), timing, body]))
        texts.append(body.strip())
        if hit:
            break
    txt = "\n".join(texts) + "\n"
    (out_dir / "transcript.txt").write_text(txt)
    (out_dir / "transcript.srt").write_text("\n\n".join(cues) + "\n")
    return len(txt.split()), len(cues)


def prepare_images(fine_dir, slides, prefix, out_slides):
    by_n = {s["n"]: s for s in json.loads((fine_dir / "slides_cropped.json").read_text())["slides"]}
    media = {}
    for n, name in slides.items():
        dst = out_slides / f"{prefix}{name}.png"
        im = Image.open(fine_dir / "cropped" / by_n[n]["cropped"]).convert("RGB")
        im.save(dst, optimize=True)
        if dst.stat().st_size > 700_000:
            im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(dst, optimize=True)
        media[name] = dst
    return media


def cut_audio(wav, clips, prefix, out_audio, lesson_end, offset=0.0):
    """clips are (start, end) seconds relative to the lesson; offset is the lesson start in the recording."""
    media = {}
    for key, (start, end) in clips.items():
        start = max(offset, offset + start - 0.2)
        end = min(lesson_end, offset + end + 0.2)
        dur = end - start
        dst = out_audio / f"{prefix}{key}.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(wav),
             "-af", f"afade=t=in:d=0.15,afade=t=out:st={max(0.0, dur - 0.15):.2f}:d=0.15",
             "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-ar", "22050", str(dst)],
            check=True,
        )
        media[key] = dst
    return media


def extra_html(quote, t, source_label, note=None):
    parts = []
    if quote:
        parts.append(f"“{quote}”")
    if note:
        parts.append(f"<br>{note}" if parts else note)
    parts.append(f'<span class="src">{source_label} · {t}</span>')
    return "".join(parts)


def build_package(deck_id, deck_name, tags, qa_model, cloze_model, qa_cards, cloze_cards,
                  images, audios, prefix, source_label, out_apkg, guid_ns=None):
    def img(name):
        return f'<img src="{images[name].name}">' if name else ""

    def snd(key):
        return f"[sound:{audios[key].name}]" if key in audios else ""

    ns = guid_ns or deck_name  # keep note GUIDs stable when notes move between (sub)decks
    deck = genanki.Deck(deck_id, deck_name)
    for c in qa_cards:
        deck.add_note(genanki.Note(
            model=qa_model,
            fields=[c["q"], c["a"], img(c.get("qimg")), img(c.get("aimg")), snd(c["key"]),
                    extra_html(c.get("quote"), c["t"], source_label, c.get("note"))],
            guid=genanki.guid_for(ns, c["key"]),
            tags=tags + c.get("tags", []),
        ))
    for c in cloze_cards:
        deck.add_note(genanki.Note(
            model=cloze_model,
            fields=[c["text"], img(c.get("img")), snd(c["key"]),
                    extra_html(c.get("quote"), c["t"], source_label, c.get("note"))],
            guid=genanki.guid_for(ns, c["key"]),
            tags=tags + c.get("tags", []),
        ))
    pkg = genanki.Package(deck)
    pkg.media_files = [str(p) for p in list(images.values()) + list(audios.values())]
    pkg.write_to_file(str(out_apkg))
    return deck


def build_lesson(cfg, scratch):
    """Build one lesson deck from a config dict; returns (deck, media paths, verify report, apkg path)."""
    out = cfg["out_dir"]
    for d in (out, out / "slides", out / "audio"):
        d.mkdir(parents=True, exist_ok=True)
    start = cfg.get("lesson_start", 0.0)
    words, cues = write_transcripts(cfg["rec_dir"], out, cfg["fixes"], cfg["lesson_end"], cfg["end_phrases"],
                                    lesson_start=start)
    images = prepare_images(cfg["fine_dir"], cfg["slides"], cfg["prefix"], out / "slides")
    audios = cut_audio(cfg["rec_dir"] / "audio.wav", cfg["clips"], cfg["prefix"], out / "audio",
                       cfg["lesson_end"], offset=start)
    qa_model, cloze_model = make_models(cfg["qa_model_id"], cfg["cloze_model_id"])
    apkg = out / f"{out.name}.apkg"
    deck = build_package(cfg["deck_id"], cfg["deck_name"], cfg["tags"], qa_model, cloze_model, cfg["qa"],
                         cfg["cloze"], images, audios, cfg["prefix"], cfg["source"], apkg)
    report = verify(apkg, scratch / f"verify_{out.name}")
    print(f"deck: {cfg['deck_name']}")
    print(f"  notes: {report['notes']}  cards: {report['cards']}  media: {report['media']}  "
          f"missing: {report['missing'] or 'none'}  unused: {report['unused'] or 'none'}")
    print(f"  apkg: {apkg} ({apkg.stat().st_size // 1024} KB)  transcript: {words} words, {cues} cues")
    return deck, list(images.values()) + list(audios.values()), report, apkg


def write_combined(decks, media, out_apkg):
    pkg = genanki.Package(decks)
    pkg.media_files = [str(p) for p in media]
    pkg.write_to_file(str(out_apkg))
    return out_apkg


def verify(apkg, verify_dir):
    verify_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(apkg) as z:
        names = z.namelist()
        db = "collection.anki21" if "collection.anki21" in names else "collection.anki2"
        z.extract(db, verify_dir)
        media_map = json.loads(z.read("media"))
    con = sqlite3.connect(verify_dir / db)
    n_notes = con.execute("select count(*) from notes").fetchone()[0]
    n_cards = con.execute("select count(*) from cards").fetchone()[0]
    flds = "\n".join(f for (f,) in con.execute("select flds from notes"))
    con.close()
    referenced = set(re.findall(r'src="([^"]+)"', flds)) | set(re.findall(r"\[sound:([^\]]+)\]", flds))
    packaged = set(media_map.values())
    return {"notes": n_notes, "cards": n_cards, "media": len(packaged),
            "missing": sorted(referenced - packaged), "unused": sorted(packaged - referenced)}
