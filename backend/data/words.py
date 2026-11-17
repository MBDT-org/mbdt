"""Built-in word lists tagged with a target phoneme.

These seed sets keep the app usable offline. Guardians may select a set from the
UI; the structure also supports importing additional vocabulary by dropping a
JSON file in `data/word_sets/` (see the README there) or by inserting into the
`word_sets` / `words` tables.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .curriculum_words import CURRICULUM_WORDS

logger = logging.getLogger("mbdt.words")

# (text, phoneme_label) grouped into named sets. Phoneme labels are simple,
# human-readable categories used by Exercise 3's categorization task.

STARTER: list[tuple[str, str]] = [
    # short vowels
    ("cat", "short-a"), ("hat", "short-a"), ("map", "short-a"), ("bat", "short-a"), ("fan", "short-a"), ("jam", "short-a"),
    ("bed", "short-e"), ("hen", "short-e"), ("net", "short-e"), ("pen", "short-e"), ("leg", "short-e"), ("vet", "short-e"),
    ("pig", "short-i"), ("sit", "short-i"), ("lip", "short-i"), ("fin", "short-i"), ("kid", "short-i"), ("six", "short-i"),
    ("dog", "short-o"), ("log", "short-o"), ("pot", "short-o"), ("fox", "short-o"), ("hop", "short-o"), ("mop", "short-o"),
    ("sun", "short-u"), ("bug", "short-u"), ("cup", "short-u"), ("nut", "short-u"), ("hug", "short-u"), ("mud", "short-u"),
    # long vowels
    ("cake", "long-a"), ("name", "long-a"), ("lake", "long-a"), ("gate", "long-a"), ("rain", "long-a"), ("day", "long-a"),
    ("tree", "long-e"), ("bee", "long-e"), ("key", "long-e"), ("leaf", "long-e"), ("sheep", "long-e"), ("three", "long-e"),
    ("kite", "long-i"), ("bike", "long-i"), ("five", "long-i"), ("lime", "long-i"), ("time", "long-i"), ("night", "long-i"),
    ("bone", "long-o"), ("home", "long-o"), ("rose", "long-o"), ("boat", "long-o"), ("coat", "long-o"), ("road", "long-o"),
    ("moon", "long-u"), ("food", "long-u"), ("boot", "long-u"), ("zoo", "long-u"), ("spoon", "long-u"), ("room", "long-u"),
    # digraphs
    ("ship", "sh"), ("fish", "sh"), ("shop", "sh"), ("shell", "sh"), ("wish", "sh"), ("brush", "sh"),
    ("chip", "ch"), ("chin", "ch"), ("chair", "ch"), ("cheese", "ch"), ("lunch", "ch"), ("chick", "ch"),
    ("thumb", "th"), ("bath", "th"), ("path", "th"), ("thin", "th"), ("moth", "th"), ("with", "th"),
    ("ring", "ng"), ("song", "ng"), ("king", "ng"), ("long", "ng"), ("wing", "ng"), ("sing", "ng"),
    # r-controlled
    ("car", "ar"), ("star", "ar"), ("jar", "ar"), ("farm", "ar"), ("arm", "ar"), ("park", "ar"),
    ("fork", "or"), ("corn", "or"), ("horn", "or"), ("storm", "or"), ("born", "or"), ("short", "or"),
]

# A slightly trickier second set (consonant blends & vowel teams).
GROWING: list[tuple[str, str]] = [
    ("frog", "short-o"), ("plug", "short-u"), ("spin", "short-i"), ("step", "short-e"), ("clap", "short-a"), ("sled", "short-e"),
    ("snail", "long-a"), ("train", "long-a"), ("pie", "long-i"), ("tie", "long-i"), ("boat", "long-o"), ("float", "long-o"),
    ("brain", "long-a"), ("cream", "long-e"), ("steam", "long-e"), ("toast", "long-o"), ("juice", "long-u"), ("fruit", "long-u"),
    ("chair", "air"), ("stair", "air"), ("hair", "air"), ("pair", "air"),
    ("book", "oo-short"), ("look", "oo-short"), ("foot", "oo-short"), ("good", "oo-short"),
    ("coin", "oi"), ("join", "oi"), ("boil", "oi"), ("soil", "oi"),
    ("cloud", "ou"), ("house", "ou"), ("mouse", "ou"), ("cow", "ou"),
    ("shirt", "or"), ("skirt", "or"), ("bird", "or"), ("dirt", "or"),
]

# ---------------------------------------------------------------------------
# Curriculum-aligned sets (primary school level). Phoneme labels reuse the same
# vowel-sound vocabulary as the phonics sets so Exercise 3's sort-by-sound task
# works within every set. The homophones set labels by *sound*, so sorting
# groups the same-sounding spellings together.
# ---------------------------------------------------------------------------

# US Dolch Pre-Primer (pre-K, age 4-5): first sight words.
DOLCH_PRE_PRIMER: list[tuple[str, str]] = [
    ("a", "schwa"), ("the", "schwa"),
    ("and", "short-a"), ("can", "short-a"),
    ("away", "long-a"), ("make", "long-a"), ("play", "long-a"),
    ("help", "short-e"), ("said", "short-e"),
    ("big", "short-i"), ("in", "short-i"), ("it", "short-i"),
    ("come", "short-u"), ("jump", "short-u"), ("run", "short-u"),
    ("down", "ou"), ("for", "or"), ("go", "long-o"), ("here", "ear"),
    ("look", "oo-short"), ("me", "long-e"), ("my", "long-i"),
    ("see", "long-e"), ("you", "oo-long"),
]

# US Dolch Grade 1 (age 6-7) sight words.
DOLCH_GRADE_1: list[tuple[str, str]] = [
    ("after", "short-a"), ("ask", "short-a"), ("had", "short-a"),
    ("has", "short-a"), ("thank", "short-a"),
    ("again", "short-e"), ("every", "short-e"), ("let", "short-e"),
    ("them", "short-e"), ("when", "short-e"),
    ("give", "short-i"), ("think", "short-i"),
    ("fly", "long-i"), ("from", "short-o"),
    ("just", "short-u"), ("of", "short-u"), ("once", "short-u"), ("some", "short-u"),
    ("how", "ou"), ("know", "long-o"), ("over", "long-o"),
    ("could", "oo-short"), ("may", "long-a"), ("take", "long-a"),
]

# US Dolch Grade 2 (age 7-8) sight words.
DOLCH_GRADE_2: list[tuple[str, str]] = [
    ("always", "or"), ("around", "ou"), ("because", "or"), ("been", "short-i"),
    ("before", "or"), ("both", "long-o"), ("call", "or"), ("cold", "long-o"),
    ("does", "short-u"), ("fast", "short-a"), ("first", "er"), ("found", "ou"),
    ("gave", "long-a"), ("made", "long-a"), ("many", "short-e"),
    ("pull", "oo-short"), ("read", "long-e"), ("right", "long-i"),
    ("sleep", "long-e"), ("their", "air"), ("these", "long-e"),
    ("which", "short-i"), ("wish", "short-i"), ("would", "oo-short"),
]

# US Fry words 101-200 selection (grades 1-2, age 6-8).
FRY_101_200: list[tuple[str, str]] = [
    ("sound", "ou"), ("only", "long-o"), ("little", "short-i"), ("work", "er"),
    ("place", "long-a"), ("live", "short-i"), ("back", "short-a"),
    ("most", "long-o"), ("things", "short-i"), ("name", "long-a"),
    ("sentence", "short-e"), ("great", "long-a"), ("through", "oo-long"),
    ("much", "short-u"), ("before", "or"), ("line", "long-i"),
    ("means", "long-e"), ("same", "long-a"), ("boy", "oi"),
    ("follow", "short-o"), ("came", "long-a"), ("show", "long-o"),
    ("picture", "short-i"), ("learn", "er"),
]

# UK National Curriculum Year 1-2 common exception words (age 5-7).
UK_YEAR_1_2: list[tuple[str, str]] = [
    ("today", "long-a"), ("says", "short-e"), ("friend", "short-e"),
    ("school", "oo-long"), ("pull", "oo-short"), ("full", "oo-short"),
    ("house", "ou"), ("door", "or"), ("floor", "or"),
    ("kind", "long-i"), ("mind", "long-i"), ("behind", "long-i"),
    ("child", "long-i"), ("children", "short-i"), ("wild", "long-i"),
    ("climb", "long-i"), ("gold", "long-o"), ("told", "long-o"),
    ("break", "long-a"), ("pretty", "short-i"), ("hour", "ou"),
    ("move", "oo-long"), ("eye", "long-i"), ("whole", "long-o"),
]

# UK National Curriculum Year 3-4 statutory word list selection (age 7-9).
UK_YEAR_3_4: list[tuple[str, str]] = [
    ("answer", "ar"), ("arrive", "long-i"), ("believe", "long-e"),
    ("bicycle", "long-i"), ("breath", "short-e"), ("build", "short-i"),
    ("caught", "or"), ("circle", "er"), ("complete", "long-e"),
    ("decide", "long-i"), ("describe", "long-i"), ("different", "short-i"),
    ("difficult", "short-i"), ("early", "er"), ("earth", "er"),
    ("eight", "long-a"), ("enough", "short-u"), ("famous", "long-a"),
    ("guard", "ar"), ("heart", "ar"), ("height", "long-i"),
    ("island", "long-i"), ("knowledge", "short-o"), ("minute", "short-i"),
]

# UK Letters and Sounds Phase 5 (age 5-7): new graphemes and split digraphs.
# Labels are the graphemes themselves (ay, ou, ie, ...) since that is what the
# phase teaches; split digraphs are written a-e / i-e / o-e / u-e.
LETTERS_SOUNDS_PHASE_5: list[tuple[str, str]] = [
    ("spray", "ay"), ("cloud", "ou"), ("pie", "ie"), ("seat", "ea"),
    ("enjoy", "oy"), ("bird", "ir"), ("blue", "ue"), ("claw", "aw"),
    ("wheel", "wh"), ("dolphin", "ph"), ("new", "ew"), ("toe", "oe"),
    ("sauce", "au"), ("key", "ey"), ("theme", "e-e"), ("prize", "i-e"),
    ("bone", "o-e"), ("cube", "u-e"), ("flute", "u-e"), ("phone", "ph"),
    ("straw", "aw"), ("few", "ew"), ("rescue", "u-e"), ("whistle", "wh"),
]

# Homophones (age 7+): pairs/triples that share a sound but not a spelling.
# Labels are the shared sound, so sort-by-sound groups each pair together.
HOMOPHONES: list[tuple[str, str]] = [
    ("to", "oo-long"), ("too", "oo-long"), ("two", "oo-long"),
    ("blue", "oo-long"), ("blew", "oo-long"),
    ("see", "long-e"), ("sea", "long-e"), ("bee", "long-e"),
    ("hear", "ear"), ("here", "ear"),
    ("where", "air"), ("wear", "air"), ("bear", "air"), ("bare", "air"),
    ("sun", "short-u"), ("son", "short-u"), ("one", "short-u"), ("won", "short-u"),
    ("no", "long-o"), ("know", "long-o"),
    ("right", "long-i"), ("write", "long-i"),
    ("eight", "long-a"), ("ate", "long-a"),
]

SETS: dict[str, list[tuple[str, str | None]]] = {
    "phonics-starter": STARTER,
    "phonics-growing": GROWING,
    "dolch-pre-primer": DOLCH_PRE_PRIMER,
    "dolch-grade-1": DOLCH_GRADE_1,
    "dolch-grade-2": DOLCH_GRADE_2,
    "fry-101-200": FRY_101_200,
    "uk-year-1-2": UK_YEAR_1_2,
    "uk-year-3-4": UK_YEAR_3_4,
    "letters-sounds-phase-5": LETTERS_SOUNDS_PHASE_5,
    "homophones": HOMOPHONES,
}

# Downloaded curriculum lists (see curriculum_words.py). These carry no
# phoneme label: hand-labelling thousands of words is infeasible, and a wrong
# guess is worse than none in a dyslexia app. Exercise 3's categorize round
# groups them under "misc"; spell rounds and Exercise 1 are unaffected.
for _set_id, _words in CURRICULUM_WORDS.items():
    SETS[_set_id] = [(w, None) for w in _words]

# Human-readable labels for the guardian UI dropdown.
SET_LABELS: dict[str, str] = {
    "phonics-starter": "Phonics Starter (age 4-6) - CVC, long vowels, digraphs",
    "phonics-growing": "Phonics Growing (age 5-7) - blends and vowel teams",
    "dolch-pre-primer": "Dolch Pre-Primer (US, age 4-5) - first sight words",
    "dolch-grade-1": "Dolch Grade 1 (US, age 6-7) - sight words",
    "dolch-grade-2": "Dolch Grade 2 (US, age 7-8) - sight words",
    "fry-101-200": "Fry Words 101-200 (US, age 6-8) - high frequency",
    "uk-year-1-2": "UK Year 1-2 (age 5-7) - common exception words",
    "uk-year-3-4": "UK Year 3-4 (age 7-9) - statutory word list",
    "letters-sounds-phase-5": "Letters and Sounds Phase 5 (UK, age 5-7) - new graphemes",
    "homophones": "Homophones (age 7+) - same sound, different spelling",
    "awl": "Academic Word List - university vocabulary",
    "ngsl": "NGSL - New General Service List, high frequency",
}

# Fonts used by Exercise 1. Most are web-safe; "lexend" and "opendyslexic" are
# accessibility-oriented and loaded on the frontend. The adaptive engine picks
# fonts the learner struggles with more often.
FONTS: list[str] = [
    "Lexend",
    "OpenDyslexic",
    "Arial",
    "Comic Sans MS",
    "Verdana",
    "Georgia",
    "Courier New",
]


# ---------------------------------------------------------------------------
# Custom word sets
# ---------------------------------------------------------------------------
# Drop a JSON file into backend/data/word_sets/ and it appears in the guardian
# word-set dropdown on the next restart. See word_sets/README.md for the format.


def _load_custom_sets(folder: Path | None = None) -> None:
    """Merge user-authored sets from `data/word_sets/*.json` into SETS."""
    folder = folder or Path(__file__).with_name("word_sets")
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("*.json")):
        if path.name.endswith(".example.json"):
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            set_id = str(raw.get("id") or path.stem).strip()
            if not set_id:
                raise ValueError("missing id")
            words: list[tuple[str, str | None]] = []
            for entry in raw.get("words", []):
                if isinstance(entry, str):
                    text, phoneme = entry, None
                elif isinstance(entry, dict):
                    text, phoneme = entry.get("word"), entry.get("phoneme")
                else:
                    continue
                text = str(text or "").strip().lower()
                if text:
                    words.append((text, str(phoneme) if phoneme else None))
            if not words:
                raise ValueError("no words")
            if set_id in SETS and not raw.get("override"):
                raise ValueError(f"{set_id!r} already exists (add \"override\": true to replace)")
            SETS[set_id] = words
            SET_LABELS[set_id] = str(raw.get("label") or set_id)
        except Exception as exc:  # a broken file must not take the app down
            logger.warning("Skipping custom word set %s: %s", path.name, exc)


_load_custom_sets()
