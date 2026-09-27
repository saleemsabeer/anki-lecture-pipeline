"""Example lesson config for build_lessons.py — copy this file per lesson and fill in the numbers.

Directory layout assumed (all under WORK):
  WORK/rec/transcript.srt   whisper.cpp output for the recording (see README step 2)
  WORK/rec/audio.wav        the recording's audio track
  WORK/slides/              output of extract_slides.py + crop_slides.py (slides_cropped.json, cropped/)
  WORK/out/<Lesson>/        where the deck, slides/ and audio/ are written
"""
from pathlib import Path

WORK = Path(__file__).resolve().parent / "work"
OUT = WORK / "out" / "Example-Lesson"

# Deterministic IDs: pick once per deck / note type and never change them (Anki updates in place on re-import).
DECK_ID = 1700000001
QA_MODEL_ID, CLOZE_MODEL_ID = 1700000101, 1700000102

CFG = dict(
    rec_dir=WORK / "rec",
    fine_dir=WORK / "slides",
    out_dir=OUT,
    deck_name="Course::Module::Example Lesson",   # "::" nests decks
    deck_id=DECK_ID,
    qa_model_id=QA_MODEL_ID,
    cloze_model_id=CLOZE_MODEL_ID,
    tags=["course", "module-1"],
    prefix="course-example-",                     # media file prefix: keep it unique per lesson
    source="Course · Example Lesson",             # shown in the Extra block with the timestamp
    lesson_start=0.0,                             # seconds into the recording where this lesson starts
    lesson_end=95.0,                              # seconds where it ends (clips are relative to lesson_start)
    end_phrases=["see you in the next lecture."], # transcript is cut after the first of these
    # regex fixes for words the transcriber gets wrong (pattern, replacement), applied case-insensitively
    fixes=[
        (r"\bcube\b", "kube"),
        (r"\bkube-?let\b", "kubelet"),
    ],
    # slide number from slides_cropped.json -> short name used by cards' qimg/aimg/img
    slides={
        2: "overview",
        5: "architecture",
    },
    # narration clip per card key: (start, end) seconds relative to lesson_start; 0.2 s padding + fades are added
    clips={
        "what-is": (3, 21),
        "parts": (22, 48),
        "parts-cloze": (22, 48),
    },
    qa=[
        dict(key="what-is", t="0:03", aimg="overview",
             q="What problem does the component introduced in this lesson solve?",
             a="<b>One-sentence answer</b>, then the detail the narrator gives.",
             quote="The narrator's exact sentence goes here — it is shown in the Extra block.",
             tags=["definition"]),
        dict(key="parts", t="0:22", aimg="architecture",
             q="Name the three parts shown on the architecture slide.",
             a="<ol><li>Part one</li><li>Part two</li><li>Part three</li></ol>",
             note="Optional extra note shown under the quote."),
    ],
    cloze=[
        dict(key="parts-cloze", t="0:22", img="architecture",
             text="The architecture has {{c1::part one}}, {{c2::part two}} and {{c3::part three}}."),
    ],
)
