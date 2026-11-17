import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Lightweight microphone recorder using MediaRecorder. Returns a WebM/Opus
// Blob suitable for the backend's STT endpoint. No external deps.

export type RecorderState = 'idle' | 'recording' | 'denied' | 'error';

export function useRecorder() {
  const [state, setState] = useState<RecorderState>('idle');
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.start();
      recorderRef.current = rec;
      setState('recording');
      setSeconds(0);
      timerRef.current = window.setInterval(() => setSeconds(s => s + 1), 1000);
    } catch (err) {
      const name = (err as { name?: string }).name;
      if (name === 'NotAllowedError' || name === 'SecurityError') setState('denied');
      else setState('error');
    }
  }, []);

  const stop = useCallback((): Promise<Blob | null> => {
    const rec = recorderRef.current;
    if (!rec || rec.state === 'inactive') {
      stopTracks();
      setState('idle');
      return Promise.resolve(null);
    }
    return new Promise(resolve => {
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
        stopTracks();
        setState('idle');
        setSeconds(0);
        resolve(blob);
      };
      rec.stop();
    });
  }, [stopTracks]);

  useEffect(() => () => stopTracks(), [stopTracks]);

  return useMemo(() => ({ state, seconds, start, stop }), [state, seconds, start, stop]);
}
