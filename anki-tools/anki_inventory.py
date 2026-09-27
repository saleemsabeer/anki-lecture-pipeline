import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from ankiconnect import invoke

BACKUP = Path(sys.argv[1])
BACKUP.mkdir(parents=True, exist_ok=True)
(BACKUP / "apkg").mkdir(exist_ok=True)
STAMP = time.strftime("%Y%m%d-%H%M%S")


def chunks(xs, n=500):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


print("AnkiConnect version:", invoke("version"))

# ---------------------------------------------------------------- decks
decks = invoke("deckNamesAndIds")
deck_rows = []
for name in sorted(decks):
    q = f'deck:"{name}"'
    deck_rows.append({"deck": name, "id": decks[name], "notes": len(invoke("findNotes", query=q)),
                      "cards": len(invoke("findCards", query=q))})

# ---------------------------------------------------------------- models (note types)
models = invoke("modelNamesAndIds")
model_dump = {}
for m in sorted(models):
    model_dump[m] = {
        "id": models[m],
        "fields": invoke("modelFieldNames", modelName=m),
        "templates": invoke("modelTemplates", modelName=m),
        "css": invoke("modelStyling", modelName=m)["css"],
        "notes": len(invoke("findNotes", query=f'note:"{m}"')),
    }
(BACKUP / f"models-{STAMP}.json").write_text(json.dumps(model_dump, indent=1))

# ---------------------------------------------------------------- notes + cards
note_ids = invoke("findNotes", query="deck:*")
notes = []
for part in chunks(note_ids):
    notes.extend(invoke("notesInfo", notes=part))
(BACKUP / f"notes-{STAMP}.json").write_text(json.dumps(notes, indent=1))

card_ids = invoke("findCards", query="deck:*")
cards = []
for part in chunks(card_ids):
    cards.extend(invoke("cardsInfo", cards=part))
(BACKUP / f"cards-{STAMP}.json").write_text(json.dumps(cards, indent=1))

# ---------------------------------------------------------------- apkg export per top-level deck (with scheduling)
top = sorted({d.split("::")[0] for d in decks})
exported = []
for t in top:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", t)
    path = BACKUP / "apkg" / f"{safe}-{STAMP}.apkg"
    ok = invoke("exportPackage", deck=t, path=str(path), includeSched=True)
    exported.append((t, path.name, ok, path.stat().st_size // 1024 if path.exists() else 0))

# ---------------------------------------------------------------- summary
print(f"\n=== decks ({len(deck_rows)}) ===")
for r in deck_rows:
    print(f"{r['notes']:5d} notes {r['cards']:5d} cards  {r['deck']}")
print(f"\n=== note types ({len(model_dump)}) ===")
for m, d in model_dump.items():
    print(f"{d['notes']:5d} notes  {m}  fields={d['fields']}  templates={[t for t in d['templates']]}")
print(f"\n=== notes by note type × top-level deck ===")
by = Counter()
deck_of_note = defaultdict(set)
for c in cards:
    deck_of_note[c["note"]].add(c["deckName"].split("::")[0])
for n in notes:
    for d in deck_of_note.get(n["noteId"], {"?"}):
        by[(d, n["modelName"])] += 1
for (d, m), k in sorted(by.items()):
    print(f"{k:5d}  {d}  ×  {m}")
tags = Counter(t for n in notes for t in n["tags"])
print(f"\n=== tags ({len(tags)}) ===")
print(", ".join(f"{t}({k})" for t, k in sorted(tags.items())))
print(f"\n=== backup ===")
print(f"notes: {len(notes)}  cards: {len(cards)}  -> {BACKUP}")
for t, name, ok, kb in exported:
    print(f"  apkg {name}: ok={ok} {kb} KB")
sched = Counter("new" if c["type"] == 0 else "learning" if c["type"] in (1, 3) else "review" for c in cards)
print("card states:", dict(sched))
