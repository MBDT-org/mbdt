import { useEffect, useRef, useState } from 'react';
import { api, type DailyStatus, type Health, type Learner, type Dashboard } from './api';
import { getAdminPw, isUnlocked } from './admin';
import { Banner, BtnSpinner } from './components/ui';
import { StreakFlame, ProgressCard, WordsCard, GuardianPage, AdminPage } from './components/Dashboard';
import { DailySession } from './components/DailySession';
import {
  HomePath, LevelBadge, LevelProgress, MasteryCard, QuestsCard, XpPill, type PathStageIndex,
} from './components/HomePath';
import { Toaster } from './components/Toaster';

type View = 'login' | 'signup' | 'home' | 'daily' | 'setup' | 'guardian' | 'admin';

const STORAGE_KEY = 'mbdt.learnerId';

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [learners, setLearners] = useState<Learner[]>([]);
  const [learnerId, setLearnerId] = useState<number | null>(null);
  const [view, setView] = useState<View>('login');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [daily, setDaily] = useState<DailyStatus | null>(null);
  const [startStage, setStartStage] = useState<PathStageIndex>(0);

  async function fetchAll(): Promise<Learner[]> {
    const [h, ls] = await Promise.all([api.health(), api.listLearners()]);
    setHealth(h); setLearners(ls);
    return ls;
  }

  // Run once on mount; restores the last signed-in learner.
  const didBootRef = useRef(false);
  useEffect(() => {
    if (didBootRef.current) return;
    didBootRef.current = true;
    void (async () => {
      try {
        const ls = await fetchAll();
        const stored = Number(localStorage.getItem(STORAGE_KEY));
        if (stored && ls.some(l => l.id === stored)) {
          setLearnerId(stored);
          setView('home');
        }
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, []);

  // Load the dashboard + daily status for the selected learner; refresh after practice.
  useEffect(() => {
    let canceled = false;
    void (async () => {
      if (learnerId == null) { setDashboard(null); setDaily(null); return; }
      try {
        const d = await api.getDashboard(learnerId);
        if (!canceled) setDashboard(d);
      } catch { /* surfaced by other error paths */ }
      try {
        const ds = await api.dailyStatus(learnerId);
        if (!canceled) setDaily(ds);
      } catch { /* daily endpoint may not exist yet; home falls back to "not done" */ }
    })();
    return () => { canceled = true; };
  }, [learnerId, refreshKey]);

  function selectLearner(id: number) {
    localStorage.setItem(STORAGE_KEY, String(id));
    setLearnerId(id);
    setView('home');
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setLearnerId(null);
    setDashboard(null);
    setDaily(null);
    setView('login');
  }

  // Returns an error string to show in the form, or null on success.
  async function handleLogin(name: string): Promise<string | null> {
    const ls = learners.length ? learners : await fetchAll();
    const match = ls.find(l => l.name.toLowerCase() === name.toLowerCase());
    if (!match) return `No learner named "${name}".`;
    selectLearner(match.id);
    return null;
  }

  async function handleSignup(name: string): Promise<string | null> {
    const ls = learners.length ? learners : await fetchAll();
    if (ls.some(l => l.name.toLowerCase() === name.toLowerCase())) {
      return `"${name}" already exists.`;
    }
    const r = await api.createLearner(name);
    await fetchAll();
    selectLearner(r.id);
    return null;
  }

  async function refreshLearner() {
    await fetchAll();
    setRefreshKey(k => k + 1);
  }

  // Gate AI-dependent practice when the gateway key is missing.
  const aiLocked = health != null && !health.api_key_configured;
  const learnerName = learners.find(l => l.id === learnerId)?.name ?? 'Learner';
  const learnerInitial = learnerName.trim().charAt(0).toUpperCase() || 'M';

  function startDaily(stage: PathStageIndex = 0) {
    setStartStage(stage);
    setView(aiLocked ? 'setup' : 'daily');
  }

  function finishDaily() {
    void refreshLearner();
    setView('home');
  }

  async function resetToday() {
    if (learnerId == null) return;
    const pw = getAdminPw();
    if (!pw) return;
    // Demo affordance; if the call fails the status refresh shows the truth
    try { await api.dailyReset(learnerId, pw); } catch { /* ignore */ }
    await refreshLearner();
  }

  function openSetup() {
    setView('setup');
  }

  return (
    <div className={`app-shell stack${view === 'daily' ? ' is-lesson' : ''}`}>
      {view !== 'daily' && (
      <header className="header">
        <button
          className="brand-btn"
          onClick={() => setView(learnerId != null ? 'home' : 'login')}
          title="MBDT · Adaptive literacy practice, locally deployed"
          aria-label="MBDT home"
        >
          <img src="/logo.svg" alt="" className="brand-logo" />
        </button>

        {learnerId != null && (
          <nav className="topnav" aria-label="Sections">
            <button
              className={`btn tab ghost nav-tab${view === 'home' ? ' is-active' : ''}`}
              onClick={() => setView('home')}
              aria-current={view === 'home' ? 'page' : undefined}
            >
              <span aria-hidden>🏠</span><span className="nav-label">Home</span>
            </button>
            <button
              className={`btn tab ghost nav-tab${view === 'guardian' ? ' is-active' : ''}`}
              onClick={() => setView('guardian')}
              aria-current={view === 'guardian' ? 'page' : undefined}
            >
              <span aria-hidden>🛡️</span><span className="nav-label">Guardian</span>
            </button>
            <button
              className={`btn tab ghost nav-tab${view === 'admin' ? ' is-active' : ''}`}
              onClick={() => setView('admin')}
              aria-current={view === 'admin' ? 'page' : undefined}
            >
              <span aria-hidden>🔐</span><span className="nav-label">Admin</span>
            </button>
          </nav>
        )}

        <div className="header-right">
          {learnerId != null && (
            <>
              {dashboard && (
                <>
                  <StreakFlame days={dashboard.streak.days} />
                  <XpPill key={dashboard.xp} xp={dashboard.xp} />
                  <LevelBadge data={dashboard} />
                </>
              )}
              <span className="avatar-chip" title={learnerName}>
                <span className="avatar" aria-hidden>{learnerInitial}</span>
                <span className="avatar-name">{learnerName}</span>
              </span>
              <button className="btn ghost btn-sm logout" onClick={logout} aria-label="Log out" title="Log out">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
                  strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <path d="m16 17 5-5-5-5" />
                  <path d="M21 12H9" />
                </svg>
                <span className="logout-text">Log out</span>
              </button>
            </>
          )}
        </div>
      </header>
      )}

      {error && <Banner kind="err">Backend unavailable: {error}. Is the FastAPI server running on :8777?</Banner>}
      {health && !health.api_key_configured && (
        <Banner kind="warn">
          AI gateway key not configured. Speech, stories and pronunciation are gated off.{' '}
          <button type="button" className="linklike" onClick={() => setView('setup')}>
            Open guardian setup →
          </button>
        </Banner>
      )}

      <main className="main">
        {/* key re-mounts the wrapper per view, replaying the entrance animation. */}
        <div
          className={`view-center view-enter${
            view === 'login' || view === 'signup' ? ' is-centered' : ''
          }`}
          key={view}
        >
          {view === 'login' && (
            <AuthView mode="login" onSubmit={handleLogin} onSwitch={() => setView('signup')} />
          )}
          {view === 'signup' && (
            <AuthView mode="signup" onSubmit={handleSignup} onSwitch={() => setView('login')} />
          )}

          {learnerId != null && view === 'home' && (
            <div className="home">
              <section className="home-hero">
                <div className="home-hero-text">
                  <span className="home-kicker">Hi {learnerName}!</span>
                  <h1 className="home-greeting">
                    {daily?.completed
                      ? 'You finished today’s practice 🎉'
                      : daily?.skipped
                        ? 'Today was skipped'
                        : 'Ready for some word games?'}
                  </h1>
                  <p className="muted home-hero-sub">
                    {daily?.completed
                      ? 'Come back tomorrow for fresh words — or keep practicing if you like.'
                      : 'About 30 minutes · four quick activities, with breaks in between.'}
                  </p>
                  {isUnlocked() && (daily?.completed || daily?.skipped) && (
                    <button type="button" className="linklike" onClick={resetToday}>
                      Reset today (admin)
                    </button>
                  )}
                </div>
              </section>

              <div className="home-grid">
                <div className="home-left">
                  <HomePath daily={daily} onStart={startDaily} />
                </div>
                <div className="home-mid">
                  <LevelProgress data={dashboard} />
                  <QuestsCard data={dashboard} />
                  <MasteryCard data={dashboard} />
                  <ProgressCard data={dashboard} />
                </div>
                <aside className="home-side" aria-label="Words">
                  <WordsCard data={dashboard} />
                </aside>
              </div>
            </div>
          )}

          {view === 'daily' && learnerId != null && (
            <DailySession
              learnerId={learnerId}
              initialStage={startStage}
              onDone={finishDaily}
              onGuardianHelp={openSetup}
            />
          )}

          {view === 'guardian' && learnerId != null && (
            <GuardianPage
              learnerId={learnerId}
              health={health}
              onChanged={refreshLearner}
            />
          )}

          {view === 'admin' && learnerId != null && (
            <AdminPage
              learnerId={learnerId}
              daily={daily}
              health={health}
              onChanged={refreshLearner}
            />
          )}

          {view === 'setup' && (
            <SetupScreen
              health={health}
              onRecheck={fetchAll}
              onBack={() => setView(learnerId != null ? 'home' : 'login')}
            />
          )}
        </div>
      </main>


      <Toaster onOpenSetup={() => setView('setup')} />
    </div>
  );
}

function AuthView({ mode, onSubmit, onSwitch }: {
  mode: 'login' | 'signup';
  onSubmit: (name: string) => Promise<string | null>;
  onSwitch: () => void;
}) {
  const isLogin = mode === 'login';
  const [name, setName] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const problem = await onSubmit(trimmed);
      if (problem) setErr(problem);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card auth-card">
      <img src="/logo.svg" alt="" className="auth-logo" />
      <h2 className="center-text">{isLogin ? 'Welcome back!' : 'Create your profile'}</h2>
      <p className="muted center-text">
        {isLogin
          ? 'Type your learner name to pick up where you left off.'
          : 'Pick a learner name — no password needed on this device.'}
      </p>
      <form className="auth-form" onSubmit={submit}>
        <label className="auth-label" htmlFor={`auth-name-${mode}`}>Learner name</label>
        <input
          id={`auth-name-${mode}`}
          className="input"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. Alex"
          autoFocus
          autoComplete="off"
        />
        {err && (
          <p className="auth-err" role="alert">
            {err}{' '}
            <button type="button" className="linklike" onClick={onSwitch}>
              {isLogin ? 'Sign up instead' : 'Log in instead'}
            </button>
          </p>
        )}
        <button className="btn primary btn-lg" type="submit" disabled={!name.trim() || busy}>
          {busy && <BtnSpinner />}
          {busy ? 'Checking…' : isLogin ? 'Log in' : 'Sign up'}
        </button>
      </form>
      <p className="muted center-text">
        {isLogin ? 'New here?' : 'Already have a profile?'}{' '}
        <button type="button" className="linklike" onClick={onSwitch}>
          {isLogin ? 'Sign up' : 'Log in'}
        </button>
      </p>
    </section>
  );
}

function SetupScreen({ health, onRecheck, onBack }: {
  health: Health | null;
  onRecheck: () => Promise<unknown>;
  onBack: () => void;
}) {
  const [checking, setChecking] = useState(false);

  async function recheck() {
    setChecking(true);
    try { await onRecheck(); } finally { setChecking(false); }
  }

  return (
    <section className="card auth-card setup-card">
      <span className="intro-emoji" aria-hidden>🛠️</span>
      <h2 className="center-text">Guardian setup</h2>
      <p className="muted center-text">
        MBDT needs a working AI gateway for speech, pronunciation and stories.
        Requesty and OpenRouter are both supported. Your API key goes in{' '}
        <code>backend/.env</code>; copy <code>backend/.env.example</code> if the file
        does not exist yet.
      </p>

      <ol className="setup-steps">
        <li>
          Add one key to <code>backend/.env</code>:
          <br /><code>MBDT_REQUESTY_API_KEY=sk-...</code>
          <br /><code>MBDT_OPENROUTER_API_KEY=sk-or-v1-...</code>
          <br />
          <span className="muted">
            If both are set, choose the gateway with{' '}
            <code>MBDT_PROVIDER=requesty</code> or <code>MBDT_PROVIDER=openrouter</code>.
          </span>
        </li>
        <li>
          Model ids live in the same file and default to the chosen gateway. Override
          them with <code>MBDT_LLM_MODEL</code>, <code>MBDT_OCR_MODEL</code>,{' '}
          <code>MBDT_TTS_MODEL</code> and <code>MBDT_STT_MODEL</code>. Each must be
          available to your key: see{' '}
          <a href="https://app.requesty.ai/model-library" target="_blank" rel="noreferrer">
            Requesty's model library
          </a>{' '}
          or{' '}
          <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer">
            OpenRouter's model list
          </a>.
        </li>
        <li>
          Restart the backend:
          <br /><code>uv run uvicorn app:app --port 8777 --reload</code>
        </li>
      </ol>

      <p className="center-text setup-status">
        {health
          ? (health.api_key_configured
            ? <span className="setup-ok">✅ {health.provider_label} API key is set</span>
            : <span className="setup-bad">❌ No {health.provider_label} API key found</span>)
          : <span className="setup-bad">⚠️ Backend unreachable</span>}
      </p>

      <div className="row-center">
        <button className="btn sky" onClick={recheck} disabled={checking}>
          {checking && <BtnSpinner />}
          {checking ? 'Checking…' : 'Re-check connection'}
        </button>
        <button className="btn primary" onClick={onBack}>Back</button>
      </div>
    </section>
  );
}
