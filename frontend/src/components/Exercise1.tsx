import { useCallback, useEffect, useState } from 'react';
import { api, type Ex1Item, type Ex1CheckResult } from '../api';
import { useRecorder } from '../useRecorder';
import { Banner, BtnSpinner, Card, Confetti, ErrBanner, Skeleton, SoundButton, Spinner } from './ui';

export interface StageStats { attempted: number; correct: number; }
export interface DailyRunProps {
  onProgress?: (done: number, total: number) => void;
  onFinish?: (stats: StageStats) => void;
  count?: number;
}

interface Props {
  learnerId: number;
  onComplete?: () => void;
  onGuardianHelp?: () => void;
  daily?: DailyRunProps;
}

type Phase = 'intro' | 'playing' | 'feedback';

// Below this similarity the transcript is usually an STT hallucination or a
// completely different word, so echoing it back is noise (and can echo a
// misheard profanity). The score is still shown.
const TRANSCRIPT_MIN_SIMILARITY = 0.35;

export function Exercise1({ learnerId, onComplete, onGuardianHelp, daily }: Props) {
  const [items, setItems] = useState<Ex1Item[]>([]);
  const [phase, setPhase] = useState<Phase>('intro');
  const [idx, setIdx] = useState(0);
  const [results, setResults] = useState<Ex1CheckResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRecorder();
  const current = items[idx];

  const dailyCount = daily?.count;
  const startRound = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.ex1Round(learnerId, dailyCount ?? 6);
      setItems(r.items);
      setResults([]);
      setIdx(0);
      setPhase('playing');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [learnerId, dailyCount]);

  // Daily mode: no intro screen, the round starts on mount. Deferred a tick so
  // the effect body itself stays free of synchronous setState.
  const dailyMode = daily != null;
  useEffect(() => {
    if (!dailyMode) return;
    const t = setTimeout(() => { void startRound(); }, 0);
    return () => clearTimeout(t);
  }, [dailyMode, startRound]);

  async function submitAudio() {
    if (!current) return;
    setBusy(true);
    try {
      const blob = await recorder.stop();
      if (!blob) { setBusy(false); return; }
      if (blob.size < 800) {
        setError('That recording was too short — hold the mic button while you say the word.');
        setBusy(false);
        return;
      }
      const res = await api.ex1Check(learnerId, current.word_id, current.font, blob);
      setResults(prev => [...prev, res]);
      daily?.onProgress?.(results.length + 1, items.length);
      setPhase('feedback');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function next() {
    if (idx + 1 >= items.length) {
      if (daily?.onFinish) {
        daily.onFinish({ attempted: results.length, correct: results.filter(r => r.correct).length });
        return;
      }
      setPhase('intro');
      onComplete?.();
    } else {
      setIdx(i => i + 1);
      setPhase('playing');
    }
  }

  // Clean up if component unmounts mid-recording. Depend on the stable stop
  // callback only: `recorder` is a fresh object whenever its state or timer
  // changes, so depending on the object would stop the recording the moment
  // it starts (and again on every seconds tick).
  const stopRecording = recorder.stop;
  useEffect(() => () => { void stopRecording(); }, [stopRecording]);

  if (phase === 'intro') {
    if (dailyMode) {
      return (
        <Card>
          <div className="exercise-intro">
            <span className="intro-emoji" aria-hidden>🗣️</span>
            <h3>Say the word</h3>
            {error && <ErrBanner error={error} onGuardian={onGuardianHelp} />}
            {error ? (
              <button className="btn primary btn-lg mt-2" onClick={startRound} disabled={busy}>
                {busy && <BtnSpinner />}
                Try again
              </button>
            ) : (
              <Spinner label="Preparing words..." />
            )}
          </div>
        </Card>
      );
    }
    return (
      <Card>
        <div className="exercise-intro">
          <span className="intro-emoji" aria-hidden>🗣️</span>
          <h3>Say the word</h3>
          <p className="muted">
            Words will drift across the screen in different fonts. Listen, look,
            and say each word out loud. We&apos;ll check your pronunciation.
          </p>
          {error && <ErrBanner error={error} onGuardian={onGuardianHelp} />}
          <button className="btn primary btn-lg mt-2" onClick={startRound} disabled={busy}>
            {busy && <BtnSpinner />}
            {busy ? 'Loading words…' : results.length ? 'Play again' : 'Start'}
          </button>
          {busy && <Skeleton className="skeleton-stage mt-3" />}
          {results.length > 0 && !busy && <ScoreSummary results={results} />}
        </div>
      </Card>
    );
  }

  if (!current) return <div className="spinner-center"><Spinner label="Preparing words..." /></div>;

  return (
    <Card className="elevated">
      <ProgressDots total={items.length} current={idx} results={results} />
      {phase === 'playing' ? (
        <PlayingStage item={current} recorder={recorder} onSubmit={submitAudio} busy={busy} error={error} onGuardianHelp={onGuardianHelp} />
      ) : (
        <FeedbackStage
          item={current}
          result={results[results.length - 1]}
          onNext={next}
          isLast={idx + 1 >= items.length}
        />
      )}
    </Card>
  );
}

function ProgressDots({ total, current, results }: { total: number; current: number; results: Ex1CheckResult[] }) {
  return (
    <div className="progress-dots">
      {Array.from({ length: total }).map((_, i) => {
        const r = results[i];
        const cls = r
          ? (r.correct ? 'dot is-correct' : 'dot is-wrong')
          : (i === current ? 'dot is-current' : 'dot is-pending');
        return (
          <span
            key={i}
            className={cls}
            aria-label={r ? (r.correct ? 'correct' : 'try again') : i === current ? 'current' : 'pending'}
          />
        );
      })}
    </div>
  );
}

function PlayingStage({
  item, recorder, onSubmit, busy, error, onGuardianHelp,
}: {
  item: Ex1Item;
  recorder: ReturnType<typeof useRecorder>;
  onSubmit: () => void;
  busy: boolean;
  error: string | null;
  onGuardianHelp?: () => void;
}) {
  const recording = recorder.state === 'recording';

  return (
    <div className="stack mt-2">
      <div className="stage" aria-live="polite">
        <span
          key={item.word_id}
          className="drift-word"
          style={{
            fontFamily: `"${item.font}", var(--font-body)`,
          }}
        >
          {item.text}
        </span>
      </div>

      <div className="row-between">
        <span className="tag lilac">font: {item.font}</span>
        <SoundButton src={api.ex1AudioUrl(item.text)} label="Hear the word" />
      </div>

      {recorder.state === 'denied' && (
        <Banner kind="err">Microphone access was blocked. Enable it in your browser settings.</Banner>
      )}
      {error && <ErrBanner error={error} onGuardian={onGuardianHelp} />}

      <div className="row-center mt-2">
        {!recording ? (
          <button className="btn primary" onClick={recorder.start} disabled={busy}>
            {busy && <BtnSpinner />}
            🎤 Hold to speak
          </button>
        ) : (
          <button
            className={`btn coral${busy ? '' : ' is-listening'}`}
            onClick={onSubmit}
            disabled={busy}
          >
            {busy && <BtnSpinner />}
            ■ Stop &amp; check ({recorder.seconds}s)
          </button>
        )}
        {busy && <Spinner label="Checking your pronunciation…" />}
      </div>
      <p className="muted center-text mt-0">
        Tip: hold the mic and say it loud — big and bold! 🎤
      </p>
    </div>
  );
}

function FeedbackStage({
  item, result, onNext, isLast,
}: {
  item: Ex1Item;
  result: Ex1CheckResult;
  onNext: () => void;
  isLast: boolean;
}) {
  return (
    <div className="stack mt-2">
      {result.correct && <Confetti />}
      <div className={`feedback-sheet ${result.correct ? 'ok' : 'err'}`} role="status">
        <div className="feedback-head">
          <span className="feedback-icon" aria-hidden>{result.correct ? '🎉' : '💪'}</span>
          <div>
            <h3>{result.correct ? 'Great job!' : 'Almost there!'}</h3>
            <p className="muted">
              {result.transcript && result.similarity >= TRANSCRIPT_MIN_SIMILARITY
                ? <>You said &ldquo;{result.transcript}&rdquo; · </>
                : <>{result.transcript ? 'We couldn’t match that clearly' : 'We didn’t catch that'} · </>}
              match {Math.round(result.similarity * 100)}% (needed {Math.round(result.threshold * 100)}%)
            </p>
          </div>
        </div>
        <div className="row-between">
          <span className="tag sky">word: {item.text}</span>
          <span className="tag mint">strength: {Math.round(result.new_strength * 100)}%</span>
        </div>
        <button className="btn lilac btn-lg feedback-next" onClick={onNext}>
          {isLast ? 'Finish' : 'Continue'}
        </button>
      </div>
    </div>
  );
}

function ScoreSummary({ results }: { results: Ex1CheckResult[] }) {
  const correct = results.filter(r => r.correct).length;
  const total = results.length;
  return (
    <div className="row-center mt-3">
      <span className="tag mint">✓ {correct} correct</span>
      <span className="tag rose">✗ {total - correct} to practice</span>
      <span className="muted">across {total} words</span>
    </div>
  );
}
