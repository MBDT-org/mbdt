import { useEffect, useMemo, useState } from 'react';
import { api, ApiError } from '../api';
import type { Dashboard as DashboardData, Ability, DailyStatus, WordTier, WordInfo, WordSetInfo, Health, Learner } from '../api';
import { Banner, BtnSpinner, Card, Select, Skeleton, Toggle } from './ui';
import { celebrationsEnabled, setCelebrationsEnabled } from '../celebrations';
import { getAdminPw, isUnlocked, unlock } from '../admin';

// Ability key -> color tone class (semantic, fixed per ability).
const ABILITY_TONE: Record<Ability['key'], string> = {
  speaking: 'mint',
  spelling: 'sky',
  recognition: 'amber',
  comprehension: 'lilac',
};

export function StreakFlame({ days }: { days: number }) {
  const cold = days <= 0;
  return (
    <div className={`streak ${cold ? 'streak-cold' : ''}`} title={cold ? 'No streak yet' : `${days}-day streak`}>
      <span className={`flame ${cold ? 'flame-off' : ''}`} aria-hidden />
      <strong className="streak-count">{days}</strong>
    </div>
  );
}

export function ProgressCard({ data }: { data: DashboardData | null }) {
  return (
    <Card className="rail-card progress-card">
      <div className="rail-head">
        <h3>Progress</h3>
        <span className="rail-emoji" aria-hidden>📊</span>
      </div>
      {data ? <ProgressChart data={data} /> : <Skeleton className="skeleton-block" />}
    </Card>
  );
}

export function WordsCard({ data }: { data: DashboardData | null }) {
  return (
    <Card className="rail-card words-card">
      <div className="rail-head">
        <h3>Words</h3>
        <span className="rail-emoji" aria-hidden>📚</span>
      </div>
      {data ? <WordsPanel data={data} /> : <Skeleton className="skeleton-block" />}
    </Card>
  );
}

/* ---- Tab 1: abilities as a vertical bar chart --------------------------- */

const Y_TICKS = [100, 75, 50, 25, 0];
const GOAL_PCT = 85;

