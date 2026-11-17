"""SQLite persistence for MBDT.

All learner data stays strictly local (a single file). The schema stores the
per-word / per-font / per-phoneme Bayesian state used by the adaptive engine,
plus a complete review log for auditability and composite-score computation.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS word_sets (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'builtin'
);

CREATE TABLE IF NOT EXISTS words (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id        INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    set_id            INTEGER REFERENCES word_sets(id) ON DELETE SET NULL,
    text              TEXT NOT NULL,
    phoneme           TEXT,
    alpha             REAL NOT NULL DEFAULT 1.0,
    beta              REAL NOT NULL DEFAULT 1.0,
    strength          REAL NOT NULL DEFAULT 0.5,
    last_reviewed_at  TEXT,
    introduced        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    UNIQUE(learner_id, text)
);

CREATE TABLE IF NOT EXISTS font_state (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id        INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    font              TEXT NOT NULL,
    alpha             REAL NOT NULL DEFAULT 1.0,
    beta              REAL NOT NULL DEFAULT 1.0,
    strength          REAL NOT NULL DEFAULT 0.5,
    last_reviewed_at  TEXT,
    UNIQUE(learner_id, font)
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    word_id     INTEGER REFERENCES words(id) ON DELETE SET NULL,
    exercise    TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    confidence  REAL NOT NULL DEFAULT 0.0,
    response    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    word_ids    TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comprehension_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id    INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    expected    TEXT NOT NULL,
    given       TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guardian_settings (
    learner_id        INTEGER PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
    word_set_id       INTEGER REFERENCES word_sets(id),
    interests         TEXT NOT NULL DEFAULT '',
    safety_categories TEXT NOT NULL DEFAULT '',
    confidence_floor  REAL NOT NULL DEFAULT 0.6,
    llm_model         TEXT,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    started_at  TEXT NOT NULL,
    ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS daily_completions (
    learner_id  INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    skipped     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (learner_id, date)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_words_learner ON words(learner_id);
CREATE INDEX IF NOT EXISTS idx_reviews_learner_time ON reviews(learner_id, created_at);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Inline migration for existing DBs; drop when DBs are recreated
        try:
            conn.execute("ALTER TABLE guardian_settings ADD COLUMN llm_model TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # US spelling migration: older rows used the British stage key.
        conn.execute(
            "UPDATE reviews SET exercise='exercise-3-categorize' "
            "WHERE exercise='exercise-3-categorise'"
        )
        conn.commit()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")
