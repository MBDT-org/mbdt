// Typed client for the MBDT backend. In dev, Vite proxies /api -> 127.0.0.1:8777
// (see vite.config.ts), so we use relative paths and avoid any CORS/env setup.

import { notifyServiceError } from './toast';

export class ApiError extends Error {
  code: string | null;
  model: string | null;
  status: number;
  constructor(
    message: string,
    opts: { code: string | null; model: string | null; status: number },
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = opts.code;
    this.model = opts.model;
    this.status = opts.status;
  }
}

export interface Learner {
  id: number;
  name: string;
  created_at: string;
  composite_score: number;
  word_accuracy: number;
  comprehension_accuracy: number;
  guardian: Guardian | null;
}

export interface Guardian {
  learner_id: number;
  word_set_id: number | null;
  word_set: string | null;
  interests: string;
  safety_categories: string;
  confidence_floor: number;
  llm_model: string | null;
  updated_at: string;
}

export interface WordSetInfo {
  id: string;
  label: string;
}

export interface Health {
  status: string;
  api_key_configured: boolean;
  provider: 'requesty' | 'openrouter';
  provider_label: string;
  models: { llm: string; ocr: string; tts: string; stt: string };
}

export interface Ex1Item {
  word_id: number;
  text: string;
  phoneme: string | null;
  font: string;
}
export interface Ex1Round {
  items: Ex1Item[];
  confidence_floor: number;
}
export interface Ex1CheckResult {
  word: string;
  transcript: string;
  similarity: number;
  threshold: number;
  correct: boolean;
  confidence: number;
  stt_confidence: number | null;
  new_strength: number;
}

export interface Ex3SpellItem {
  word_id: number;
  phoneme: string | null;
}
export interface Ex3SpellRound {
  items: Ex3SpellItem[];
}
export interface Ex3SpellCheckResult {
  word: string;
  submitted: string;
  similarity: number;
  correct: boolean;
  new_strength: number;
  /** True when the photo/drawing could not be read; nothing was scored. */
  ocr_failed?: boolean;
  message?: string;
}
export interface Ex3CategorizeOption {
  word_id: number;
  text: string;
}
export interface Ex3CategorizeRound {
  phoneme: string;
  options: Ex3CategorizeOption[];
}
export interface Ex3CategorizeResult {
  phoneme: string;
  correct_ids: number[];
  incorrect_ids: number[];
  missed_count: number;
  target_ids: number[];
  score: number;
}

export interface Ex5Question {
  question: string;
  expected: string;
}
export interface Ex5Story {
  story_id: number;
  text: string;
  target_words: string[];
  questions: Ex5Question[];
}
export interface Ex5Answer {
  question: string;
  expected: string;
  given: string;
}
export interface Ex5CheckResult {
  story_id: number;
  answered: number;
  correct: number;
  accuracy: number;
}

export interface DailyStatus { date: string; completed: boolean; skipped: boolean; xp_today: number; }

export interface Streak {
  days: number;
  practiced_today: boolean;
}
export interface Ability {
  key: 'speaking' | 'spelling' | 'recognition' | 'comprehension';
  label: string;
  emoji: string;
  accuracy: number | null;
  attempts: number;
}
export interface WordInfo {
  text: string;
  phoneme: string | null;
  mastery: number;
  attempts: number;
  last: string | null;
}
export interface WordTier {
  key: 'mastered' | 'familiar' | 'learning' | 'new';
  label: string;
  words: WordInfo[];
}
export interface Quest {
  key: 'items' | 'correct' | 'session';
  emoji: string;
  label: string;
  target: number;
  progress: number;
  done: boolean;
}
export interface TodayStats {
  reviews: number;
  correct: number;
  xp: number;
}
export interface Dashboard {
  streak: Streak;
  abilities: Ability[];
  word_tiers: WordTier[];
  xp: number;
  level: number;
  level_start: number;
  level_next: number;
  level_progress: number;
  today: TodayStats;
  quests: Quest[];
}