function ProgressChart({ data }: { data: DashboardData }) {
  return (
    <div className="progress-chart">
      <div className="ability-chart">
        <div className="chart-body">
          <div className="chart-y" aria-hidden>
            {Y_TICKS.map(t => <span key={t}>{t}</span>)}
          </div>
          <div className="chart-plot">
            <div className="chart-goal" style={{ bottom: `${GOAL_PCT}%` }}>
              <span className="chart-goal-label">goal</span>
            </div>
            <div className="chart-bars">
              {data.abilities.map(a => <AbilityBar key={a.key} ability={a} />)}
            </div>
          </div>
        </div>
        <div className="chart-caps">
          {data.abilities.map(a => (
            <span key={a.key} className={`chart-cap${a.attempts ? '' : ' muted'}`}>
              <span aria-hidden>{a.emoji}</span><br />
              {a.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function AbilityBar({ ability }: { ability: Ability }) {
  const practiced = ability.attempts > 0 && ability.accuracy != null;
  const pct = practiced ? Math.round(ability.accuracy! * 100) : 0;
  return (
    <div
      className="chart-col"
      title={practiced ? `${ability.label}: ${pct}% over ${ability.attempts} tries` : `${ability.label}: not practiced yet`}
    >
      <span className={`chart-val${practiced ? '' : ' muted'}`}>
        {practiced ? `${pct}%` : 'not yet'}
      </span>
      {practiced && (
        <span
          className={`chart-bar ${ABILITY_TONE[ability.key]}`}
          style={{ height: `${pct}%` }}
          role="progressbar"
          aria-orientation="vertical"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label={ability.label}
        />
      )}
    </div>
  );
}

/* ---- Tab 2: searchable word list ---------------------------------------- */

const TIER_META: Record<WordTier['key'], { emoji: string; tone: string }> = {
  mastered: { emoji: '🏆', tone: 'mint' },
  familiar: { emoji: '😊', tone: 'sky' },
  learning: { emoji: '🌱', tone: 'amber' },
  new: { emoji: '💤', tone: 'ghost' },
};

interface WordRow {
  info: WordInfo;
  tier: WordTier['key'];
}

function lastLabel(iso: string | null): string {
  if (!iso) return 'not practiced yet';
  const days = Math.floor((Date.now() - new Date(`${iso}T00:00:00`).getTime()) / 86400000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days}d ago`;
}

function WordsPanel({ data }: { data: DashboardData }) {
  const [query, setQuery] = useState('');
  const [tierFilter, setTierFilter] = useState<WordTier['key'] | 'all'>('all');

  const rows = useMemo<WordRow[]>(() => {
    const flat = data.word_tiers.flatMap(t =>
      t.words.map(info => ({ info, tier: t.key as WordTier['key'] })),
    );
    return flat.sort((a, b) => a.info.text.localeCompare(b.info.text));
  }, [data]);

  const q = query.trim().toLowerCase();
  const filtered = rows.filter(r =>
    (tierFilter === 'all' || r.tier === tierFilter) &&
    (!q || r.info.text.toLowerCase().includes(q)),
  );

  if (rows.length === 0) {
    return <p className="muted">Words will appear here once a word set is chosen.</p>;
  }

  return (
    <div className="stack-sm">
      <div className="words-toolbar">
        <input
          className="input words-search"
          type="search"
          placeholder="Search words..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          aria-label="Search words"
        />
        <div className="filter-chips" role="group" aria-label="Filter by level">
          <button
            className={`filter-chip${tierFilter === 'all' ? ' is-active' : ''}`}
            onClick={() => setTierFilter('all')}
          >
            All <span className="chip-n">{rows.length}</span>
          </button>
          {data.word_tiers.map(t => (
            <button
              key={t.key}
              className={`filter-chip ${TIER_META[t.key].tone}${tierFilter === t.key ? ' is-active' : ''}`}
              onClick={() => setTierFilter(tierFilter === t.key ? 'all' : t.key)}
            >
              {TIER_META[t.key].emoji} {t.label} <span className="chip-n">{t.words.length}</span>
            </button>
          ))}
        </div>
      </div>

      <p className="muted words-count">
        Showing {filtered.length} of {rows.length} words
      </p>

      {filtered.length === 0 ? (
        <p className="muted center-text words-empty">
          {q ? `No words match "${query.trim()}".` : 'No words in this level yet.'}
        </p>
      ) : (
        <div className="word-list">
          {filtered.map(r => <WordListRow key={r.info.text} row={r} />)}
        </div>
      )}
    </div>
  );
}

function WordListRow({ row }: { row: WordRow }) {
  const { info, tier } = row;
  const { tone } = TIER_META[tier];
  const pct = Math.round(info.mastery * 100);
  const isNew = tier === 'new';
  return (
    <div className="word-row">
      <div className="word-main">
        <span className="word-text">{info.text}</span>
        {info.phoneme && <span className="word-phon">{info.phoneme}</span>}
      </div>
      <div className="word-stats">
        {isNew ? (
          <span>not practiced yet</span>
        ) : (
          <>
            <span>
              <strong className="word-pct">{pct}%</strong>
              {' · '}
              {info.attempts} {info.attempts === 1 ? 'try' : 'tries'}
            </span>
            <span>{lastLabel(info.last)}</span>
          </>
        )}
      </div>
      <span
        className="word-vbar"
        title={isNew ? 'Not practiced yet' : `${pct}% mastery`}
        aria-hidden
      >
        {!isNew && <span className={tone} style={{ height: `${Math.max(pct, 6)}%` }} />}
      </span>
      <span className={`tag tag-mini ${tone} word-tier-tag`}>
        {TIER_META[tier].emoji} {tier}
      </span>
    </div>
  );
}

/* ---- Tab 3: guardian settings ------------------------------------------- */

export function GuardianTab({ learnerId, health, onChanged }: {
  learnerId: number;
  health: Health | null;
  onChanged: () => void;
}) {
  const [learner, setLearner] = useState<Learner | null>(null);
  const [sets, setSets] = useState<WordSetInfo[]>([]);
  const [interests, setInterests] = useState('');
  const [safety, setSafety] = useState('');
  const [wordSet, setWordSet] = useState('');
  const [model, setModel] = useState('');
  const [floor, setFloor] = useState(0.6);
  const [celebrate, setCelebrate] = useState(celebrationsEnabled);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;
    void (async () => {
      const [l, s] = await Promise.all([api.getLearner(learnerId), api.listWordSets()]);
      if (canceled) return;
      setLearner(l); setSets(s.sets);
      setInterests(l.guardian?.interests ?? '');
      setSafety(l.guardian?.safety_categories ?? '');
      setModel(l.guardian?.llm_model ?? '');
      setFloor(l.guardian?.confidence_floor ?? 0.6);
      setWordSet(l.guardian?.word_set ?? s.sets[0]?.id ?? '');
    })();
    return () => { canceled = true; };
  }, [learnerId]);

  async function save() {
    setBusy(true); setMsg(null);
    try {
      await api.updateGuardian(learnerId, {
        word_set: wordSet || undefined,
        interests,
        safety_categories: safety,
        confidence_floor: floor,
        llm_model: model, // empty string clears the override server-side
      });
      setMsg('Saved.');
      onChanged();
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  }

  if (!learner) {
    return (
      <div className="stack" aria-busy="true" aria-label="Loading guardian settings">
        <Skeleton className="skeleton-field" />
        <Skeleton className="skeleton-field" />
        <Skeleton className="skeleton-field" />
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="field">
        <label className="field-label" htmlFor="g-set">Word set</label>
        <Select
          id="g-set"
          value={wordSet}
          options={sets.map(s => ({ value: s.id, label: s.label }))}
          onChange={setWordSet}
        />
        <span className="muted field-hint">
          Adds the set&apos;s words to the learner&apos;s list; words already practiced stay.
        </span>
      </div>
      <div className="field">
        <label className="field-label" htmlFor="g-int">Interests (comma-separated)</label>
        <input id="g-int" className="input"
          value={interests} onChange={e => setInterests(e.target.value)}
          placeholder="cats, space, dinosaurs" />
        <span className="muted field-hint">Story themes the child likes.</span>
      </div>
      <div className="field">
        <label className="field-label" htmlFor="g-model">Story model (LLM override)</label>
        <input id="g-model" className="input"
          value={model} onChange={e => setModel(e.target.value)}
          placeholder={health ? `Default: ${health.models.llm}` : 'provider/model'} />
        <span className="muted field-hint">
          Leave empty for the server default. The model must be available to your
          gateway API key.
        </span>
      </div>
      <div className="field">
        <label className="field-label" htmlFor="g-safety">Story topics to avoid (comma-separated)</label>
        <input id="g-safety" className="input"
          value={safety} onChange={e => setSafety(e.target.value)}
          placeholder="dogs, the dark" />
      </div>
      <div className="field">
        <label className="field-label" htmlFor="g-floor">
          Confidence floor: <strong>{Math.round(floor * 100)}%</strong>
        </label>
        <input id="g-floor" type="range" min={0.4} max={0.95} step={0.05}
          className="range-input"
          value={floor} onChange={e => setFloor(parseFloat(e.target.value))} />
      </div>
      <div className="field">
        <Toggle
          id="g-celebrate"
          label="Celebration confetti"
          hint="Show a confetti burst on correct answers and finished rounds."
          checked={celebrate}
          onChange={v => { setCelebrate(v); setCelebrationsEnabled(v); }}
        />
      </div>
      <div className="row">
        <button className="btn primary" onClick={save} disabled={busy}>
          {busy && <BtnSpinner />}
          {busy ? 'Saving…' : 'Save settings'}
        </button>
        {msg && <span className="muted">{msg}</span>}
      </div>
    </div>
  );
}

/* ---- Tab 4: admin / demo tools -------------------------------------------- */

export function AdminTab({ learnerId, daily, health, onChanged }: {
  learnerId: number;
  daily: DailyStatus | null;
  health: Health | null;
  onChanged: () => void;
}) {
  const [unlocked, setUnlocked] = useState(isUnlocked());
  const [pw, setPw] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [pwMsg, setPwMsg] = useState<string | null>(null);

  async function submitUnlock(e: React.FormEvent) {
    e.preventDefault();
    if (!pw || busy) return;
    setBusy(true); setErr(null);
    try {
      await api.adminVerify(pw);
      unlock(pw);
      setUnlocked(true);
      setPw('');
      onChanged();
    } catch (e2) {
      setErr(e2 instanceof ApiError && e2.code === 'admin_auth_failed'
        ? 'Wrong password'
        : (e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function run(okMsg: string, action: (pw: string) => Promise<unknown>) {
    const adminPw = getAdminPw();
    if (!adminPw) { setMsg('Admin is locked — unlock again.'); return; }
    setBusy(true); setMsg(null);
    try {
      await action(adminPw);
      setMsg(okMsg);
      onChanged();
    } catch (e) {
      setMsg(e instanceof ApiError && e.code === 'admin_auth_failed' ? 'Wrong password' : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitChange(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg(null);
    if (next.length < 4) { setPwMsg('New password needs at least 4 characters.'); return; }
    if (next !== confirm) { setPwMsg('New passwords don\'t match.'); return; }
    setBusy(true);
    try {
      await api.adminSetPassword(cur, next);
      unlock(next); // keep the session unlocked under the new password
      setUnlocked(true);
      setPwMsg('Password changed ✅');
      setCur(''); setNext(''); setConfirm('');
    } catch (e2) {
      setPwMsg(e2 instanceof ApiError && e2.code === 'admin_auth_failed'
        ? 'Current password is wrong.'
        : (e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!unlocked) {
    return (
      <form className="stack" onSubmit={submitUnlock}>
        <p className="muted">
          Admin tools are locked. Enter the admin password to unlock them for this page load.
        </p>
        <div className="field">
          <label className="field-label" htmlFor="admin-pw">Admin password</label>
          <input
            id="admin-pw"
            type="password"
            className="input"
            value={pw}
            onChange={e => setPw(e.target.value)}
            autoComplete="off"
          />
        </div>
        {err && <Banner kind="err">{err}</Banner>}
        <div className="row">
          <button className="btn primary" type="submit" disabled={busy || !pw}>
            {busy && <BtnSpinner />}
            Unlock
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="stack">
      <Banner kind="ok">Admin unlocked for this page load.</Banner>

      <AdminConnection initial={health} />

      <div className="field">
        <span className="field-label">Today&apos;s practice</span>
        <span className="muted field-hint">
          Status: {daily == null ? '…' : daily.completed ? 'completed' : daily.skipped ? 'skipped (demo)' : 'not done yet'}
        </span>
        <div className="row">
          <button
            className="btn amber"
            disabled={busy}
            onClick={() => run('Marked today as done (skipped).', p => api.dailySkip(learnerId, p))}
          >
            {busy && <BtnSpinner />}
            Skip today (mark complete)
          </button>
          <button
            className="btn ghost"
            disabled={busy}
            onClick={() => run('Today\'s progress was reset.', p => api.dailyReset(learnerId, p))}
          >
            Reset today&apos;s progress
          </button>
        </div>
        {msg && <span className="muted">{msg}</span>}
      </div>

      <form className="stack" onSubmit={submitChange}>
        <div className="field">
          <label className="field-label" htmlFor="admin-cur">Current password</label>
          <input id="admin-cur" type="password" className="input"
            value={cur} onChange={e => setCur(e.target.value)} autoComplete="off" />
        </div>
        <div className="field">
          <label className="field-label" htmlFor="admin-new">New password</label>
          <input id="admin-new" type="password" className="input"
            value={next} onChange={e => setNext(e.target.value)} autoComplete="off" />
          <span className="muted field-hint">At least 4 characters.</span>
        </div>
        <div className="field">
          <label className="field-label" htmlFor="admin-confirm">Confirm new password</label>
          <input id="admin-confirm" type="password" className="input"
            value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="off" />
        </div>
        {pwMsg && <span className="muted">{pwMsg}</span>}
        <div className="row">
          <button className="btn primary" type="submit" disabled={busy || !cur || !next}>
            {busy && <BtnSpinner />}
            Change admin password
          </button>
        </div>
      </form>
    </div>
  );
}

/* ---- Admin: connection + model ids ---------------------------------------- */

function ModelRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="model-row">
      <span className="model-label">{label}</span>
      <code className="model-value">{value ?? '…'}</code>
    </div>
  );
}

/** Connection status and the four model ids, shown only in the Admin tab. */
function AdminConnection({ initial }: { initial: Health | null }) {
  const [health, setHealth] = useState<Health | null>(initial);
  const [checking, setChecking] = useState(false);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function recheck() {
    setChecking(true); setErr(null);
    try {
      setHealth(await api.health());
      setCheckedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setChecking(false);
    }
  }

  const configured = health?.api_key_configured;
  return (
    <div className="field admin-connection">
      <div className="row-between">
        <span className="field-label">
          Models &amp; connection
          {health?.provider_label ? ` · ${health.provider_label}` : ''}
        </span>
        {health && (
          <span className={`tag ${configured ? 'mint' : 'rose'}`}>
            {configured ? '✓ API key configured' : '⚠ No API key'}
          </span>
        )}
      </div>
      <div className="model-grid">
        <ModelRow label="Story LLM" value={health?.models.llm} />
        <ModelRow label="Handwriting OCR" value={health?.models.ocr} />
        <ModelRow label="Speech (TTS)" value={health?.models.tts} />
        <ModelRow label="Transcription (STT)" value={health?.models.stt} />
      </div>
      {err && <Banner kind="err">{err}</Banner>}
      <div className="row">
        <button className="btn ghost btn-sm" onClick={recheck} disabled={checking}>
          {checking && <BtnSpinner />}
          {checking ? 'Checking…' : 'Re-check connection'}
        </button>
        {checkedAt && <span className="muted">Checked {checkedAt}</span>}
      </div>
      <span className="muted field-hint">
        Gateway selected with <code>MBDT_PROVIDER</code>; model ids and keys are set
        in <code>backend/.env</code> with <code>MBDT_LLM_MODEL</code>,{' '}
        <code>MBDT_OCR_MODEL</code>, <code>MBDT_TTS_MODEL</code> and{' '}
        <code>MBDT_STT_MODEL</code>.
      </span>
    </div>
  );
}

/* ---- Standalone guardian / admin pages ---------------------------------- */

export function GuardianPage({ learnerId, health, onChanged }: {
  learnerId: number;
  health: Health | null;
  onChanged: () => void;
}) {
  return (
    <div className="page">
      <header className="page-head">
        <p className="page-kicker">Grown-up settings</p>
        <h1>Guardian controls</h1>
        <p className="muted">
          Word sets, story interests, safety filters and helper options. Changes apply from
          the next round.
        </p>
      </header>
      <Card>
        <GuardianTab learnerId={learnerId} health={health} onChanged={onChanged} />
      </Card>
    </div>
  );
}

export function AdminPage({ learnerId, daily, health, onChanged }: {
  learnerId: number;
  daily: DailyStatus | null;
  health: Health | null;
  onChanged: () => void;
}) {
  return (
    <div className="page">
      <header className="page-head">
        <p className="page-kicker">Maintenance</p>
        <h1>Admin</h1>
        <p className="muted">
          Connection status, model ids and demo tools. The password is held in memory only,
          so a reload locks this page again.
        </p>
      </header>
      <Card>
        <AdminTab learnerId={learnerId} daily={daily} health={health} onChanged={onChanged} />
      </Card>
    </div>
  );
}
