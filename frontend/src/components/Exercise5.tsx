import { useCallback, useEffect, useState } from 'react';
import { api, type Ex5Story, type Ex5Answer } from '../api';
import { BtnSpinner, Card, Confetti, ErrBanner, Skeleton } from './ui';
import type { DailyRunProps } from './Exercise1';

interface Props {
  learnerId: number;
  onComplete?: () => void;
  onGuardianHelp?: () => void;
  daily?: DailyRunProps;
}

/* Story generation takes ~8-10s, so the wait gets its own little scene:
   a bobbing book, floating sparks, rotating status lines and a story-shaped
   skeleton so the delay feels like something is happening. */
const STORY_STAGES = [
  'Picking just-right words…',
  'Writing your story…',
  'Adding fun details…',
  'Checking every page…',
];

function StoryWait() {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStage(s => (s + 1) % STORY_STAGES.length), 2400);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="story-wait" role="status" aria-live="polite">
      <div className="story-wait-scene" aria-hidden>
        <span className="story-wait-book">📖</span>
        <span className="story-wait-spark s1">✨</span>
        <span className="story-wait-spark s2">⭐</span>
        <span className="story-wait-spark s3">✏️</span>
      </div>
      {/* key restarts the msg-swap animation on each stage change. */}
      <p key={stage} className="story-wait-msg">{STORY_STAGES[stage]}</p>
      <div className="story-wait-skels" aria-hidden>
        <Skeleton className="skeleton-line" />
        <Skeleton className="skeleton-line" />
        <Skeleton className="skeleton-line" />
      </div>
    </div>
  );
}

export function Exercise5({ learnerId, onComplete, onGuardianHelp, daily }: Props) {
  const [story, setStory] = useState<Ex5Story | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ correct: number; total: number; accuracy: number } | null>(null);

  const loadStory = useCallback(async () => {
    setBusy(true); setError(null); setResult(null); setAnswers([]);
    try {
      const s = await api.ex5Story(learnerId, 8);
      setStory(s);
      setAnswers(new Array(s.questions.length).fill(''));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }, [learnerId]);

  // Daily mode: no intro screen, the story loads on mount. Deferred a tick so
  // the effect body itself stays free of synchronous setState.
  const dailyMode = daily != null;
  useEffect(() => {
    if (!dailyMode) return;
    const t = setTimeout(() => { void loadStory(); }, 0);
    return () => clearTimeout(t);
  }, [dailyMode, loadStory]);

  async function submit() {
    if (!story) return;
    setBusy(true); setError(null);
    try {
      const payload: Ex5Answer[] = story.questions.map((q, i) => ({
        question: q.question,
        expected: q.expected,
        given: answers[i] ?? '',
      }));
      const res = await api.ex5Check(learnerId, story.story_id, payload);
      setResult({ correct: res.correct, total: res.answered, accuracy: res.accuracy });
      daily?.onProgress?.(1, 1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function done() {
    if (daily?.onFinish && result) {
      daily.onFinish({ attempted: result.total, correct: result.correct });
      return;
    }
    onComplete?.();
    setStory(null); setResult(null); setAnswers([]);
  }

  if (!story) {
    return (
      <Card>
        <div className="exercise-intro">
          <span className="intro-emoji" aria-hidden>📖</span>
          <h3>Read a story</h3>
          <p className="muted">
            A short story is generated from words you&apos;ve been practicing.
            Read it, then answer three questions.
          </p>
          {error && <ErrBanner error={error} onGuardian={onGuardianHelp} />}
          {(!dailyMode || error) && (
            <button className="btn lilac btn-lg mt-2" onClick={loadStory} disabled={busy}>
              {busy && <BtnSpinner />}
              {busy ? 'Writing your story…' : dailyMode ? 'Try again' : 'Generate story'}
            </button>
          )}
          {busy && <StoryWait />}
        </div>
      </Card>
    );
  }

  return (
    <Card className="elevated">
      <div className="row-between">
        <h3 className="mt-0">Read a story</h3>
        <span className="muted">{result ? 'Results' : 'Reading'}</span>
      </div>

      {busy ? (
        <StoryWait />
      ) : (
        <article className="story rise-in mt-3">
          {story.text.split(/(\s+)/).map((tok, i) => {
            const clean = tok.replace(/[^a-zA-Z]/g, '').toLowerCase();
            const isTarget = story.target_words.map(w => w.toLowerCase()).includes(clean);
            return isTarget
              ? <mark key={i}>{tok}</mark>
              : <span key={i}>{tok}</span>;
          })}
        </article>
      )}

      <div className="target-words mt-2">
        <span className="muted">Target words in this story:</span>{' '}
        {story.target_words.map(w => <span key={w} className="tag mint">{w}</span>)}
      </div>

      <div className="stack mt-4">
        {story.questions.map((q, i) => (
          <div key={i} className="question">
            <label className="question-label" htmlFor={`q-${i}`}>
              <strong>Q{i + 1}.</strong> {q.question}
            </label>
            <input
              id={`q-${i}`}
              className="input"
              value={answers[i] ?? ''}
              disabled={!!result || busy}
              onChange={e => setAnswers(prev => { const n = [...prev]; n[i] = e.target.value; return n; })}
            />
            {result && (
              <div className="reveal">
                Answer: <strong className="reveal-answer">{q.expected}</strong> · You: <strong className="reveal-yours">{answers[i] || '(no answer)'}</strong>
              </div>
            )}
          </div>
        ))}
      </div>

      {error && <div className="mt-3"><ErrBanner error={error} onGuardian={onGuardianHelp} /></div>}

      {result && (
      <div className="stack questions mt-4">
          {result.accuracy >= 0.7 && <Confetti />}
          <div className={`feedback-sheet ${result.accuracy >= 0.7 ? 'ok' : 'warn'}`} role="status">
            <div className="feedback-head">
              <span className="feedback-icon" aria-hidden>{result.accuracy >= 0.7 ? '🎉' : '📚'}</span>
              <div>
                <h3>{result.accuracy >= 0.7 ? 'Nice reading!' : 'Good try'}</h3>
                <p className="muted">
                  {result.correct} of {result.total} questions correct ·{' '}
                  {Math.round(result.accuracy * 100)}%
                </p>
              </div>
            </div>
            <div className="row-center">
              <button className="btn primary btn-lg" onClick={done}>Finish</button>
              {!dailyMode && (
                <button className="btn lilac" onClick={loadStory} disabled={busy}>
                  {busy && <BtnSpinner />}
                  {busy ? 'Writing…' : 'New story'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {!result && (
        <div className="row-center mt-4">
          <button className="btn primary" onClick={submit} disabled={busy || answers.some(a => !a.trim())}>
            {busy && <BtnSpinner />}
            {busy ? 'Checking…' : 'Check answers'}
          </button>
        </div>
      )}
    </Card>
  );
}
