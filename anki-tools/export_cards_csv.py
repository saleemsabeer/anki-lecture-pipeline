#!/usr/bin/env python3
"""Export every card in your Anki collection to a CSV via AnkiConnect (one row per card, rendered text).

  python export_cards_csv.py [--query 'deck:*'] [--out anki-cards.csv] [--open]

Columns: Deck, Note type, Card, Question, Answer, Tags, Suspended, Diagram, Audio, Note ID, Card ID.
HTML is stripped, images/SVG become "[diagram]", sound tags are removed; the Answer column holds only the answer side
when the template separates it with <hr id="answer">.
"""
import argparse
import csv
import html
import os
import re
import subprocess

from ankiconnect import invoke


def clean(s):
    s = re.sub(r"\[sound:[^\]]+\]|\[anki:play:[qa]:\d+\]", "", s or "")
    s = re.sub(r"<(style|script).*?</\1>", "", s, flags=re.S)
    s = re.sub(r"<svg.*?</svg>", " [diagram] ", s, flags=re.S)
    s = re.sub(r"<img[^>]*>", " [diagram] ", s)
    s = re.sub(r"<br\s*/?>|</(div|p|li|tr)>", " / ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"(\s*/\s*)+", " / ", s)
    return re.sub(r"\s+", " ", s).strip(" /")


def answer_only(a):
    parts = re.split(r"<hr\s+id=\"?answer\"?\s*/?>", a or "", maxsplit=1, flags=re.I)
    return parts[1] if len(parts) == 2 else a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="deck:*", help="Anki search; default = every card")
    ap.add_argument("--out", default="anki-cards.csv")
    ap.add_argument("--open", action="store_true", help="open the file with the default app afterwards (macOS)")
    a = ap.parse_args()

    ids = invoke("findCards", query=a.query)
    cards = []
    for i in range(0, len(ids), 200):
        cards += invoke("cardsInfo", cards=ids[i:i + 200])
    nids = sorted({c["note"] for c in cards})
    tags = {}
    for i in range(0, len(nids), 200):
        for n in invoke("notesInfo", notes=nids[i:i + 200]):
            tags[n["noteId"]] = " ".join(n["tags"])
    cards.sort(key=lambda c: (c["deckName"], c["note"], c["ord"]))

    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads UTF-8
        w = csv.writer(f)
        w.writerow(["Deck", "Note type", "Card", "Question", "Answer", "Tags", "Suspended", "Diagram", "Audio",
                    "Note ID", "Card ID"])
        for c in cards:
            raw = c["question"] + c["answer"]
            w.writerow([c["deckName"], c["modelName"], c["ord"] + 1, clean(c["question"]),
                        clean(answer_only(c["answer"])), tags.get(c["note"], ""),
                        "yes" if c["queue"] == -1 else "", "yes" if re.search(r"<img|<svg", raw) else "",
                        "yes" if re.search(r"\[anki:play|\[sound:", raw) else "", c["note"], c["cardId"]])
    print(f"wrote {len(cards)} cards ({len(nids)} notes) -> {a.out} ({os.path.getsize(a.out) // 1024} KB)")
    if a.open:
        subprocess.run(["open", a.out], check=False)


if __name__ == "__main__":
    main()
