"""Adaptive Bayesian forgetting engine.

Each learnable item (a word, a font, a phoneme bucket) carries a Beta(alpha,
beta) posterior over its immediate-recall success rate. The posterior mean is
the item's `strength`. A time-decay term models forgetting: the half-life grows
with mastery, so well-known words stay fresh longer while fragile words are
re-prioritized quickly.

Selection ("surgically target weak spots") samples items proportional to their
forgetting-adjusted need, with an exploration term and a path for introducing
new words once the active pool is mostly mastered. This is the evolutionary
targeting described in the plan, implemented as a Thompson-flavoured weighted
sampler rather than a literal genetic algorithm.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

import numpy as np

# Half-life bounds (days). A fresh word (strength 0.5) -> ~7.5 day half-life;
# a mastered word (strength ~1) -> ~14.5 days.
_MIN_HALF_LIFE = 0.5
_HALF_LIFE_SPAN = 14.0


@dataclass
class ItemState:
    id: int
    alpha: float
    beta: float
    strength: float
    last_reviewed_at: float  # epoch seconds, 0 if never
    introduced: bool = True

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def half_life_days(self) -> float:
        return _MIN_HALF_LIFE + _HALF_LIFE_SPAN * clamp01(self.strength)

    def effective_recall(self, now_epoch: float) -> float:
        """Posterior recall probability after forgetting since last review."""
        base = self.mean
        if self.last_reviewed_at <= 0:
            return base
        days = max(0.0, (now_epoch - self.last_reviewed_at) / 86400.0)
        return base * math.exp(-days / self.half_life_days())


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def success_score(correct: bool, confidence: float) -> float:
    """Map a binary outcome + confidence in [0,1] to a Beta update mass in [0,1]."""
    confidence = clamp01(confidence)
    return clamp01(confidence if correct else (1.0 - confidence) * 0.5)


def update(state: ItemState, correct: bool, confidence: float, now_epoch: float) -> ItemState:
    """Return a new ItemState after a single review trial."""
    s = success_score(correct, confidence)
    alpha = state.alpha + s
    beta = state.beta + (1.0 - s)
    strength = alpha / (alpha + beta)
    return ItemState(
        id=state.id,
        alpha=alpha,
        beta=beta,
        strength=strength,
        last_reviewed_at=now_epoch,
        introduced=True,
    )


def sample_weak_items(
    states: Sequence[ItemState],
    n: int,
    now_epoch: float,
    temperature: float = 2.5,
    explore_eps: float = 0.15,
    introduce_when_mean_above: float = 0.8,
    rng: random.Random | None = None,
) -> list[int]:
    """Pick `n` item ids, favoring high-need (weak / forgotten) items.

    A fraction of slots may be reserved for unintroduced items once the active
    pool is largely mastered, so the learner keeps progressing.
    """
    rng = rng or random
    if not states:
        return []
    n = min(n, len(states))

    recalls = [s.effective_recall(now_epoch) for s in states]
    introduced = [s.introduced for s in states]
    mean_recall = np.mean(recalls)

    need = np.array([1.0 - r for r in recalls], dtype=float)
    # Reservior for new words when the pool is strong.
    new_ids = [s.id for s, intro in zip(states, introduced) if not intro]
    n_intro = 0
    if new_ids and mean_recall > introduce_when_mean_above:
        n_intro = min(len(new_ids), max(1, int(round(n * 0.3))))

    remaining = n - n_intro
    pool_ids: list[int] = []
    pool_need = need
    candidate_ids = [s.id for s in states]
    if n_intro:
        chosen_new = rng.sample(new_ids, n_intro)
        pool_ids.extend(chosen_new)
        keep = [i for i, sid in enumerate(candidate_ids) if sid not in chosen_new]
        candidate_ids = [candidate_ids[i] for i in keep]
        pool_need = need[keep]

    # Weighted sampling without replacement from the remaining pool.
    weights = np.power(pool_need, temperature)
    if weights.sum() == 0:
        weights = np.ones_like(weights)
    probs = weights / weights.sum()

    # Exploration: with prob eps, pick uniformly instead of by need.
    chosen: list[int] = []
    avail = list(range(len(candidate_ids)))
    av_probs = list(probs)
    while len(chosen) < remaining and avail:
        if rng.random() < explore_eps:
            idx_pos = rng.randrange(len(avail))
        else:
            idx_pos = _sample_index(av_probs)
        chosen.append(candidate_ids[avail.pop(idx_pos)])
        av_probs.pop(idx_pos)
        s = sum(av_probs)
        if s > 0:
            av_probs = [p / s for p in av_probs]
        elif av_probs:
            # Pool exhausted -> loop exits; all-zero probs -> uniform fallback.
            av_probs = [1.0 / len(av_probs)] * len(av_probs)

    pool_ids.extend(chosen)
    rng.shuffle(pool_ids)
    return pool_ids


def _sample_index(probs: Sequence[float]) -> int:
    arr = np.array(probs, dtype=float)
    if arr.sum() == 0:
        arr = np.ones_like(arr)
    arr = arr / arr.sum()
    return int(np.random.choice(len(arr), p=arr))


def softmax_pick(scores: Sequence[float], temperature: float, rng: random.Random | None = None) -> int:
    """Pick an index by softmax over scores (higher = more likely)."""
    rng = rng or random
    arr = np.array(scores, dtype=float)
    arr = arr - arr.max()
    exp = np.exp(arr / max(1e-6, temperature))
    probs = exp / exp.sum()
    return int(rng.choices(range(len(arr)), weights=probs.tolist(), k=1)[0])


def composite_score(word_accuracy: float, comprehension_accuracy: float) -> float:
    """Unified 0-100 performance metric aggregating word + comprehension accuracy."""
    return round(100.0 * clamp01(0.5 * word_accuracy + 0.5 * comprehension_accuracy), 1)
