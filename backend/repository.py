"""Repository: reads/writes adaptive state into SQLite and applies Bayesian updates.

This is the glue between `db.py` (raw persistence) and `algorithm.py` (the
forgetting model). It exposes typed helpers consumed by the exercise routers.
"""

from __future__ import annotations

import time
import random
from dataclasses import dataclass
from typing import Iterable

import algorithm as alg
from algorithm import ItemState
from data import FONTS, SETS
from db import get_conn, now_iso


@dataclass
class WordRow:
    id: int
    text: str
    phoneme: str | None
    strength: float
    introduced: bool


@dataclass
class FontRow:
    font: str
    strength: float


# ---------------------------------------------------------------------------
# Learners & setup
# ---------------------------------------------------------------------------


def ensure_learner(name: str) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM learners WHERE name=?", (name,)).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO learners(name, created_at) VALUES (?, ?)",
            (name, now_iso()),
        )
        return int(cur.lastrowid)


def list_learners() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM learners ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_learner(learner_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM learners WHERE id=?", (learner_id,)
        ).fetchone()
        return dict(row) if row else None


def seed_word_set(learner_id: int, set_name: str) -> int:
    """Insert a named builtin set's words for a learner. Returns the set id.

    Idempotent: words already present (same learner + text) are skipped.
    """
    if set_name not in SETS:
        raise ValueError(f"Unknown word set: {set_name}")
    with get_conn() as conn:
        set_row = conn.execute(
            "SELECT id FROM word_sets WHERE name=?", (set_name,)
        ).fetchone()
        if set_row:
            set_id = int(set_row["id"])
        else:
            cur = conn.execute(
                "INSERT INTO word_sets(name, source) VALUES (?, 'builtin')",
                (set_name,),
            )
            set_id = int(cur.lastrowid)
        # Words are unique per learner (any set), so skip anything the learner
        # already has even if it came from a different set.
        existing = {
            r["text"]
            for r in conn.execute(
                "SELECT text FROM words WHERE learner_id=?", (learner_id,)
            ).fetchall()
        }
        for text, phoneme in SETS[set_name]:
            if text in existing:
                continue
            conn.execute(
                "INSERT INTO words(learner_id, set_id, text, phoneme, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (learner_id, set_id, text, phoneme, now_iso()),
            )
            existing.add(text)  # guard against duplicates inside one set too
        return set_id


def set_guardian_word_set(learner_id: int, set_name: str) -> None:
    set_id = seed_word_set(learner_id, set_name)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT learner_id FROM guardian_settings WHERE learner_id=?",
            (learner_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE guardian_settings SET word_set_id=?, updated_at=? WHERE learner_id=?",
                (set_id, now_iso(), learner_id),
            )
        else:
            conn.execute(
                "INSERT INTO guardian_settings(learner_id, word_set_id, updated_at) "
                "VALUES (?, ?, ?)",
                (learner_id, set_id, now_iso()),
            )


def update_guardian_settings(
    learner_id: int,
    *,
    interests: str | None = None,
    safety_categories: str | None = None,
    confidence_floor: float | None = None,
    llm_model: str | None = None,
) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM guardian_settings WHERE learner_id=?", (learner_id,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO guardian_settings(learner_id, updated_at) VALUES (?, ?)",
                (learner_id, now_iso()),
            )
            row = conn.execute(
                "SELECT * FROM guardian_settings WHERE learner_id=?", (learner_id,)
            ).fetchone()
        updates, params = [], []
        if interests is not None:
            updates.append("interests=?"); params.append(interests)
        if safety_categories is not None:
            updates.append("safety_categories=?"); params.append(safety_categories)
        if confidence_floor is not None:
            updates.append("confidence_floor=?"); params.append(float(confidence_floor))
        if llm_model is not None:
            updates.append("llm_model=?"); params.append(llm_model.strip() or None)
        updates.append("updated_at=?"); params.append(now_iso())
        params.append(learner_id)
        conn.execute(
            f"UPDATE guardian_settings SET {', '.join(updates)} WHERE learner_id=?",
            params,
        )


def get_guardian_settings(learner_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT g.*, w.name AS word_set FROM guardian_settings g "
            "LEFT JOIN word_sets w ON w.id = g.word_set_id "
            "WHERE g.learner_id=?",
            (learner_id,),
        ).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Word / font state
# ---------------------------------------------------------------------------