// Ceiling on any single API call. The backend's own retry ceiling is ~2min;
// beyond that the request is dead and the UI should show an error, not spin.
const REQUEST_TIMEOUT_MS = 120_000;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'TimeoutError')
      throw new Error('Request timed out — please try again', { cause: e });
    throw e;
  }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    let code: string | null = null;
    let model: string | null = null;
    let hasCode = false;
    try {
      const body = await res.json();
      if (body?.detail) {
        if (typeof body.detail === 'string') {
          msg = body.detail;
        } else if (
          typeof body.detail === 'object' && typeof body.detail.code === 'string'
        ) {
          hasCode = true;
          code = body.detail.code;
          model = typeof body.detail.model === 'string' ? body.detail.model : null;
          msg = String(body.detail.message ?? JSON.stringify(body.detail));
        } else {
          msg = JSON.stringify(body.detail);
        }
      }
    } catch { /* ignore */ }
    if (hasCode && code) notifyServiceError(code, model);
    throw new ApiError(msg, { code, model, status: res.status });
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) return res.json() as Promise<T>;
  return (await res.text()) as unknown as T;
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req<Health>('/api/health'),
  listLearners: () => req<Learner[]>('/api/learners'),
  createLearner: (name: string) => req<{ id: number; name: string }>('/api/learners', json({ name })),
  getLearner: (id: number) => req<Learner>(`/api/learners/${id}`),
  getDashboard: (id: number) => req<Dashboard>(`/api/learners/${id}/dashboard`),
  updateGuardian: (id: number, body: Partial<{
    word_set: string; interests: string; safety_categories: string;
    confidence_floor: number; llm_model: string;
  }>) => req<{ ok: boolean; guardian: Guardian }>(`/api/learners/${id}/guardian`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  listWordSets: () => req<{ sets: WordSetInfo[] }>('/api/word-sets'),

  // Exercise 1
  ex1Round: (learnerId: number, n = 8) => req<Ex1Round>(`/api/exercise1/${learnerId}/round?n=${n}`),
  ex1AudioUrl: (word: string) => `/api/exercise1/${encodeURIComponent(word)}/audio`,
  ex1Check: (learnerId: number, wordId: number, font: string, audio: Blob) => {
    const fd = new FormData();
    fd.append('word_id', String(wordId));
    fd.append('font', font);
    // Keep the real container: Safari records audio/mp4, Chrome audio/webm.
    const subtype = (audio.type.split(';')[0].split('/')[1] || 'webm').replace('mpeg', 'mp3');
    fd.append('audio', audio, `audio.${subtype}`);
    return req<Ex1CheckResult>(`/api/exercise1/${learnerId}/check`, { method: 'POST', body: fd });
  },

  // Exercise 3
  ex3SpellRound: (learnerId: number, n = 6) => req<Ex3SpellRound>(`/api/exercise3/${learnerId}/spell?n=${n}`),
  ex3WordAudioUrl: (word: string) => `/api/exercise3/word/${encodeURIComponent(word)}/audio`,
  ex3WordAudioByIdUrl: (learnerId: number, wordId: number) =>
    `/api/exercise3/learner/${learnerId}/word-id/${wordId}/audio`,
  ex3SpellCheck: (learnerId: number, wordId: number, submitted: string, imageDataUrl?: string) =>
    req<Ex3SpellCheckResult>(`/api/exercise3/${learnerId}/spell/check`, json({
      word_id: wordId, submitted, image_data_url: imageDataUrl,
    })),
  ex3CategorizeRound: (learnerId: number, nOptions = 6) =>
    req<Ex3CategorizeRound>(`/api/exercise3/${learnerId}/categorize?n_options=${nOptions}`),
  ex3CategorizeCheck: (learnerId: number, phoneme: string, selectedWordIds: number[], optionWordIds: number[]) =>
    req<Ex3CategorizeResult>(`/api/exercise3/${learnerId}/categorize/check`, json({
      phoneme, selected_word_ids: selectedWordIds, option_word_ids: optionWordIds,
    })),

  // Exercise 5
  ex5Story: (learnerId: number, nWords = 8) => req<Ex5Story>(`/api/exercise5/${learnerId}/story?n_words=${nWords}`),
  ex5Check: (learnerId: number, storyId: number, answers: Ex5Answer[]) =>
    req<Ex5CheckResult>(`/api/exercise5/${learnerId}/check`, json({ story_id: storyId, answers })),

  ttsUrl: (text: string, voice?: string) =>
    `/api/tts?text=${encodeURIComponent(text)}${voice ? `&voice=${voice}` : ''}`,

  // Daily practice session + admin/demo affordances
  dailyStatus: (learnerId: number) => req<DailyStatus>(`/api/daily/${learnerId}/status`),
  dailyComplete: (learnerId: number) => req<DailyStatus>(`/api/daily/${learnerId}/complete`, json({})),
  dailySkip: (learnerId: number, password: string) =>
    req<DailyStatus>(`/api/daily/${learnerId}/skip`, json({ password })),
  dailyReset: (learnerId: number, password: string) =>
    req<DailyStatus>(`/api/daily/${learnerId}/reset`, json({ password })),
  adminVerify: (password: string) => req<{ ok: boolean }>('/api/admin/verify', json({ password })),
  adminSetPassword: (current: string, next: string) =>
    req<{ ok: boolean }>('/api/admin/password', json({ current, new: next })),
};
