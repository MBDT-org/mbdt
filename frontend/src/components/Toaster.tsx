import { useEffect, useRef, useState } from 'react';
import { onToast, dismissToast, type Toast } from '../toast';

export function Toaster({ onOpenSetup }: { onOpenSetup: () => void }) {
  const [queue, setQueue] = useState<Toast[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  useEffect(() => {
    const timersMap = timers.current;
    const unsub = onToast(t => {
      // Empty text === dismiss tombstone (see toast.ts).
      if (t.text === '') {
        const handle = timersMap.get(t.id);
        if (handle) { clearTimeout(handle); timersMap.delete(t.id); }
        setQueue(q => q.filter(x => x.id !== t.id));
        return;
      }
      setQueue(q => [...q, t].slice(-3)); // cap 3, drop oldest
      const handle = setTimeout(() => dismissToast(t.id), 10_000);
      timersMap.set(t.id, handle);
    });
    return () => {
      unsub();
      timersMap.forEach(h => clearTimeout(h));
      timersMap.clear();
    };
  }, []);

  function runAction(id: number) {
    onOpenSetup();
    dismissToast(id);
  }

  return (
    <div className="toast-stack">
      {queue.map(t => (
        <div
          key={t.id}
          className={`toast ${t.kind}`}
          role={t.kind === 'err' ? 'alert' : 'status'}
        >
          <span className="toast-text">{t.text}</span>
          {t.action === 'open-setup' && (
            <button type="button" className="linklike toast-action" onClick={() => runAction(t.id)}>
              Open setup →
            </button>
          )}
          <button type="button" className="toast-close" aria-label="Dismiss notification" onClick={() => dismissToast(t.id)}>×</button>
        </div>
      ))}
    </div>
  );
}
