import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api';
import { isUnlocked, unlock } from '../admin';
import { Exercise1, type StageStats } from './Exercise1';
import { Exercise3 } from './Exercise3';
import { Exercise5 } from './Exercise5';
import { Banner, BtnSpinner, Card, Confetti, ProgressBar } from './ui';

// Session shape: Ex1 -> break -> Ex3 spell -> break -> Ex3 categorize -> break -> Ex5 -> summary.
const EX1_WORDS = 12;
const EX3_SPELL = 8;
const EX3_CAT_ROUNDS = 2;
const EX5_STORIES = 1;
const BREAK_SECONDS = 45;

type StageKey = 'ex1' | 'ex3spell' | 'ex3cat' | 'ex5';
interface StageDef { key: StageKey; label: string; emoji: string; total: number; }

const STAGES: StageDef[] = [
  { key: 'ex1', label: 'Say the word', emoji: '🗣️', total: EX1_WORDS },
  { key: 'ex3spell', label: 'Spell from sound', emoji: '✍️', total: EX3_SPELL },
  { key: 'ex3cat', label: 'Sort by sound', emoji: '👂', total: EX3_CAT_ROUNDS },
  { key: 'ex5', label: 'Read a story', emoji: '📖', total: EX5_STORIES },
];

type Phase = 'run' | 'break' | 'stageEnd' | 'summary';

interface Recorded extends StageStats { skipped: boolean; stage: number }

