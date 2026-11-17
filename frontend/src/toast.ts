// Toast emitter for service errors. Plain module (no React) so api.ts can fire
// toasts without importing the component tree. The Toaster component subscribes.
//
// Dismiss is signalled to listeners as a tombstone Toast with an empty
// `text`; the Toaster treats text==='' as "remove id". Keeps the (t: Toast) => void
// callback signature single-purpose. A real toast never has empty text.

export type ServiceErrorCode =
  | 'no_api_key' | 'auth_failed' | 'model_not_approved' | 'model_not_found'
  | 'model_unavailable'
  | 'rate_limited' | 'length_truncated' | 'network_error' | 'upstream_error'
  | 'insufficient_credits';

export type ToastAction = 'open-setup';

export interface Toast {
  id: number;
  kind: 'err' | 'warn';
  text: string;
  action?: ToastAction;
}

type Listener = (t: Toast) => void;

const listeners = new Set<Listener>();
let nextId = 1;
const lastFired = new Map<string, number>();
const DEDUP_MS = 10_000;

interface MsgSpec {
  kind: 'err' | 'warn';
  text: (model: string | null) => string;
  action?: ToastAction;
}

const MESSAGES: Record<ServiceErrorCode, MsgSpec> = {
  no_api_key: {
    kind: 'err',
    text: () => 'No AI gateway API key configured — add MBDT_REQUESTY_API_KEY or MBDT_OPENROUTER_API_KEY to backend/.env and restart.',
    action: 'open-setup',
  },
  auth_failed: {
    kind: 'err',
    text: () => 'The AI gateway rejected the API key — check your key and MBDT_PROVIDER in backend/.env.',
    action: 'open-setup',
  },
  model_not_approved: {
    kind: 'err',
    text: m => `The model “${m ?? 'this model'}” isn’t available to this API key — approve it with your gateway or change the MBDT_*_MODEL setting in backend/.env.`,
    action: 'open-setup',
  },
  model_not_found: {
    kind: 'err',
    text: m => `The model “${m ?? 'this model'}” doesn’t exist on the gateway — check the model id in backend/.env.`,
    action: 'open-setup',
  },
  model_unavailable: {
    kind: 'err',
    text: m => `The model “${m ?? 'this model'}” isn’t available to your account right now (provider or region restriction) — allow more providers in your gateway settings or choose another model in backend/.env.`,
    action: 'open-setup',
  },
  insufficient_credits: {
    kind: 'err',
    text: () => 'The AI gateway account is out of credits — top up, or switch gateway in backend/.env and restart.',
    action: 'open-setup',
  },
  length_truncated: {
    kind: 'warn',
    text: () => 'The AI’s answer was cut off (token limit) — try again, or switch to a lighter model in backend/.env.',
    action: 'open-setup',
  },
  rate_limited: {
    kind: 'warn',
    text: () => 'Rate limited by the AI gateway — wait a few seconds and try again.',
  },
  network_error: {
    kind: 'warn',
    text: () => 'The AI service is unreachable right now — please try again shortly.',
  },
  upstream_error: {
    kind: 'warn',
    text: () => 'The AI service is unreachable right now — please try again shortly.',
  },
};

export function onToast(cb: Listener): () => void {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

export function dismissToast(id: number): void {
  const tombstone: Toast = { id, kind: 'err', text: '' };
  listeners.forEach(cb => cb(tombstone));
}

export function notifyServiceError(code: string | null, model: string | null): void {
  if (!code) return;
  const spec = MESSAGES[code as ServiceErrorCode];
  if (!spec) return; // unknown / inline-only codes (bad_response, empty_response) -> no toast
  const now = Date.now();
  if (now - (lastFired.get(code) ?? 0) < DEDUP_MS) return;
  lastFired.set(code, now);
  const toast: Toast = { id: nextId++, kind: spec.kind, text: spec.text(model), action: spec.action };
  listeners.forEach(cb => cb(toast));
}
