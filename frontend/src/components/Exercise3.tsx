import { useCallback, useEffect, useRef, useState } from 'react';
import {
  api,
  type Ex3SpellItem,
  type Ex3SpellCheckResult,
  type Ex3CategorizeOption,
  type Ex3CategorizeResult,
} from '../api';
import { Banner, BtnSpinner, Card, Confetti, ErrBanner, Skeleton } from './ui';
import type { DailyRunProps } from './Exercise1';

interface Props {
  learnerId: number;
  onComplete?: () => void;
  onGuardianHelp?: () => void;
  daily?: DailyRunProps;
  dailyStage?: 'spell' | 'categorize';
}

type Mode = 'menu' | 'spell' | 'categorize';

export function Exercise3({ learnerId, onComplete, onGuardianHelp, daily, dailyStage }: Props) {
  const [mode, setMode] = useState<Mode>(daily ? (dailyStage ?? 'spell') : 'menu');
  return (
    <>
      {mode === 'menu' && (
        <Card>
          <div className="exercise-intro">
            <span className="intro-emoji" aria-hidden>✏️</span>
            <h3>Build the word</h3>
            <p className="muted">Two short tasks, both targeting the words you find trickiest.</p>
            <div className="mode-grid mt-3">
              <button className="btn primary mode-card" onClick={() => setMode('spell')}>
                <span className="mode-emoji" aria-hidden>✍️</span>
                <span>Spell from sound</span>
                <span className="mode-desc">Listen, then type the word</span>
              </button>
              <button className="btn lilac mode-card" onClick={() => setMode('categorize')}>
                <span className="mode-emoji" aria-hidden>👂</span>
                <span>Sort by sound</span>
                <span className="mode-desc">Pick every word that matches</span>
              </button>
            </div>
          </div>
        </Card>
      )}
      {mode === 'spell' && (
        <SpellTask learnerId={learnerId} onBack={() => setMode('menu')} onComplete={onComplete} onGuardianHelp={onGuardianHelp} daily={daily} />
      )}
      {mode === 'categorize' && (
        <CategorizeTask learnerId={learnerId} onBack={() => setMode('menu')} onComplete={onComplete} onGuardianHelp={onGuardianHelp} daily={daily} />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// A. Spell from sound
// ---------------------------------------------------------------------------

type InputMode = 'type' | 'draw' | 'photo';

/** Keep verdict text readable if a model ever returns a paragraph. */
function truncate(text: string, max = 64): string {
  const t = (text || '').trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

const INPUT_MODES: ReadonlyArray<readonly [InputMode, string, string]> = [
  ['type', '⌨️', 'Type'],
  ['draw', '✍️', 'Write'],
  ['photo', '📷', 'Photo'],
];

function SpellTask({
  learnerId, onBack, onComplete, onGuardianHelp, daily,
}: { learnerId: number; onBack: () => void; onComplete?: () => void; onGuardianHelp?: () => void; daily?: DailyRunProps }) {
  const [items, setItems] = useState<Ex3SpellItem[]>([]);
  const [idx, setIdx] = useState(0);
  const [typed, setTyped] = useState('');
  const [inputMode, setInputMode] = useState<InputMode>('type');
  const [drawDirty, setDrawDirty] = useState(false);
  const [photo, setPhoto] = useState<string | null>(null);
  const padRef = useRef<{ export: () => string | null; clear: () => void } | null>(null);
  const [result, setResult] = useState<Ex3SpellCheckResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const correctRef = useRef(0);

  function resetInputs() {
    setTyped(''); setPhoto(null); setDrawDirty(false);
  }

  function switchMode(m: InputMode) {
    if (m === inputMode) return;
    setInputMode(m); setError(null);
    resetInputs();
  }

  const dailyCount = daily?.count;
  const start = useCallback(async () => {
    setLoading(true); setError(null); setResult(null);
    resetInputs();
    correctRef.current = 0;
    try {
      const r = await api.ex3SpellRound(learnerId, dailyCount ?? 6);
      setItems(r.items); setIdx(0);
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [learnerId, dailyCount]);

  // Daily mode: no intro screen, the round starts on mount. Deferred a tick so
  // the effect body itself stays free of synchronous setState.
  const dailyMode = daily != null;
  useEffect(() => {
    if (!dailyMode) return;
    const t = setTimeout(() => { void start(); }, 0);
    return () => clearTimeout(t);
  }, [dailyMode, start]);

  async function submit() {
    const item = items[idx];
    if (!item) return;
    let submitted = '';
    let image: string | undefined;
    if (inputMode === 'type') {
      submitted = typed.trim();
      if (!submitted) return;
    } else if (inputMode === 'draw') {
      const data = padRef.current?.export();
      if (!data) return;
      image = data;
    } else {
      if (!photo) return;
      image = photo;
    }
    setBusy(true); setError(null);
    try {
      const res = await api.ex3SpellCheck(learnerId, item.word_id, submitted, image);
      if (res.correct) correctRef.current += 1;
      setResult(res);
      // An unreadable image isn't an attempt: let the learner retry without
      // inflating the stage's progress count.
      if (!res.ocr_failed) daily?.onProgress?.(idx + 1, items.length);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function next() {
    if (idx + 1 >= items.length) {
      if (daily?.onFinish) {
        daily.onFinish({ attempted: items.length, correct: correctRef.current });
        return;
      }
      onComplete?.();
      setItems([]); setIdx(0); setResult(null);
    } else {
      setIdx(i => i + 1); setResult(null);
    }
    resetInputs();
  }

  const canSubmit = inputMode === 'type' ? !!typed.trim()
    : inputMode === 'draw' ? drawDirty
    : !!photo;

  if (items.length === 0) {
    return (
      <Card>
        <div className="exercise-intro">
          <span className="intro-emoji" aria-hidden>✍️</span>
          <h3>Spell from sound</h3>
          <p className="muted">Listen to each word, then type what you hear.</p>
          {error && <ErrBanner error={error} onGuardian={onGuardianHelp} />}
          <div className="row-center mt-2">
            <button className="btn primary btn-lg" onClick={start} disabled={loading}>
              {loading && <BtnSpinner />}
              {loading ? 'Loading words…' : dailyMode && error ? 'Try again' : 'Start'}
            </button>
            {!dailyMode && <button className="btn ghost" onClick={onBack}>Back</button>}
          </div>
          {loading && <Skeleton className="skeleton-stage mt-3" />}
        </div>
      </Card>
    );
  }

  const item = items[idx];
  return (
    <Card className="elevated">
      <div className="row-between">
        <h3 className="mt-0">Spell from sound</h3>
        <span className="muted">{idx + 1} / {items.length}</span>
      </div>

      <div className="mt-4 center-text">
        <PlayWordButton learnerId={learnerId} wordId={item.word_id} onGuardianHelp={onGuardianHelp} />
      </div>

      <div className="field mt-4">
        <div className="input-mode-switch" role="tablist" aria-label="How do you want to answer?">
          {INPUT_MODES.map(([m, emoji, label]) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={inputMode === m}
              className={`btn input-mode-btn ${inputMode === m ? 'sky' : 'ghost'}`}
              onClick={() => switchMode(m)}
              disabled={!!result || busy}
            >
              <span aria-hidden>{emoji} </span>{label}
            </button>
          ))}
        </div>

        {inputMode === 'type' && (
          <>
            <label className="field-label mt-3" htmlFor="spell-input">What word did you hear? Spell it!</label>
            <input
              id="spell-input"
              className="input spell-input"
              value={typed}
              onChange={e => setTyped(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !result) submit(); }}
              disabled={!!result || busy}
              autoFocus
            />
          </>
        )}

        {inputMode === 'draw' && (
          <>
            <div className="field-label mt-3">Write the word with your finger</div>
            <DrawPad
              key={item.word_id}
              disabled={!!result || busy}
              onDirtyChange={setDrawDirty}
              padRef={padRef}
            />
            <div className="row-center mt-2">
              <button
                type="button"
                className="btn ghost"
                onClick={() => padRef.current?.clear()}
                disabled={!!result || busy || !drawDirty}
              >
                Clear
              </button>
            </div>
          </>
        )}

        {inputMode === 'photo' && (
          <>
            <div className="field-label mt-3">Photograph your handwritten word</div>
            <CameraSnap
              photo={photo}
              onPhoto={setPhoto}
              onError={setError}
              disabled={!!result || busy}
            />
          </>
        )}
      </div>

      {error && <div className="mt-3"><ErrBanner error={error} onGuardian={onGuardianHelp} /></div>}

      {result && (
        <div className="stack mt-3">
          {result.correct && <Confetti />}
          {result.ocr_failed ? (
            <div className="feedback-sheet warn" role="alert">
              <div className="feedback-head">
                <span className="feedback-icon" aria-hidden>📷</span>
                <div>
                  <h3>We couldn&apos;t read that</h3>
                  <p className="muted">
                    {result.message ?? 'Try again with clearer, larger letters — or type the word.'}{' '}
                    Nothing was scored.
                  </p>
                </div>
              </div>
              <div className="row-center">
                <button
                  className="btn amber btn-lg"
                  onClick={() => { setResult(null); resetInputs(); }}
                >
                  Try again
                </button>
                <button className="btn ghost" onClick={() => switchMode('type')}>Type it</button>
              </div>
            </div>
          ) : (
            <div className={`feedback-sheet ${result.correct ? 'ok' : 'err'}`} role="status">
              <div className="feedback-head">
                <span className="feedback-icon" aria-hidden>{result.correct ? '🎉' : '💪'}</span>
                <div>
                  <h3>{result.correct ? 'Correct!' : 'Not quite'}</h3>
                  <p className="muted">
                    The word was <strong>{result.word}</strong>. You wrote{' '}
                    <strong>{truncate(result.submitted) || '(blank)'}</strong> ·{' '}
                    {Math.round(result.similarity * 100)}% match
                  </p>
                </div>
              </div>
              <button className="btn lilac btn-lg feedback-next" onClick={next}>
                {idx + 1 >= items.length ? 'Finish' : 'Continue'}
              </button>
            </div>
          )}
        </div>
      )}

      {!result && (
        <div className="row-center mt-4">
          <button className="btn primary" onClick={submit} disabled={busy || !canSubmit}>
            {busy && <BtnSpinner />}
            {busy ? (inputMode === 'type' ? 'Checking…' : 'Reading your writing…') : 'Check'}
          </button>
          {!dailyMode && <button className="btn ghost" onClick={onBack}>Back</button>}
        </div>
      )}
    </Card>
  );
}

function PlayWordButton({ learnerId, wordId, onGuardianHelp }: { learnerId: number; wordId: number; onGuardianHelp?: () => void }) {
  const ref = useRef<HTMLAudioElement | null>(null);
  const fetched = useRef(false);
  const [err, setErr] = useState<string | null>(null);
  const url = api.ex3WordAudioByIdUrl(learnerId, wordId);

  // Fetch the audio URL once and surface the backend `detail` so a 503 is
  // visible instead of silently swallowed.
  async function handleError() {
    if (fetched.current) return;
    fetched.current = true;
    try {
      const r = await fetch(url);
      const body = await r.json();
      setErr(body?.detail ? String(body.detail) : `Audio unavailable (${r.status})`);
    } catch {
      setErr('Audio unavailable');
    }
  }

  return (
    <>
      <audio ref={ref} src={url} preload="none" onError={handleError} />
      <button className="btn amber" onClick={() => ref.current?.play().catch(handleError)}>
        🔊 Play word
      </button>
      {err && (
        <p className="muted" style={{ color: 'var(--err-ink)' }}>
          {err}
          {onGuardianHelp && (
            <>
              {' '}
              <button type="button" className="linklike" onClick={onGuardianHelp}>
                Guardian setup →
              </button>
            </>
          )}
        </p>
      )}
    </>
  );
}

function DrawPad({ disabled, onDirtyChange, padRef }: {
  disabled: boolean;
  onDirtyChange: (dirty: boolean) => void;
  padRef: { current: { export: () => string | null; clear: () => void } | null };
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const scaleRef = useRef(1);
  const drawingRef = useRef(false);

  const paintPaper = useCallback(() => {
    const c = canvasRef.current;
    const ctx = ctxRef.current;
    if (!c || !ctx) return;
    ctx.save();
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, c.width, c.height);
    const s = scaleRef.current;
    ctx.lineWidth = 2 * s;
    ctx.strokeStyle = '#e4e8f2';
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(0, c.height * 0.72); ctx.lineTo(c.width, c.height * 0.72);
    ctx.stroke();
    ctx.strokeStyle = '#f0f2f9';
    ctx.setLineDash([8 * s, 8 * s]);
    ctx.beginPath();
    ctx.moveTo(0, c.height * 0.38); ctx.lineTo(c.width, c.height * 0.38);
    ctx.stroke();
    ctx.restore();
  }, []);

  const clear = useCallback(() => {
    paintPaper();
    onDirtyChange(false);
  }, [paintPaper, onDirtyChange]);

  useEffect(() => {
    const c = canvasRef.current;
    const wrap = wrapRef.current;
    if (!c || !wrap) return;
    const cssW = wrap.clientWidth || 600;
    const cssH = 220;
    const scale = Math.min(window.devicePixelRatio || 1, 1400 / cssW);
    scaleRef.current = scale;
    c.width = Math.round(cssW * scale);
    c.height = Math.round(cssH * scale);
    c.style.height = `${cssH}px`;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#232733';
    ctx.lineWidth = 9 * scale;
    ctxRef.current = ctx;
    paintPaper();
  }, [paintPaper]);

  useEffect(() => {
    padRef.current = {
      export: () => canvasRef.current?.toDataURL('image/png') ?? null,
      clear,
    };
    return () => { padRef.current = null; };
  }, [padRef, clear]);

  function point(e: React.PointerEvent<HTMLCanvasElement>) {
    const r = canvasRef.current!.getBoundingClientRect();
    const s = scaleRef.current;
    return { x: (e.clientX - r.left) * s, y: (e.clientY - r.top) * s };
  }

  function onPointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    if (disabled) return;
    const c = canvasRef.current;
    const ctx = ctxRef.current;
    if (!c || !ctx) return;
    c.setPointerCapture(e.pointerId);
    drawingRef.current = true;
    const p = point(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x + 0.01, p.y + 0.01);
    ctx.stroke();
    onDirtyChange(true);
  }

  function onPointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current || !ctxRef.current) return;
    const p = point(e);
    ctxRef.current.lineTo(p.x, p.y);
    ctxRef.current.stroke();
  }

  function onPointerUp(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    const c = canvasRef.current;
    if (c?.hasPointerCapture(e.pointerId)) c.releasePointerCapture(e.pointerId);
  }

  return (
    <div ref={wrapRef} className="draw-pad">
      <canvas
        ref={canvasRef}
        className="draw-canvas"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      />
    </div>
  );
}

function CameraSnap({ photo, onPhoto, onError, disabled }: {
  photo: string | null;
  onPhoto: (dataUrl: string | null) => void;
  onError: (msg: string | null) => void;
  disabled: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (photo) return;
    let canceled = false;
    async function open() {
      onError(null);
      if (!navigator.mediaDevices?.getUserMedia) {
        onError('Camera is not available here. Try writing or typing instead.');
        return;
      }
      setStarting(true);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
        });
        if (canceled) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch (e) {
        if (canceled) return;
        const name = (e as DOMException).name;
        onError(
          name === 'NotAllowedError'
            ? 'Camera permission was denied. Allow camera access, or try writing or typing instead.'
            : name === 'NotFoundError'
              ? 'No camera found on this device. Try writing or typing instead.'
              : 'Could not start the camera. Try writing or typing instead.',
        );
      } finally {
        if (!canceled) setStarting(false);
      }
    }
    void open();
    return () => {
      canceled = true;
      streamRef.current?.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    };
  }, [photo, onError]);

  function capture() {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const k = Math.min(1, 1600 / Math.max(v.videoWidth, v.videoHeight));
    const c = document.createElement('canvas');
    c.width = Math.round(v.videoWidth * k);
    c.height = Math.round(v.videoHeight * k);
    c.getContext('2d')!.drawImage(v, 0, 0, c.width, c.height);
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    onPhoto(c.toDataURL('image/png'));
  }

  if (photo) {
    return (
      <div className="camera-box">
        <img className="camera-shot" src={photo} alt="Your handwritten word" />
        <div className="row-center mt-2">
          <button type="button" className="btn ghost" onClick={() => onPhoto(null)} disabled={disabled}>
            Retake
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="camera-box">
      <video ref={videoRef} className="camera-video" muted playsInline autoPlay />
      <div className="row-center mt-2">
        <button type="button" className="btn amber" onClick={capture} disabled={disabled || starting}>
          {starting && <BtnSpinner />}
          {starting ? 'Starting camera…' : '📸 Capture'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// B. Sort by sound
// ---------------------------------------------------------------------------

function CategorizeTask({
  learnerId, onBack, onComplete, onGuardianHelp, daily,
}: { learnerId: number; onBack: () => void; onComplete?: () => void; onGuardianHelp?: () => void; daily?: DailyRunProps }) {
  const [phoneme, setPhoneme] = useState<string | null>(null);
  const [options, setOptions] = useState<Ex3CategorizeOption[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [result, setResult] = useState<Ex3CategorizeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const correctRef = useRef(0);
  // Daily mode: multiple rounds back-to-back (default 2); standalone stays single-round.
  const totalRounds = daily ? (daily.count ?? 2) : 1;

  const start = useCallback(async () => {
    setBusy(true); setError(null); setResult(null); setSelected(new Set());
    try {
      const r = await api.ex3CategorizeRound(learnerId, 6);
      setPhoneme(r.phoneme); setOptions(r.options);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, [learnerId]);

  // Daily mode: no intro screen, the round starts on mount. Deferred a tick so
  // the effect body itself stays free of synchronous setState.
  const dailyMode = daily != null;
  useEffect(() => {
    if (!dailyMode) return;
    const t = setTimeout(() => { void start(); }, 0);
    return () => clearTimeout(t);
  }, [dailyMode, start]);

  function toggle(id: number) {
    setSelected(prev => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  async function submit() {
    if (!phoneme) return;
    setBusy(true); setError(null);
    try {
      const res = await api.ex3CategorizeCheck(
        learnerId, phoneme, [...selected], options.map(o => o.word_id),
      );
      if (res.score >= 0.7) correctRef.current += 1;
      setResult(res);
      daily?.onProgress?.(round + 1, totalRounds);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function nextRound() {
    if (round + 1 >= totalRounds) {
      daily?.onFinish?.({ attempted: totalRounds, correct: correctRef.current });
      return;
    }
    setRound(r => r + 1);
    void start();
  }

  if (!phoneme) {
    return (
      <Card>
        <div className="exercise-intro">
          <span className="intro-emoji" aria-hidden>👂</span>
          <h3>Sort by sound</h3>
          <p className="muted">Pick every word that shares the target sound.</p>
          {error && <ErrBanner error={error} onGuardian={onGuardianHelp} />}
          <div className="row-center mt-2">
            <button className="btn lilac btn-lg" onClick={start} disabled={busy}>
              {busy && <BtnSpinner />}
              {busy ? 'Loading words…' : dailyMode && error ? 'Try again' : 'Start'}
            </button>
            {!dailyMode && <button className="btn ghost" onClick={onBack}>Back</button>}
          </div>
          {busy && <Skeleton className="skeleton-block mt-3" />}
        </div>
      </Card>
    );
  }

  return (
    <Card className="elevated">
      <div className="row-between">
        <h3 className="mt-0">Sort by sound</h3>
        {dailyMode
          ? <span className="muted">{round + 1} / {totalRounds}</span>
          : <button className="btn ghost" onClick={onBack}>Back</button>}
      </div>
      <div className="mt-3 center-text">
        <span className="tag amber target-sound-tag">
          Target sound: <strong>{phoneme}</strong>
        </span>
      </div>

      <div className="word-grid mt-4">
        {options.map((o, i) => {
          const on = selected.has(o.word_id);
          let cls = 'word-btn';
          if (result) {
            const isTarget = result.target_ids.includes(o.word_id);
            if (isTarget && on) cls += ' is-correct';
            else if (!isTarget && on) cls += ' is-wrong';
            else if (isTarget && !on) cls += ' is-missed';
          } else if (on) {
            cls += ' is-selected';
          }
          return (
            <button
              key={o.word_id}
              className={cls}
              style={{ animationDelay: `${i * 45}ms` }}
              onClick={() => !result && toggle(o.word_id)}
            >
              {o.text}
            </button>
          );
        })}
      </div>

      {error && <div className="mt-3"><ErrBanner error={error} onGuardian={onGuardianHelp} /></div>}

      {result && (
        <div className="stack mt-4">
          {result.score >= 0.7 && <Confetti />}
          <Banner kind={result.score >= 0.7 ? 'ok' : 'warn'}>
            Score {Math.round(result.score * 100)}% · {result.correct_ids.length} right,
            {' ' + result.incorrect_ids.length} wrong, {result.missed_count} missed
          </Banner>
          {dailyMode ? (
            <div className="row-center">
              <button className="btn primary" onClick={nextRound}>
                {round + 1 >= totalRounds ? 'Finish' : 'Next round →'}
              </button>
            </div>
          ) : (
            <div className="row-center">
              <button className="btn primary" onClick={() => { onComplete?.(); setPhoneme(null); }}>Done</button>
              <button className="btn lilac" onClick={start}>New round</button>
            </div>
          )}
        </div>
      )}

      {!result && (
        <div className="row-center mt-4">
          <button className="btn primary" onClick={submit} disabled={busy || selected.size === 0}>
            {busy && <BtnSpinner />}
            {busy ? 'Checking…' : 'Check answers'}
          </button>
        </div>
      )}
    </Card>
  );
}