def _row_to_state(row) -> ItemState:
    import time as _t
    last = 0.0
    if row["last_reviewed_at"]:
        try:
            from datetime import datetime
            last = _t.mktime(datetime.fromisoformat(row["last_reviewed_at"]).timetuple())
        except ValueError:
            last = 0.0
    keys = set(row.keys())
    return ItemState(
        id=int(row["id"]),
        alpha=float(row["alpha"]),
        beta=float(row["beta"]),
        strength=float(row["strength"]),
        last_reviewed_at=last,
        introduced=bool(row["introduced"]) if "introduced" in keys else True,
    )


def load_word_states(learner_id: int) -> list[ItemState]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM words WHERE learner_id=? ORDER BY id", (learner_id,)
        ).fetchall()
        return [_row_to_state(r) for r in rows]


def load_word(learner_id: int, word_id: int) -> WordRow | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, text, phoneme, strength, introduced FROM words "
            "WHERE learner_id=? AND id=?",
            (learner_id, word_id),
        ).fetchone()
        if not row:
            return None
        return WordRow(
            id=int(row["id"]),
            text=row["text"],
            phoneme=row["phoneme"],
            strength=float(row["strength"]),
            introduced=bool(row["introduced"]),
        )


def load_words_by_ids(learner_id: int, word_ids: Iterable[int]) -> list[WordRow]:
    ids = list(word_ids)
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, text, phoneme, strength, introduced FROM words "
            f"WHERE learner_id=? AND id IN ({placeholders})",
            (learner_id, *ids),
        ).fetchall()
        return [
            WordRow(
                id=int(r["id"]),
                text=r["text"],
                phoneme=r["phoneme"],
                strength=float(r["strength"]),
                introduced=bool(r["introduced"]),
            )
            for r in rows
        ]


def mark_words_introduced(learner_id: int, word_ids: Iterable[int]) -> None:
    ids = list(word_ids)
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    with get_conn() as conn:
        conn.execute(
            f"UPDATE words SET introduced=1 WHERE learner_id=? AND id IN ({placeholders})",
            (learner_id, *ids),
        )


def record_word_review(
    learner_id: int,
    word_id: int,
    exercise: str,
    correct: bool,
    confidence: float,
    response: str | None = None,
) -> float:
    """Apply a Bayesian update to the word and append a review row.

    Returns the new strength.
    """
    now = time.time()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM words WHERE learner_id=? AND id=?", (learner_id, word_id)
        ).fetchone()
        if not row:
            raise ValueError(f"word {word_id} not found for learner {learner_id}")
        state = _row_to_state(row)
        new = alg.update(state, correct, confidence, now)
        conn.execute(
            "UPDATE words SET alpha=?, beta=?, strength=?, last_reviewed_at=?, introduced=1 "
            "WHERE id=?",
            (new.alpha, new.beta, new.strength, now_iso(), word_id),
        )
        conn.execute(
            "INSERT INTO reviews(learner_id, word_id, exercise, correct, confidence, response, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (learner_id, word_id, exercise, int(correct), float(confidence), response, now_iso()),
        )
        return new.strength


def load_font_states(learner_id: int) -> list[ItemState]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM font_state WHERE learner_id=? ORDER BY id", (learner_id,)
        ).fetchall()
        if rows:
            return [_row_to_state(r) for r in rows]
        # First touch: initialize rows for all builtin fonts.
        _init_font_rows(conn, learner_id)
        rows = conn.execute(
            "SELECT * FROM font_state WHERE learner_id=? ORDER BY id", (learner_id,)
        ).fetchall()
        return [_row_to_state(r) for r in rows]


def _init_font_rows(conn, learner_id: int) -> None:
    for f in FONTS:
        conn.execute(
            "INSERT OR IGNORE INTO font_state(learner_id, font, alpha, beta, strength, last_reviewed_at) "
            "VALUES (?, ?, 1.0, 1.0, 0.5, NULL)",
            (learner_id, f),
        )


def record_font_review(
    learner_id: int, font: str, correct: bool, confidence: float
) -> float:
    now = time.time()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM font_state WHERE learner_id=? AND font=?",
            (learner_id, font),
        ).fetchone()
        if not row:
            _init_font_rows(conn, learner_id)
            row = conn.execute(
                "SELECT * FROM font_state WHERE learner_id=? AND font=?",
                (learner_id, font),
            ).fetchone()
            if not row:
                raise ValueError(f"font {font} not initialized for learner {learner_id}")
        state = _row_to_state(row)
        new = alg.update(state, correct, confidence, now)
        conn.execute(
            "UPDATE font_state SET alpha=?, beta=?, strength=?, last_reviewed_at=? "
            "WHERE learner_id=? AND font=?",
            (new.alpha, new.beta, new.strength, now_iso(), learner_id, font),
        )
        return new.strength


