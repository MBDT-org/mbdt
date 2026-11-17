import type { Dashboard, DailyStatus } from '../api';
import { ProgressBar } from './ui';

/** The four activities in today's session, in play order. Kept in sync with
    DailySession's STAGES (same keys and order). */
const PATH_STAGES = [
  { key: 'ex1', label: 'Say the word', emoji: '🗣️', hint: '12 words' },
  { key: 'ex3spell', label: 'Spell from sound', emoji: '✍️', hint: '8 words' },
  { key: 'ex3cat', label: 'Sort by sound', emoji: '👂', hint: '2 rounds' },
  { key: 'ex5', label: 'Read a story', emoji: '📖', hint: '1 story' },
] as const;

export type PathStageIndex = 0 | 1 | 2 | 3;

/* ---- Status HUD pieces (header) ---------------------------------------- */

/** Circular level badge: number inside a progress ring toward the next level. */
export function LevelBadge({ data }: { data: Dashboard | null }) {
  const level = data?.level ?? 1;
  const progress = data?.level_progress ?? 0;
  const r = 15;
  const c = 2 * Math.PI * r;
  return (
    <span
      className="level-badge"
      title={
        data
          ? `Level ${level} · ${data.xp} XP (${Math.max(0, data.level_next - data.xp)} XP to level ${level + 1})`
          : 'Level'
      }
    >
      <svg viewBox="0 0 40 40" aria-hidden className="level-ring">
        <circle cx="20" cy="20" r={r} className="level-ring-track" />
        <circle
          cx="20" cy="20" r={r}
          className="level-ring-fill"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.min(1, Math.max(0, progress)))}
        />
      </svg>
      <span className="level-num">{level}</span>
      <span className="sr-only">Level {level}</span>
    </span>
  );
}

/** XP counter chip. `key` in the caller re-mounts it so the pop replays. */
export function XpPill({ xp }: { xp: number }) {
  return (
    <span className="xp-pill" title={`${xp} XP earned`}>
      <span className="xp-bolt" aria-hidden>⚡</span>
      <strong>{xp.toLocaleString()}</strong>
      <span className="sr-only">XP</span>
    </span>
  );
}

/** Level progress toward the next level, shown in the home header row. */
export function LevelProgress({ data }: { data: Dashboard | null }) {
  const level = data?.level ?? 1;
  const xp = data?.xp ?? 0;
  const pct = Math.round(Math.min(1, Math.max(0, data?.level_progress ?? 0)) * 100);
  const toNext = Math.max(0, (data?.level_next ?? 0) - xp);
  return (
    <div className="level-progress">
      <div className="level-progress-head">
        <span className="level-progress-badge">Level {level}</span>
        <span className="muted">
          {toNext > 0 ? `${toNext} XP to level ${level + 1}` : 'Max level'}
        </span>
      </div>
      <ProgressBar value={pct} max={100} label={`Level ${level} progress`} className="level-progress-bar" />
      <span className="muted level-progress-xp">{xp.toLocaleString()} XP total</span>
    </div>
  );
}

/* ---- Home: the lesson path --------------------------------------------- */

export function HomePath({ daily, onStart }: {
  daily: DailyStatus | null;
  onStart: (stage: PathStageIndex) => void;
}) {
  const done = daily?.completed ?? false;
  const current = done ? -1 : 0;

  return (
    <section className="path-card" aria-label="Today's practice">
      <header className="unit-band">
        <div className="unit-band-text">
          <span className="unit-kicker">Unit 1</span>
          <h2>Today&apos;s practice</h2>
          <span className="unit-sub">
            {done ? 'All four done — nice work!' : 'Speaking · spelling · sounds · reading'}
          </span>
        </div>
        <span className={`unit-badge${done ? ' is-done' : ''}`} aria-hidden>
          {done ? '✓' : '★'}
        </span>
      </header>

      <nav className="path">
        {PATH_STAGES.map((s, i) => {
          const state = done ? 'is-done' : i === current ? 'is-current' : 'is-todo';
          return (
            <div className={`path-step ${i % 2 ? 'is-right' : 'is-left'} ${state}`} key={s.key}>
              {i === current && <span className="path-bubble" aria-hidden>START</span>}
              <button
                className="path-node"
                onClick={() => onStart(i as PathStageIndex)}
                aria-label={`Part ${i + 1} of 4: ${s.label} (${s.hint})`}
              >
                <span className="path-node-emoji" aria-hidden>{s.emoji}</span>
                {done && <span className="path-check" aria-hidden>✓</span>}
              </button>
              <span className="path-node-label">
                {s.label}
                <small>{s.hint}</small>
              </span>
            </div>
          );
        })}
      </nav>

      <button className="btn primary btn-lg path-cta" onClick={() => onStart(0)}>
        {done ? 'Practice again' : 'Start practice'}
      </button>
    </section>
  );
}

/* ---- Home rail: quests + mastery --------------------------------------- */

export function QuestsCard({ data }: { data: Dashboard | null }) {
  const quests = data?.quests ?? [];
  return (
    <section className="card rail-card">
      <header className="rail-head">
        <h3>Daily quests</h3>
        <span className="rail-emoji" aria-hidden>🎁</span>
      </header>
      <ul className="quest-list">
        {quests.map(q => (
          <li className={`quest${q.done ? ' is-done' : ''}`} key={q.key}>
            <span className="quest-emoji" aria-hidden>{q.done ? '✅' : q.emoji}</span>
            <div className="quest-main">
              <span className="quest-label">{q.label}</span>
              <ProgressBar
                value={q.progress}
                max={q.target}
                label={q.label}
                className="quest-bar"
              />
            </div>
            <span className="quest-count">{q.progress}/{q.target}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MasteryCard({ data }: { data: Dashboard | null }) {
  const tiers = data?.word_tiers ?? [];
  const byTier = Object.fromEntries(tiers.map(t => [t.key, t.words.length]));
  const total = tiers.reduce((n, t) => n + t.words.length, 0);
  const mastered = byTier.mastered ?? 0;
  const pct = total > 0 ? mastered / total : 0;

  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <section className="card rail-card mastery-card">
      <div className="mastery-ring-wrap">
        <svg viewBox="0 0 64 64" aria-hidden className="mastery-ring">
          <circle cx="32" cy="32" r={r} className="level-ring-track" />
          <circle
            cx="32" cy="32" r={r}
            className="mastery-ring-fill"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - pct)}
          />
        </svg>
        <span className="mastery-pct">{Math.round(pct * 100)}%</span>
      </div>
      <div className="mastery-text">
        <h3>Words mastered</h3>
        <p className="muted">{mastered} of {total || '—'} words are solid.</p>
        <div className="mastery-chips">
          <span className="tag mint">{byTier.mastered ?? 0} mastered</span>
          <span className="tag amber">{byTier.learning ?? 0} learning</span>
          <span className="tag sky">{byTier.new ?? 0} new</span>
        </div>
      </div>
    </section>
  );
}
