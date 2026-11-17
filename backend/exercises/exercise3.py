"""Exercise 3: spelling from sound + phoneme categorization.

Two sub-tasks share this exercise:
  A. Spell-from-sound: the backend TTS-render a target word; the learner writes
     it (typed or handwritten -> OCR). We compare with fuzzy match.
  B. Categorize: present N candidate words and a target phoneme; learner picks
     which words share that phoneme.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from rapidfuzz import fuzz

import algorithm as alg
import repository as repo
import services


@dataclass
class SpellItem:
    word_id: int
    text: str
    phoneme: str | None


@dataclass
class SpellRound:
    items: list[SpellItem]
    # Audio is generated on demand per item to keep round payloads small.


@dataclass
class CategorizeRound:
    phoneme: str
    options: list["CategorizeOption"]


@dataclass
class CategorizeOption:
    word_id: int
    text: str
    is_target: bool


def build_spell_round(learner_id: int, n: int = 6, rng: random.Random | None = None) -> SpellRound:
    rng = rng or random
    states = repo.load_word_states(learner_id)
    if not states:
        repo.seed_word_set(learner_id, "phonics-starter")
        repo.set_guardian_word_set(learner_id, "phonics-starter")
        states = repo.load_word_states(learner_id)
    ids = alg.sample_weak_items(states, n, time.time(), rng=rng)
    words = repo.load_words_by_ids(learner_id, ids)
    return SpellRound(items=[SpellItem(w.id, w.text, w.phoneme) for w in words])


def render_word_audio(word: str) -> bytes:
    return services.synthesize_speech(word)


def check_spelling(
    learner_id: int,
    word_id: int,
    submitted: str,
    *,
    image_data_url: str | None = None,
) -> dict:
    """Check a typed or handwritten (OCR) spelling submission."""
    word = repo.load_word(learner_id, word_id)
    if not word:
        raise ValueError("unknown word")
    used_ocr = bool(image_data_url) and not submitted
    if used_ocr:
        submitted = services.ocr_from_image_data_url(image_data_url)
        if not submitted:
            # An unreadable page is not evidence about spelling: don't score it.
            return {
                "word": word.text,
                "submitted": "",
                "similarity": 0.0,
                "correct": False,
                "new_strength": round(word.strength, 3),
                "ocr_failed": True,
                "message": "We couldn't read the writing in that photo. Try again in "
                           "clearer light, or type the word instead.",
            }
    norm = _normalize(submitted)
    target = _normalize(word.text)
    similarity = fuzz.ratio(norm, target) / 100.0
    correct = norm == target if target else False
    if not correct and similarity >= 0.9:
        correct = True
    new_strength = repo.record_word_review(
        learner_id, word_id, "exercise-3-spell", correct, similarity, response=submitted
    )
    return {
        "word": word.text,
        "submitted": submitted,
        "similarity": round(similarity, 3),
        "correct": correct,
        "new_strength": round(new_strength, 3),
        "ocr_failed": False,
    }


def build_categorize_round(
    learner_id: int, n_options: int = 6, rng: random.Random | None = None
) -> CategorizeRound:
    """Pick a target phoneme, then sample options mixing target + distractor words."""
    rng = rng or random
    states = repo.load_word_states(learner_id)
    if not states:
        repo.seed_word_set(learner_id, "phonics-starter")
        repo.set_guardian_word_set(learner_id, "phonics-starter")
        states = repo.load_word_states(learner_id)
    words = repo.load_words_by_ids(learner_id, [s.id for s in states])
    if not words:
        raise ValueError("no words available")
    # Group by phoneme.
    by_phoneme: dict[str, list[repo.WordRow]] = {}
    for w in words:
        by_phoneme.setdefault(w.phoneme or "misc", []).append(w)
    viable = [p for p, ws in by_phoneme.items() if len(ws) >= 2]
    if not viable:
        viable = list(by_phoneme.keys())
    phoneme = rng.choice(viable)
    target_pool = by_phoneme[phoneme]
    distractor_pool = [w for p, ws in by_phoneme.items() if p != phoneme for w in ws]
    rng.shuffle(distractor_pool)
    n_target = max(1, min(len(target_pool), n_options // 2))
    chosen_targets = rng.sample(target_pool, n_target)
    n_dist = max(0, n_options - n_target)
    chosen_distractors = distractor_pool[:n_dist] if distractor_pool else []
    options = (
        [CategorizeOption(w.id, w.text, True) for w in chosen_targets]
        + [CategorizeOption(w.id, w.text, False) for w in chosen_distractors]
    )
    rng.shuffle(options)
    return CategorizeRound(phoneme=phoneme, options=options)


def check_categorization(
    learner_id: int,
    phoneme: str,
    selected_word_ids: list[int],
    option_word_ids: list[int],
) -> dict:
    """Score the learner's selected words against the target phoneme.

    Scoring is confined to the option words shown in the round
    (`option_word_ids`), so a perfect round scores 1.0 and words that were
    never shown are no longer penalised with spurious False reviews.
    """
    selected = set(selected_word_ids)
    options = set(option_word_ids)
    if not options:
        # Empty round -> zero score, no reviews recorded, no SQL IN ().
        return {
            "phoneme": phoneme,
            "correct_ids": [],
            "incorrect_ids": [],
            "target_ids": [],
            "missed_count": 0,
            "score": 0.0,
        }
    # Load the shown option words in one query.
    with repo.get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, phoneme FROM words WHERE learner_id=? AND id IN "
            f"({','.join('?' * len(options))})",
            (learner_id, *options),
        ).fetchall()
    target_ids = sorted(int(r["id"]) for r in rows if r["phoneme"] == phoneme)
    target_set = set(target_ids)
    correct_ids = sorted(selected & target_set)
    incorrect_ids = sorted(selected - target_set)
    missed_ids = sorted(target_set - selected)
    # Bayesian update: each correct pick reinforces; each wrong pick penalises;
    # each missed target counts as a missed opportunity. Only shown options.
    for wid in correct_ids:
        repo.record_word_review(learner_id, wid, "exercise-3-categorize", True, 0.8)
    for wid in incorrect_ids:
        repo.record_word_review(learner_id, wid, "exercise-3-categorize", False, 0.4)
    for wid in missed_ids:
        repo.record_word_review(learner_id, wid, "exercise-3-categorize", False, 0.3)
    score = len(correct_ids) / max(1, len(target_ids) + len(incorrect_ids))
    return {
        "phoneme": phoneme,
        "correct_ids": correct_ids,
        "incorrect_ids": incorrect_ids,
        "target_ids": target_ids,
        "missed_count": len(missed_ids),
        "score": round(score, 3),
    }


def _normalize(text: str) -> str:
    return "".join(ch.lower() for ch in (text or "") if ch.isalpha())
