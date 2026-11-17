"""Self-checks for STT-confidence integration into review scoring.

Run: uv run python backend/test_confidence.py
"""

from exercises.exercise1 import _verdict_confidence
from safety import mask_profanity
from services import _is_no_speech


def test_clear_match_no_stt_signal():
    # Voxtral path: no avg_logprob -> verdict rests on the margin alone.
    assert _verdict_confidence(1.0, 0.6, None) == 1.0


def test_borderline_verdict_is_coin_flip():
    # Just under the threshold: barely-confident failure (soft update).
    assert abs(_verdict_confidence(0.88, 0.92, None) - 0.6) < 1e-9


def test_stt_confidence_discounts_trust():
    # Same transcript match, but STT is unsure -> discounted up to half.
    assert _verdict_confidence(1.0, 0.6, 1.0) == 1.0
    assert abs(_verdict_confidence(1.0, 0.6, 0.3) - 0.65) < 1e-9


def test_confidently_wrong_is_confident_failure():
    # STT clearly heard a wrong word -> high confidence in the *failure*
    # verdict, which success_score maps to a strong failure update.
    assert _verdict_confidence(0.0, 0.6, 0.9) > 0.9


def test_silent_clip_is_not_transcribed():
    # Whisper hallucinates "you" on silence; no_speech_prob is the cue.
    assert _is_no_speech([{"no_speech_prob": 0.94, "avg_logprob": -0.51}])
    assert not _is_no_speech([{"no_speech_prob": 0.09, "avg_logprob": -0.78}])
    # One real segment means the clip is not silent.
    assert not _is_no_speech([
        {"no_speech_prob": 0.95}, {"no_speech_prob": 0.10},
    ])
    # No segments / no signal (other STT models) must not be treated as silence.
    assert not _is_no_speech([])
    assert not _is_no_speech([{"avg_logprob": -0.2}])


def test_profanity_is_masked_in_feedback():
    # Whole words only: "ship"/"class"/"assassin" are ordinary words.
    assert mask_profanity("Shit.") == "****."
    assert mask_profanity("ship") == "ship"
    assert mask_profanity("class assassin") == "class assassin"
    assert mask_profanity("ass") == "***"
    assert mask_profanity("FUCK this") == "**** this"
    assert mask_profanity("") == ""
    assert mask_profanity("shipping") == "shipping"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all confidence self-checks passed")