def pick_fonts(learner_id: int, n: int, rng: random.Random | None = None) -> list[str]:
    """Pick `n` fonts, favoring weaker ones (adaptive targeting)."""
    states = load_font_states(learner_id)
    if not states:
        return FONTS[:n]
    now = time.time()
    ids = alg.sample_weak_items(states, n, now, temperature=1.5, explore_eps=0.2, rng=rng)
    id_to_font = {s.id: _font_name_by_id(learner_id, s.id) for s in states}
    out = [id_to_font[i] for i in ids if i in id_to_font]
    return out


def _font_name_by_id(learner_id: int, font_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT font FROM font_state WHERE id=?", (font_id,)
        ).fetchone()
        return row["font"] if row else FONTS[0]


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def word_accuracy(learner_id: int, since_days: int = 30) -> float:
    """Mean correctness over recent word reviews."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(correct) AS acc FROM reviews "
            "WHERE learner_id=? AND word_id IS NOT NULL "
            "AND created_at >= datetime('now', ?)",
            (learner_id, f"-{since_days} days"),
        ).fetchone()
        if not row or row["acc"] is None:
            return 0.0
        return float(row["acc"])


def comprehension_accuracy(learner_id: int, since_days: int = 30) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(cr.correct) AS acc "
            "FROM comprehension_results cr "
            "JOIN stories s ON s.id = cr.story_id "
            "WHERE s.learner_id=? AND cr.created_at >= datetime('now', ?)",
            (learner_id, f"-{since_days} days"),
        ).fetchone()
        if not row or row["acc"] is None:
            return 0.0
        return float(row["acc"])


def composite(learner_id: int) -> float:
    return alg.composite_score(word_accuracy(learner_id), comprehension_accuracy(learner_id))


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------


def save_story(learner_id: int, text: str, word_ids: list[int]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO stories(learner_id, text, word_ids, created_at) VALUES (?, ?, ?, ?)",
            (learner_id, text, ",".join(map(str, word_ids)), now_iso()),
        )
        return int(cur.lastrowid)


def save_comprehension_result(
    story_id: int, question: str, expected: str, given: str, correct: bool
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO comprehension_results(story_id, question, expected, given, correct, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (story_id, question, expected, given, int(correct), now_iso()),
        )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def start_session(learner_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions(learner_id, started_at) VALUES (?, ?)",
            (learner_id, now_iso()),
        )
        return int(cur.lastrowid)


def end_session(session_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?", (now_iso(), session_id)
        )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def _streak_from_dates(dates: list[str]) -> tuple[int, bool]:
    """Count consecutive practice days ending today (or yesterday if none today).

    `dates` is distinct "YYYY-MM-DD" strings, newest first.
    """
    from datetime import datetime, timedelta
    if not dates:
        return 0, False
    today = datetime.utcnow().date()
    latest = datetime.strptime(dates[0], "%Y-%m-%d").date()
    practiced_today = latest == today
    anchor = today if practiced_today else today - timedelta(days=1)
    if latest != anchor:
        return 0, practiced_today
    count = 0
    for d in dates:
        if datetime.strptime(d, "%Y-%m-%d").date() == anchor:
            count += 1
            anchor -= timedelta(days=1)
        else:
            break
    return count, practiced_today


# XP weights, defined once so the dashboard, the daily status and the summary
# screen all agree. An attempt is worth something (effort), a correct answer
# more, and a comprehension answer most (it is the hardest task).
_XP_ATTEMPT = 10
_XP_CORRECT = 5
_XP_COMPREHENSION = 20


def _xp(attempts: int, correct: int, comp_correct: int) -> int:
    return _XP_ATTEMPT * attempts + _XP_CORRECT * correct + _XP_COMPREHENSION * comp_correct


def level_info(xp: int) -> dict:
    """Level curve: level n starts at 50·n·(n-1) XP (0, 100, 300, 600, 1000…)."""
    level = 1
    while 50 * level * (level + 1) <= xp:
        level += 1
    start = 50 * (level - 1) * level
    nxt = 50 * level * (level + 1)
    return {
        "xp": xp,
        "level": level,
        "level_start": start,
        "level_next": nxt,
        "level_progress": round((xp - start) / (nxt - start), 3),
    }


def _xp_today(conn, learner_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(correct), 0) AS c FROM reviews "
        "WHERE learner_id=? AND exercise != 'exercise-5-exposure' "
        "AND DATE(created_at) = DATE('now')",
        (learner_id,),
    ).fetchone()
    comp = conn.execute(
        "SELECT COALESCE(SUM(cr.correct), 0) AS c "
        "FROM comprehension_results cr JOIN stories s ON s.id = cr.story_id "
        "WHERE s.learner_id=? AND DATE(cr.created_at) = DATE('now')",
        (learner_id,),
    ).fetchone()
    return _xp(int(row["n"]), int(row["c"]), int(comp["c"]))


def _xp_total(conn, learner_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(correct), 0) AS c FROM reviews "
        "WHERE learner_id=? AND exercise != 'exercise-5-exposure'",
        (learner_id,),
    ).fetchone()
    comp = conn.execute(
        "SELECT COALESCE(SUM(cr.correct), 0) AS c "
        "FROM comprehension_results cr JOIN stories s ON s.id = cr.story_id "
        "WHERE s.learner_id=?",
        (learner_id,),
    ).fetchone()
    return _xp(int(row["n"]), int(row["c"]), int(comp["c"]))


def _quests(reviews: int, correct: int, session_done: bool) -> list[dict]:
    """Daily quests, all derived from real activity (never invented progress)."""
    return [
        {
            "key": "items", "emoji": "⚡", "label": "Answer 20 practice items",
            "target": 20, "progress": min(reviews, 20), "done": reviews >= 20,
        },
        {
            "key": "correct", "emoji": "🎯", "label": "Get 10 answers right",
            "target": 10, "progress": min(correct, 10), "done": correct >= 10,
        },
        {
            "key": "session", "emoji": "🏁", "label": "Finish today's session",
            "target": 1, "progress": 1 if session_done else 0, "done": session_done,
        },
    ]


def learner_dashboard(learner_id: int) -> dict | None:
    """Aggregate progress snapshot: streak, abilities, word tiers, XP and quests."""
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM learners WHERE id=?", (learner_id,)
        ).fetchone():
            return None

        # Streak: distinct practice dates, newest first.
        dates = [
            r["d"]
            for r in conn.execute(
                "SELECT DISTINCT DATE(created_at) AS d FROM reviews "
                "WHERE learner_id=? ORDER BY d DESC",
                (learner_id,),
            ).fetchall()
        ]
        streak_days, practiced_today = _streak_from_dates(dates)

        # Abilities: group reviews by exercise (exclude exposure — always correct).
        ex_rows = conn.execute(
            "SELECT exercise, AVG(correct) AS acc, COUNT(*) AS n FROM reviews "
            "WHERE learner_id=? AND exercise != 'exercise-5-exposure' "
            "GROUP BY exercise",
            (learner_id,),
        ).fetchall()
        by_ex = {r["exercise"]: (r["acc"], r["n"]) for r in ex_rows}
        comp = conn.execute(
            "SELECT AVG(cr.correct) AS acc, COUNT(*) AS n "
            "FROM comprehension_results cr "
            "JOIN stories s ON s.id = cr.story_id "
            "WHERE s.learner_id=?",
            (learner_id,),
        ).fetchone()

        # Today's activity feeds the quest list; exposure rows don't count.
        today = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(correct), 0) AS c FROM reviews "
            "WHERE learner_id=? AND exercise != 'exercise-5-exposure' "
            "AND DATE(created_at) = DATE('now')",
            (learner_id,),
        ).fetchone()

        def _ability(key, label, emoji, acc, n):
            n = int(n or 0)
            return {
                "key": key,
                "label": label,
                "emoji": emoji,
                "accuracy": round(float(acc), 3) if acc is not None and n > 0 else None,
                "attempts": n,
            }

        sp = by_ex.get("exercise-1", (None, 0))
        st = by_ex.get("exercise-3-spell", (None, 0))
        re = by_ex.get("exercise-3-categorize", (None, 0))
        abilities = [
            _ability("speaking", "Speaking", "🗣️", sp[0], sp[1]),
            _ability("spelling", "Spelling", "✏️", st[0], st[1]),
            _ability("recognition", "Recognition", "👂", re[0], re[1]),
            _ability("comprehension", "Comprehension", "📖", comp["acc"], comp["n"]),
        ]

        # Word tiers: mastery = alpha / (alpha + beta). Each word carries its
        # supplementary info so the frontend can render a searchable word list.
        tiers: dict[str, list[dict]] = {
            "mastered": [], "familiar": [], "learning": [], "new": [],
        }
        for r in conn.execute(
            "SELECT w.id, w.text, w.phoneme, w.alpha, w.beta, w.last_reviewed_at, "
            "(SELECT COUNT(*) FROM reviews rv WHERE rv.word_id = w.id) AS n "
            "FROM words w WHERE w.learner_id=?",
            (learner_id,),
        ).fetchall():
            a, b = float(r["alpha"]), float(r["beta"])
            m = a / (a + b) if (a + b) > 0 else 0.0
            info = {
                "text": r["text"],
                "phoneme": r["phoneme"],
                "mastery": round(m, 3),
                "attempts": int(r["n"]),
                "last": (r["last_reviewed_at"] or "")[:10] or None,
            }
            if r["last_reviewed_at"] is None:
                tiers["new"].append(info)
            elif m > 0.85:
                tiers["mastered"].append(info)
            elif m >= 0.65:
                tiers["familiar"].append(info)
            else:
                tiers["learning"].append(info)
        for k in tiers:
            tiers[k].sort(key=lambda w: w["text"])
        word_tiers = [
            {"key": k, "label": k.capitalize(), "words": tiers[k]}
            for k in ("mastered", "familiar", "learning", "new")
        ]

        return {
            "streak": {"days": streak_days, "practiced_today": practiced_today},
            "abilities": abilities,
            "word_tiers": word_tiers,
            **level_info(_xp_total(conn, learner_id)),
            "today": {
                "reviews": int(today["n"]),
                "correct": int(today["c"]),
                "xp": _xp_today(conn, learner_id),
            },
            "quests": _quests(
                int(today["n"]), int(today["c"]),
                session_done=conn.execute(
                    "SELECT 1 FROM daily_completions WHERE learner_id=? AND date=?",
                    (learner_id, _today_utc()),
                ).fetchone() is not None,
            ),
        }


# ---------------------------------------------------------------------------
# Daily sessions & admin tools
# ---------------------------------------------------------------------------

def _today_utc() -> str:
    from datetime import datetime
    return datetime.utcnow().date().isoformat()


def daily_status(learner_id: int) -> dict:
    """Whether the learner has completed (or skipped) today's session, UTC dates."""
    today = _today_utc()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT skipped FROM daily_completions WHERE learner_id=? AND date=?",
            (learner_id, today),
        ).fetchone()
        xp_today = _xp_today(conn, learner_id)
    return {
        "date": today,
        "completed": row is not None,
        "skipped": bool(row["skipped"]) if row else False,
        "xp_today": xp_today,
    }


