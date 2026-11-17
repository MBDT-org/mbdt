import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { celebrationsEnabled } from '../celebrations';

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Banner({ kind, children }: { kind: 'ok' | 'warn' | 'err'; children: ReactNode }) {
  return <div className={`banner ${kind}`}>{children}</div>;
}

/** Error banner that offers a jump to guardian setup when the failure looks
    like a service/key problem (503, missing key, provider rejection). */
export function ErrBanner({ error, onGuardian }: { error: string | null; onGuardian?: () => void }) {
  if (!error) return null;
  const servicey = /503|unavailable|api key|failed|not approved/i.test(error);
  return (
    <Banner kind="err">
      {error}
      {servicey && onGuardian && (
        <>
          {' '}
          <button type="button" className="linklike" onClick={onGuardian}>
            Guardian setup →
          </button>
        </>
      )}
    </Banner>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="spinner" role="status">
      <span className="spinner-ring" aria-hidden />
      {label && <span className="muted">{label}</span>}
    </div>
  );
}

/** Tiny white ring for inside colored buttons (busy state). */
export function BtnSpinner() {
  return <span className="btn-spinner" aria-hidden />;
}

/* ---- Sound button (replaces the native <audio> transport bar) ----------- */

export function SoundButton({ src, label = 'Hear it', className = 'amber' }: {
  src: string;
  label?: string;
  className?: string;
}) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const a = new Audio(src);
    audioRef.current = a;
    const onPlay = () => setPlaying(true);
    const onStop = () => setPlaying(false);
    a.addEventListener('play', onPlay);
    a.addEventListener('ended', onStop);
    a.addEventListener('pause', onStop);
    return () => {
      a.pause();
      a.removeEventListener('play', onPlay);
      a.removeEventListener('ended', onStop);
      a.removeEventListener('pause', onStop);
    };
  }, [src]);

  function toggle() {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) {
      a.currentTime = 0;
      void a.play().catch(() => setPlaying(false));
    } else {
      a.pause();
    }
  }

  return (
    <button
      type="button"
      className={`btn ${className} btn-sm sound-btn`}
      onClick={toggle}
      aria-pressed={playing}
    >
      <span aria-hidden>{playing ? '⏸' : '🔊'}</span> {playing ? 'Playing…' : label}
    </button>
  );
}

/* ---- Toggle -------------------------------------------------------------- */

export function Toggle({ id, label, hint, checked, onChange, disabled }: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="toggle-field">
      <span className="toggle-text" id={`${id}-label`}>
        {label}
        {hint && <span className="muted field-hint">{hint}</span>}
      </span>
      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        className={`toggle${checked ? ' is-on' : ''}`}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className="toggle-track" aria-hidden>
          <span className="toggle-thumb" />
        </span>
      </button>
    </div>
  );
}

/* ---- Select (custom dropdown, no native <select>) ------------------------- */

export interface SelectOption {
  value: string;
  label: string;
}

/** Keyboard model: focus stays on the trigger; Enter/Space/arrows open,
    arrows/Home/End move the active option, Enter/Space commit, Esc closes,
    printable chars typeahead-jump. */
export function Select({ id, value, options, onChange, disabled, ariaLabel }: {
  id?: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  const autoId = useId();
  const baseId = id ?? autoId;
  const [open, setOpen] = useState(false);
  const selected = Math.max(0, options.findIndex(o => o.value === value));
  const [active, setActive] = useState(selected);
  const rootRef = useRef<HTMLDivElement>(null);

  // No selected->active sync effect; every open resets active to
  // selected, and value can't change while the list is open.

  // Click-away closes the list.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  // Keep the active option visible while arrowing through a long list.
  useEffect(() => {
    if (!open) return;
    rootRef.current
      ?.querySelector('.select-option.is-active')
      ?.scrollIntoView({ block: 'nearest' });
  }, [open, active]);

  function commit(i: number) {
    const o = options[i];
    if (!o) return;
    onChange(o.value);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (disabled || options.length === 0) return;
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); // also suppresses the button's native Space/Enter click
        setActive(selected);
        setOpen(true);
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActive(a => (a + 1) % options.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActive(a => (a - 1 + options.length) % options.length);
        break;
      case 'Home':
        e.preventDefault();
        setActive(0);
        break;
      case 'End':
        e.preventDefault();
        setActive(options.length - 1);
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        commit(active);
        break;
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        break;
      case 'Tab':
        setOpen(false);
        break;
      default:
        // Single-char typeahead, first match after the active one
        if (e.key.length === 1 && /\S/.test(e.key)) {
          const q = e.key.toLowerCase();
          for (let k = 1; k <= options.length; k++) {
            const j = (active + k) % options.length;
            if (options[j].label.toLowerCase().startsWith(q)) { setActive(j); break; }
          }
        }
    }
  }

  const current = options[selected];
  return (
    <div className={`select${open ? ' is-open' : ''}`} ref={rootRef} onKeyDown={onKeyDown}>
      <button
        type="button"
        id={baseId}
        className="input select-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-activedescendant={open ? `${baseId}-opt-${active}` : undefined}
        aria-label={ariaLabel}
        onClick={() => { setActive(selected); setOpen(o => !o); }}
      >
        <span className="select-value">{current?.label ?? 'Select…'}</span>
        <span className="select-chevron" aria-hidden>▾</span>
      </button>
      {open && (
        <ul className="select-list" role="listbox" aria-labelledby={ariaLabel ? undefined : baseId} aria-label={ariaLabel}>
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${baseId}-opt-${i}`}
              role="option"
              aria-selected={o.value === value}
              className={`select-option${i === active ? ' is-active' : ''}${o.value === value ? ' is-selected' : ''}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={e => e.preventDefault() /* keep focus on the trigger */}
              onClick={() => commit(i)}
            >
              <span>{o.label}</span>
              {o.value === value && <span aria-hidden>✓</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ---- Skeleton ------------------------------------------------------------ */

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/* ---- Progress bar --------------------------------------------------------- */

export function ProgressBar({ value, max, label, className = '' }: {
  value: number;
  max: number;
  label?: string;
  className?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div
      className={`pbar ${className}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={label}
    >
      <span className="pbar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ---- Confetti --------------------------------------------------------------- */

const CONFETTI_COLORS = ['#58CC02', '#1CB0F6', '#FFC800', '#CE82FF', '#FF4B4B'];

/** Deterministic pseudo-random so re-renders don't reshuffle the burst. */
function crand(i: number, salt: number): number {
  const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

/** CSS-only confetti burst from the top-center of the viewport. Respects the
    guardian "Celebration confetti" toggle and (via the blanket CSS rule)
    prefers-reduced-motion. Self-removes after the animation ends. */
export function Confetti({ count = 26 }: { count?: number }) {
  const [gone, setGone] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setGone(true), 1700);
    return () => clearTimeout(t);
  }, []);
  if (gone || !celebrationsEnabled()) return null;
  return (
    <div className="confetti" aria-hidden>
      {Array.from({ length: count }, (_, i) => {
        const style = {
          '--x': `${(crand(i, 1) - 0.5) * 70}vw`,
          '--y': `${26 + crand(i, 2) * 40}vh`,
          '--r': `${(crand(i, 3) - 0.5) * 720}deg`,
          '--d': `${crand(i, 4) * 0.18}s`,
          '--c': CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        } as CSSProperties;
        return <span key={i} className="confetti-piece" style={style} />;
      })}
    </div>
  );
}
