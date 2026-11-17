"""Exercise 5: LLM-generated stories built from the learner's target words,
phonemes and (optionally) guardian-approved interests; then reading
comprehension questions answered by the learner and auto-scored.

Safety: we never send personally identifiable information to the model. The
prompt is constructed server-side from a fixed template and the learner's
*word list* + guardian-approved interest categories only. Output is additionally
post-filtered by a keyword blocklist that combines a fixed safety list with the
topics the guardian asked to avoid.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass

import algorithm as alg
import repository as repo
import services


@dataclass
class ComprehensionQuestion:
    question: str
    expected: str


@dataclass
class StoryRound:
    story_id: int
    text: str
    target_words: list[str]
    questions: list[ComprehensionQuestion]


STORY_SYSTEM = (
    "You are a writer of short, joyful stories for young children (ages 7-11) "
    "who have dyslexia. Rules you MUST follow: "
    "(1) Use simple, decodable language and short sentences. "
    "(2) Every requested word MUST appear verbatim at least once. "
    "(3) Be kind, encouraging and culturally inclusive. "
    "(4) NEVER include violence, scares, romance, politics, religion, medical "
    "content, or anything frightening. "
    "(5) Keep the story under 150 words. "
    "(6) Return ONLY a JSON object of the form "
    '{"story": "...", "questions": [{"question": "...", "answer": "..."}, ...]} '
    "with 3 literal reading-comprehension questions whose answers are stated "
    "directly in the story."
)

BASE_BLOCKLIST = [
    "kill", "blood", "gun", "drug", "sex", "hate", "war", "weapon", "bomb",
    "terror", "suicide", "abuse",
]

# Strict json_schema for Requesty structured output: every field required,
# additionalProperties false on every object (see Requesty structured-outputs
# docs). The model is constrained at decoding level to emit this shape.
STORY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "story": {
            "type": "string",
            "description": "The story text, under 150 words, simple decodable language.",
        },
        "questions": {
            "type": "array",
            "description": "Exactly 3 literal reading-comprehension questions.",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["story", "questions"],
    "additionalProperties": False,
}


def build_story(learner_id: int, n_words: int = 8, rng: random.Random | None = None) -> StoryRound:
    """Generate an LLM story targeting the learner's weakest words."""
    rng = rng or random
    states = repo.load_word_states(learner_id)
    if not states:
        repo.seed_word_set(learner_id, "phonics-starter")
        repo.set_guardian_word_set(learner_id, "phonics-starter")
        states = repo.load_word_states(learner_id)
    ids = alg.sample_weak_items(states, n_words, time.time(), rng=rng)
    words = repo.load_words_by_ids(learner_id, ids)
    word_texts = [w.text for w in words]
    guardian = repo.get_guardian_settings(learner_id) or {}
    interests = [t for t in (guardian.get("interests") or "").split(",") if t.strip()]
    avoid = [t for t in (guardian.get("safety_categories") or "").split(",") if t.strip()]
    model = (guardian.get("llm_model") or "").strip() or None

    user_prompt = _build_user_prompt(word_texts, interests, avoid)
    payload = services.chat_json(
        [
            {"role": "system", "content": STORY_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.6,
        max_tokens=4096,  # generous: reasoning models spend tokens before the story
        schema=STORY_SCHEMA,
        schema_name="StoryRound",
    )
    story = _filter_story(str(payload.get("story", "")), avoid)
    raw_questions = payload.get("questions", []) or []
    questions = [
        ComprehensionQuestion(
            question=str(q.get("question", "")).strip(),
            expected=str(q.get("answer", "")).strip(),
        )
        for q in raw_questions
        if q.get("question") and q.get("answer")
    ][:3]
    # Persist.
    story_id = repo.save_story(learner_id, story, [w.id for w in words])
    # Reinforce word exposure: a light positive prior for appearing in a story.
    for w in words:
        repo.record_word_review(learner_id, w.id, "exercise-5-exposure", True, 0.5)
    return StoryRound(
        story_id=story_id,
        text=story,
        target_words=word_texts,
        questions=questions,
    )


def _build_user_prompt(
    words: list[str], interests: list[str], avoid: list[str] | None = None,
) -> str:
    interest_clause = (
        f" Suggested themes the child likes (use at most one, keep it optional): {', '.join(interests)}."
        if interests else ""
    )
    avoid_clause = (
        f" The child's guardian asked to avoid these topics entirely: {', '.join(avoid)}."
        if avoid else ""
    )
    return (
        f"Write a short story that includes each of these words at least once: "
        f"{', '.join(words)}.{interest_clause}{avoid_clause}\n"
        f"Then write 3 literal reading-comprehension questions a 7-11 year old can "
        f"answer from the text. Return JSON: "
        f'{{"story": "...", "questions": [{{"question": "...", "answer": "..."}}]}}.'
    )


def _filter_story(text: str, avoid: list[str] | None = None) -> str:
    """Soft safety filter: blank obvious violations and guardian-requested
    topics. Provider-side filtering is the primary guard; this is
    defense-in-depth.

    Terms match whole words only, so a blocked "war" does not blank a sentence
    about something "warm", and "skill" survives a block on "kill".
    """
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    terms = {b.lower() for b in BASE_BLOCKLIST}
    for term in avoid or []:
        term = term.strip().lower()
        if len(term) >= 2:
            terms.add(term)
    for bad in sorted(terms, key=len, reverse=True):
        pattern = re.compile(
            r"[^.!?]*(?<!\w)" + re.escape(bad) + r"(?!\w)[^.!?]*[.!?]?",
            re.IGNORECASE,
        )
        if pattern.search(cleaned):
            cleaned = pattern.sub(
                "[This part of the story was removed by the safety filter.]",
                cleaned,
                count=1,
            )
    return cleaned


def check_comprehension(
    learner_id: int,
    story_id: int,
    answers: list[dict[str, str]],
) -> dict:
    """Score submitted answers against expected answers; record results."""
    with repo.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, text, word_ids FROM stories WHERE id=? AND learner_id=?",
            (story_id, learner_id),
        ).fetchall()
        if not rows:
            raise ValueError("story not found")
    # We don't store the questions separately, so callers pass (question, answer).
    n_total = len(answers)
    n_correct = 0
    for a in answers:
        expected = (a.get("expected") or "").strip().lower()
        given = (a.get("given") or "").strip().lower()
        correct = bool(expected) and _answer_match(given, expected)
        if correct:
            n_correct += 1
        repo.save_comprehension_result(
            story_id,
            a.get("question", ""),
            a.get("expected", ""),
            a.get("given", ""),
            correct,
        )
    accuracy = n_correct / n_total if n_total else 0.0
    return {
        "story_id": story_id,
        "answered": n_total,
        "correct": n_correct,
        "accuracy": round(accuracy, 3),
    }


def _answer_match(given: str, expected: str) -> bool:
    from rapidfuzz import fuzz
    if given == expected:
        return True
    # Token-set ratio handles articles / word-order differences.
    return fuzz.token_set_ratio(given, expected) / 100.0 >= 0.85