export function DailySession({ learnerId, initialStage = 0, onDone, onGuardianHelp }: {
  learnerId: number;
  /** Jump straight into this stage (0-3), from the home path. */
  initialStage?: number;
  onDone: () => void;
  onGuardianHelp?: () => void;
}) {
  const startIdx = Math.min(Math.max(initialStage, 0), STAGES.length - 1);
  const [stageIdx, setStageIdx] = useState(startIdx);
  const [phase, setPhase] = useState<Phase>('run');
  const [done, setDone] = useState(0);
  const [stats, setStats] = useState<Recorded[]>([]);
  const [confirmExit, setConfirmExit] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(0);
  // Session clock starts on mount; read only in event handlers (render must stay pure).
  useEffect(() => { startRef.current = Date.now(); }, []);

  const stage = STAGES[stageIdx];
  const lastStat = stats[stats.length - 1];
  // Progress counts only the stages this run covers (a node jump starts mid-session).
  const plannedTotal = STAGES.slice(startIdx).reduce((n, s) => n + s.total, 0);
  const finishedItems = stats.reduce((n, r) => n + STAGES[r.stage].total, 0);
  const overallDone = finishedItems + (phase === 'run' ? done : 0);

  const onProgress = useCallback((d: number) => setDone(d), []);

  function finishStage(s: StageStats, skipped = false) {
    setStats(prev => [...prev, { ...s, skipped, stage: stageIdx }]);
    setDone(0);
    setPwOpen(false);
    setConfirmExit(false);
    setPhase('stageEnd');
  }

  // From the stage-end card: skipped stages go straight to the next exercise (no break).
  function advance() {
    if (stageIdx + 1 >= STAGES.length) {
      setElapsed(Math.max(0, Math.round((Date.now() - startRef.current) / 1000)));
      setPhase('summary');
      return;
    }
    setStageIdx(i => i + 1);
    setPhase(lastStat?.skipped ? 'run' : 'break');
  }

  const endBreak = useCallback(() => {
    // advance() already moved to the next stage before the break was shown;
    // incrementing here would skip a stage (and run past the last one).
    setPhase('run');
  }, []);

  function skipStage() {
    setPwOpen(false);
    finishStage({ attempted: 0, correct: 0 }, true);
  }

  return (
    <div className="stack lesson">
      {phase !== 'summary' && (
        <div className="lesson-bar">
          <button
            className="xbtn"
            onClick={() => setConfirmExit(true)}
            aria-label="Exit today's practice"
            title="Exit"
          >
            ✕
          </button>
          <div className="lesson-bar-main">
            <span className="lesson-caption">
              Part {stageIdx + 1} of {STAGES.length} · {stage.label}
            </span>
            <ProgressBar
              value={overallDone}
              max={plannedTotal}
              label="Today's practice"
              className="lesson-pbar"
            />
          </div>
          {phase === 'run' && (
            <button
              className="btn ghost btn-sm lesson-skip"
              onClick={() => (isUnlocked() ? skipStage() : setPwOpen(true))}
            >
              Skip
            </button>
          )}
        </div>
      )}

      {confirmExit && phase !== 'summary' && (
        <Banner kind="warn">
          Leave today&apos;s practice? Your progress so far won&apos;t be saved.
          <span className="daily-confirm-btns">
            <button className="btn rose btn-sm" onClick={onDone}>Yes, exit</button>
            <button className="btn ghost btn-sm" onClick={() => setConfirmExit(false)}>Keep practicing</button>
          </span>
        </Banner>
      )}

      {pwOpen && phase === 'run' && (
        <AdminUnlock
          onCancel={() => setPwOpen(false)}
          onUnlocked={skipStage}
        />
      )}

      {phase === 'run' && stage.key === 'ex1' && (
        <Exercise1
          key="ex1"
          learnerId={learnerId}
          onGuardianHelp={onGuardianHelp}
          daily={{ count: EX1_WORDS, onProgress, onFinish: s => finishStage(s) }}
        />
      )}
      {phase === 'run' && stage.key === 'ex3spell' && (
        <Exercise3
          key="ex3spell"
          learnerId={learnerId}
          dailyStage="spell"
          onGuardianHelp={onGuardianHelp}
          daily={{ count: EX3_SPELL, onProgress, onFinish: s => finishStage(s) }}
        />
      )}
      {phase === 'run' && stage.key === 'ex3cat' && (
        <Exercise3
          key="ex3cat"
          learnerId={learnerId}
          dailyStage="categorize"
          onGuardianHelp={onGuardianHelp}
          daily={{ count: EX3_CAT_ROUNDS, onProgress, onFinish: s => finishStage(s) }}
        />
      )}
      {phase === 'run' && stage.key === 'ex5' && (
        <Exercise5
          key="ex5"
          learnerId={learnerId}
          onGuardianHelp={onGuardianHelp}
          daily={{ onProgress, onFinish: s => finishStage(s) }}
        />
      )}

      {phase === 'break' && <BreakScreen onEnd={endBreak} />}

      {phase === 'stageEnd' && lastStat && (
        <StageEnd stage={STAGES[lastStat.stage]} stat={lastStat} onContinue={advance} />
      )}

      {phase === 'summary' && (
        <Summary learnerId={learnerId} stats={stats} elapsed={elapsed} onDone={onDone} />
      )}
    </div>
  );
}

/* ---- Admin unlock prompt (password verified, then held in memory) -------- */

