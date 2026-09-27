# anki-lecture-pipeline

Tools for turning your own study material into [Anki](https://apps.ankiweb.net/) decks, entirely offline:

| Folder | What it does |
|---|---|
| `video-to-anki/` | Screen recording of a lecture → slide images (deduplicated), narration clips, and a `.apkg` deck whose cards carry the exact slide and the narrator's sentence. Uses ffmpeg, whisper.cpp and genanki. |
| `yaml-deck-builder/` | YAML card definitions → `.apkg` with Mermaid diagrams (fill-in-the-blank fronts supported), macOS `say` audio, deterministic IDs (rebuilds update cards in place), plus checkpoint / criterion coverage checks and a sqlite read-back report. |
| `anki-tools/` | Small AnkiConnect utilities: raw API calls, full collection backup + inventory, CSV export of every card, and an inline-SVG diagram library for card fields. |

Nothing here calls an external API: transcription (whisper.cpp), text-to-speech (`say`) and diagram rendering
(mermaid-cli driving your local Chrome) all run on your machine.

> Decks built from paid or licensed courses contain the course's slides and narration. Keep those decks for your own
> study — this repo publishes the tooling only.

## Requirements

- macOS (for `say`; everything else is portable), Python 3.11+
- `pip install genanki pyyaml numpy pillow`
- `brew install ffmpeg whisper-cpp` and a whisper model (e.g. `ggml-large-v3-turbo.bin`)
- Node ≥ 18 for `npx @mermaid-js/mermaid-cli`; `yaml-deck-builder/puppeteer.json` points it at the system Google Chrome
  so no Chromium download is needed (edit the path for another browser). Graphviz `dot` is used as a fallback when a
  `<name>.dot` file exists next to the `.mmd`.
- Anki desktop with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on for the `anki-tools/` scripts.

## video-to-anki

1. **Record** the lecture (e.g. OBS, application capture of the browser, 1080p). Extract the audio:
   `ffmpeg -i lecture.mov -vn -ac 1 -ar 16000 audio.wav`
2. **Transcribe** offline: `whisper-cli -m ggml-large-v3-turbo.bin -f audio.wav -osrt -of transcript --prompt "<domain vocabulary>"`
   → `transcript.srt`. Priming with the lecture's vocabulary fixes most jargon; the rest goes in the config's `fixes`.
3. **Find the slides**: `python extract_slides.py lecture.mov slides/ [BIG] [SMALL]` samples one frame per second, hashes
   them (dHash), cuts the video into stable segments and keeps the last stable frame of each unique slide. It writes
   `slides.json` and contact sheets so you can pick slide numbers by eye. `add_frames.py lecture.mov slides/ 312 480`
   adds specific timestamps that the detector skipped.
4. **Crop** the player out of the recording: `python crop_slides.py slides/ [lesson_end_seconds] [l,t,r,b]` finds the
   region that actually changes between slides and crops every frame to it.
5. **Write a lesson config** (see `example_lesson.py`): which slide number goes with which card, the narration clip for
   each card as `(start, end)` seconds, and the Q/A or cloze text.
6. **Build**: `python build_lessons.py example_lesson --combined all.apkg` cuts the clips, packages the images and
   verifies the `.apkg` (every referenced media file present, none unused). Import the `.apkg` into Anki.

Card layout: question (+ optional image) on the front; answer, slide image, narration clip and an *Extra* block with the
narrator's sentence and a timestamp on the back. Cloze notes share the same media.

## yaml-deck-builder

```bash
cd yaml-deck-builder
python build.py --check              # coverage checks only
python build.py --no-audio           # fast build → dist/<deck>.apkg (+ dist/all-decks.apkg when several decks)
python build.py --report --samples 3 # full build with audio, then sqlite read-back with samples
```

`cards/<deck>.yaml` is the source of truth — see `cards/git-basics.yaml`. Deck header keys: `deck` (Anki name, `::`
nests), `base_tag` / `phase_tag` (added to every note), `apkg` (output file name), `criteria` + `min_per_criterion`
(criterion → minimum card count, matched by tag), `checkpoint_prefix` (which ids in `checkpoints.yaml` this deck must
cover). Card types: `basic`, `basic_reversed`, `cloze`, `scenario`, `command` (spoken literally, then in plain English),
`why`, `rego` (or any code walk-through; spoken as a one-sentence summary). Optional per card: `diagram` (back),
`diagram_front` (e.g. a blanked variant), `audio: full|summary|none`, `spoken_summary`, `extra`, `source`, `tags`,
`checkpoints`, `confidence` (`low` adds the tag `needs-review`).

Note GUIDs derive from the card `id`, so keep ids stable and re-import to update existing cards without losing review
history. Diagrams (`diagrams/<name>.mmd`) and audio clips are cached by content hash under `media/`.

## anki-tools

- `ankiconnect.py version` / `ankiconnect.py findNotes '{"query":"tag:needs-review"}'` — call any AnkiConnect action.
- `anki_inventory.py backup/` — dumps every note, card and note type as JSON, exports each top-level deck as `.apkg`
  (with scheduling) and prints an inventory (decks, note types, tags, card states).
- `export_cards_csv.py [--query 'deck:*'] [--out cards.csv] [--open]` — one row per card with the rendered
  question/answer text, tags, suspended/diagram/audio flags.
- `bp_svg.py` — builds inline SVG "blueprint" diagrams (boxes, arrows, groups) that render inside Anki fields without
  media files; `python bp_svg.py` writes the built-in examples.

## Layout conventions

Generated output (`dist/`, `media/`, `build-cache/`, `.apkg`, audio, images, recordings) is git-ignored; only sources
are versioned.
