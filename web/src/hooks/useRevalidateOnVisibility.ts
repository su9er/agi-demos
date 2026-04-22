import { useEffect } from 'react';

/**
 * Fallback for WS half-open: when the tab becomes visible after being hidden,
 * force a refresh callback. Complements the WS watchdog (which handles
 * background / still-visible cases) — here we catch the laptop-sleep case
 * where both the watchdog timer and the OS have been frozen.
 *
 * Borrowed from multica HANDOFF_ARCHITECTURE_AUDIT.md option B.
 */
export function useRevalidateOnVisibility(callback: () => void, enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    const handler = () => {
      if (document.visibilityState === 'visible') {
        callback();
      }
    };
    document.addEventListener('visibilitychange', handler);
    return () => {
      document.removeEventListener('visibilitychange', handler);
    };
  }, [callback, enabled]);
}
