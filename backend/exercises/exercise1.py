"""Exercise 1: Words move across the screen in adaptively-selected fonts; the
learner speaks each word and an STT model checks pronunciation.

Pipeline:
  1. Backend samples N weak words + N weak fonts (Bayesian targeting).
  2. Frontend animates each word in its assigned font and captures microphone
     audio per word.
  3. Backend transcribes the audio (Requesty STT), fuzzy-matches it against the
     target, and records a word + font review. Confidence scheduling tightens
     the required similarity as the learner's mean strength rises.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass

from rapidfuzz import fuzz

import algorithm as alg
import repository as repo
import services
from config import settings
from safety import mask_profanity


@dataclass
class Exercise1Item:
    word_id: int
    text: str
    phoneme: str | None
    font: str
    audio_url: str | None = None  # TTS model pronunciation (optional)


@dataclass
class Exercise1Round:
    items: list[Exercise1Item]
    confidence_floor: float


def build_round(learner_id: int, n: int = 8, rng: random.Random | None = None) -> Exercise1Round:
    """Compose a round: sample words, fonts, and TTS pronunciation references."""
    rng = rng or random
    word_states = repo.load_word_states(learner_id)
    if not word_states:
        # Nothing seeded yet: use starter set.
        repo.seed_word_set(learner_id, "phonics-starter")
        repo.set_guardian_word_set(learner_id, "phonics-starter")
        word_states = repo.load_word_states(learner_id)

    word_ids = alg.sample_weak_items(word_states, n, time.time(), rng=rng)
    words = repo.load_words_by_ids(learner_id, word_ids)
    fonts = repo.pick_fonts(learner_id, n, rng=rng)

    guardian = repo.get_guardian_settings(learner_id) or {}
    floor = float(guardian.get("confidence_floor") or 0.6)

    items: list[Exercise1Item] = []
    # Fewer fonts than words (7 builtin fonts < default n=8): cycle so no word
    # is dropped by zip() truncation.
    for i, w in enumerate(words):
        items.append(Exercise1Item(
            word_id=w.id,
            text=w.text,
            phoneme=w.phoneme,
            font=fonts[i % len(fonts)],
        ))
    return Exercise1Round(items=items, confidence_floor=floor)


def generate_pronunciation_audio(word: str) -> bytes:
    """TTS-render a reference pronunciation (used as a 'try again' hint)."""
    return services.synthesize_speech(word)


def check_pronunciation(
    learner_id: int,
    word_id: int,
    font: str,
    audio_bytes: bytes,
    *,
    filename: str = "audio.webm",
) -> dict:
    """Transcribe the learner's audio and score it against the target word."""
    word = repo.load_word(learner_id, word_id)
    if not word:
        raise ValueError("unknown word")
    transcript, stt_conf = services.transcribe(audio_bytes, filename=filename)
    # Normalize: lowercase, strip punctuation/whitespace, take first token.
    norm = _normalize(transcript)
    similarity = _transcript_similarity(transcript, word.text)
    # Adaptive threshold: higher for stronger words (confidence scheduling).
    strength = word.strength
    threshold = _adaptive_threshold(strength)
    correct = bool(norm) and similarity >= threshold

    # Confidence in the verdict itself; feeds the Bayesian update mass via
    # algorithm.success_score (confident correct -> strong success,
    # confident wrong -> strong failure, uncertain -> merciful half-mass).
    if not norm:
        # No intelligible speech: the mic may simply have failed — record a
        # soft failure rather than a confident one.
        confidence = 0.25
    else:
        confidence = _verdict_confidence(similarity, threshold, stt_conf)
    new_strength = repo.record_word_review(
        learner_id, word_id, "exercise-1", correct, confidence, response=transcript
    )
    repo.record_font_review(learner_id, font, correct, confidence)
    return {
        "word": word.text,
        # The raw transcript is what the learner said, so it is stored as
        # evidence above; mask it before it is shown back in the UI.
        "transcript": mask_profanity(transcript),
        "similarity": round(similarity, 3),
        "threshold": round(threshold, 3),
        "correct": correct,
        "confidence": round(confidence, 3),
        "stt_confidence": None if stt_conf is None else round(stt_conf, 3),
        "new_strength": round(new_strength, 3),
    }


def _normalize(text: str) -> str:
    out = "".join(ch.lower() for ch in text if ch.isalpha())
    return out


def _transcript_similarity(transcript: str, target: str) -> float:
    """Edit similarity between what was said and the target word, in [0, 1].

    Speech-to-text often returns a whole utterance ("the word is bat") or extra
    punctuation. Comparing the concatenated transcript against "bat" scores that
    as a miss, so the best single token is considered too. The full-string ratio
    still wins for words the model splits or hyphenates.
    """
    wanted = _normalize(target)
    if not wanted:
        return 0.0
    best = fuzz.ratio(_normalize(transcript), wanted)
    for token in re.findall(r"[A-Za-z]+", transcript or ""):
        best = max(best, fuzz.ratio(token.lower(), wanted))
    return round(best / 100.0, 4)


def _verdict_confidence(
    similarity: float, threshold: float, stt_conf: float | None
) -> float:
    """Confidence in the correct/incorrect verdict, in [0, 1].

    Two signals combine:
    - margin: how far `similarity` sits from the decision threshold; a margin
      of 0.2 saturates (fully confident), at-threshold is a coin flip (0.5).
    - stt_conf: the transcription model's own confidence from segment
      avg_logprob (whisper reports it; voxtral currently does not). When
      present it discounts trust in the transcript by up to half; when None
      the verdict rests on the margin alone.
    """
    margin = (similarity - threshold) if similarity >= threshold else (threshold - similarity)
    conf = min(1.0, 0.5 + margin * 2.5)
    if stt_conf is not None:
        conf *= 0.5 + 0.5 * stt_conf
    return conf


def _adaptive_threshold(strength: float, lo: float = 0.6, hi: float = 0.92) -> float:
    """Linearly raise the required similarity as word strength improves."""
    s = max(0.0, min(1.0, strength))
    return lo + (hi - lo) * s
