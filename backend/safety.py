"""Display-side text safety helpers.

The speech-to-text model can hallucinate or mishear an innocuous word as an
insult (for example "ship" -> "shit"). The raw transcript is still stored in
the local review record, but anything echoed back to the learner goes through
`mask_profanity` first.

Matching is whole-word only, so "class" and "assassin" are untouched.
"""

from __future__ import annotations

import re

PROFANITY: tuple[str, ...] = (
    "ass",
    "asshole",
    "bastard",
    "bitch",
    "cock",
    "cunt",
    "dick",
    "faggot",
    "fuck",
    "nigger",
    "piss",
    "rape",
    "retard",
    "shit",
    "slut",
    "whore",
)

_PATTERN = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(word) for word in PROFANITY) + r")(?!\w)",
    re.IGNORECASE,
)


def mask_profanity(text: str) -> str:
    """Replace whole-word profanity with one asterisk per character."""
    return _PATTERN.sub(lambda match: "*" * len(match.group(0)), text or "")