def mark_daily_complete(learner_id: int) -> None:
    """First write wins: an existing skipped row is not flipped back."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO daily_completions (learner_id, date, skipped, created_at) "
            "VALUES (?, ?, 0, ?)",
            (learner_id, _today_utc(), now_iso()),
        )


def mark_daily_skipped(learner_id: int) -> None:
    """Admin demo action: today counts as done, flagged skipped."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO daily_completions (learner_id, date, skipped, created_at) "
            "VALUES (?, ?, 1, ?) "
            "ON CONFLICT(learner_id, date) DO UPDATE SET skipped=1",
            (learner_id, _today_utc(), now_iso()),
        )


def reset_daily(learner_id: int) -> None:
    """Admin demo action: forget today's completion so the session can re-run."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM daily_completions WHERE learner_id=? AND date=?",
            (learner_id, _today_utc()),
        )


def _get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else None


def _set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def verify_admin_password(password: str) -> bool:
    """Constant-time check; seeds the stored hash from config on first use."""
    import hashlib
    import hmac

    from config import settings

    stored = _get_setting("admin_password_sha256")
    if stored is None:
        stored = hashlib.sha256(settings.admin_password.encode()).hexdigest()
        _set_setting("admin_password_sha256", stored)
    given = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(given, stored)


def set_admin_password(password: str) -> None:
    import hashlib

    _set_setting("admin_password_sha256", hashlib.sha256(password.encode()).hexdigest())