function AdminUnlock({ onUnlocked, onCancel }: { onUnlocked: () => void; onCancel: () => void }) {
  const [pw, setPw] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!pw || busy) return;
    setBusy(true); setErr(null);
    try {
      await api.adminVerify(pw);
      unlock(pw);
      onUnlocked();
    } catch (e2) {
      setErr(e2 instanceof ApiError && e2.code === 'admin_auth_failed'
        ? 'Wrong password'
        : (e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <form className="stack" onSubmit={submit}>
        <h3 className="mt-0">Grown-up check</h3>
        <p className="muted">Enter the admin password to skip this activity. Stays unlocked until the page reloads.</p>
        <input
          type="password"
          className="input"
          value={pw}
          onChange={e => setPw(e.target.value)}
          placeholder="Admin password"
          autoFocus
          autoComplete="off"
          aria-label="Admin password"
        />
        {err && <Banner kind="err">{err}</Banner>}
        <div className="row-center">
          <button className="btn primary" type="submit" disabled={busy || !pw}>
            {busy && <BtnSpinner />}
            Unlock &amp; skip
          </button>
          <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </Card>
  );
}

/* ---- Break screen ---------------------------------------------------------- */

function BreakScreen({ onEnd }: { onEnd: () => void }) {
  const [left, setLeft] = useState(BREAK_SECONDS);
  useEffect(() => {
    const t = setInterval(() => setLeft(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (left <= 0) onEnd();
  }, [left, onEnd]);

  return (
    <Card>
      <div className="exercise-intro break-screen">
        <span className="intro-emoji break-emoji" aria-hidden>🧃</span>
        <h3>Break time!</h3>
        <p className="muted">Wiggle your fingers, look out the window, take a sip of water.</p>
        <span className="break-count" role="status" aria-live="polite">{left}s</span>
        <button className="btn primary btn-lg mt-2" onClick={onEnd}>Skip break →</button>
      </div>
    </Card>
  );
}

/* ---- Per-stage stats card ---------------------------------------------------- */

function encouragement(pct: number): string {
  if (pct >= 80) return 'Amazing work! 🌟';
  if (pct >= 50) return 'Good effort — keep going! 💪';
  return 'Nice try — practice makes progress! 🌱';
}

function StageEnd({ stage, stat, onContinue }: { stage: StageDef; stat: Recorded; onContinue: () => void }) {
  const pct = stat.attempted > 0 ? Math.round((stat.correct / stat.attempted) * 100) : 0;
  return (
    <Card>
      <div className="exercise-intro stage-end">
        <span className="intro-emoji" aria-hidden>{stage.emoji}</span>
        <h3>{stage.label}</h3>
        {stat.skipped ? (
          <p className="muted">Skipped</p>
        ) : (
          <>
            <p className="stage-end-stat">{stat.correct} of {stat.attempted} correct · {pct}%</p>
            <p className="muted">{encouragement(pct)}</p>
          </>
        )}
        <button className="btn primary btn-lg mt-2" onClick={onContinue}>Continue →</button>
      </div>
    </Card>
  );
}

/* ---- Final summary ----------------------------------------------------------- */

function Summary({ learnerId, stats, elapsed, onDone }: {
  learnerId: number;
  stats: Recorded[];
  elapsed: number;
  onDone: () => void;
}) {
  const [xp, setXp] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const doneStats = stats.filter(s => !s.skipped);
  const attempted = doneStats.reduce((n, s) => n + s.attempted, 0);
  const correct = doneStats.reduce((n, s) => n + s.correct, 0);
  const accuracy = attempted > 0 ? correct / attempted : 0;
  const duration = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`;

  // Mark the day done as soon as the summary opens; the exercises themselves
  // have already persisted every review, so this only flips the daily flag.
  useEffect(() => {
    let canceled = false;
    void (async () => {
      try {
        const st = await api.dailyComplete(learnerId);
        if (!canceled) setXp(st.xp_today);
      } catch (e) {
        if (!canceled) setError((e as Error).message);
      }
    })();
    return () => { canceled = true; };
  }, [learnerId]);

  return (
    <Card>
      {doneStats.length > 0 && accuracy >= 0.7 && <Confetti />}
      <div className="exercise-intro summary">
        <h3>Today&apos;s practice is done!</h3>
        <p className="summary-xp">
          <span aria-hidden>⚡</span>
          {xp == null ? 'Saving…' : xp.toLocaleString()}
          <small>XP today</small>
        </p>
        <div className="summary-rows">
          {STAGES.map((def, i) => {
            const s = stats.find(r => r.stage === i);
            if (!s) return null;
            const p = s.attempted > 0 ? Math.round((s.correct / s.attempted) * 100) : 0;
            return (
              <div className="summary-row" key={def.key}>
                <span className="summary-row-label">
                  <span aria-hidden>{def.emoji}</span> {def.label}
                </span>
                {s.skipped
                  ? <span className="muted">Skipped</span>
                  : <span><strong>{s.correct}/{s.attempted}</strong> · {p}%</span>}
              </div>
            );
          })}
        </div>
        <p className="stage-end-stat">
          Overall: {attempted > 0 ? `${Math.round(accuracy * 100)}%` : '—'} · {duration} min
        </p>
        {error && <Banner kind="err">{error}</Banner>}
        <button className="btn primary btn-lg mt-2" onClick={onDone}>Back home</button>
      </div>
    </Card>
  );
}
