// Guardian-controlled flag for celebration effects (confetti bursts).
// Stored in localStorage so it survives restarts of the local app.

const CELEBRATIONS_KEY = 'mbdt.celebrations';

export function celebrationsEnabled(): boolean {
  try { return localStorage.getItem(CELEBRATIONS_KEY) !== 'off'; } catch { return true; }
}

export function setCelebrationsEnabled(on: boolean) {
  try { localStorage.setItem(CELEBRATIONS_KEY, on ? 'on' : 'off'); } catch { /* private mode */ }
}
