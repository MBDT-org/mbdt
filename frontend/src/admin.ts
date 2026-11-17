// In-memory admin unlock for demo affordances (skip-a-day, resets, stage skip).
// The password lives in a module variable ONLY — never localStorage — so a page
// reload relocks everything, which is the intended (and safer) behavior.

let adminPw: string | null = null;

export function unlock(pw: string): void {
  adminPw = pw;
}

export function lock(): void {
  adminPw = null;
}

export function getAdminPw(): string | null {
  return adminPw;
}

export function isUnlocked(): boolean {
  return adminPw != null;
}
