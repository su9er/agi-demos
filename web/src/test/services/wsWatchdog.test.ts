import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { attachWatchdog } from '@/services/client/wsWatchdog';

// WebSocket global may be undefined in the jsdom test env; use numeric
// constants per the WHATWG spec (OPEN=1, CLOSED=3).
class FakeWebSocket {
  readyState = 1; // OPEN
  closed = false;
  closeCode?: number;
  close(code?: number) {
    this.closed = true;
    this.closeCode = code;
    this.readyState = 3; // CLOSED
  }
}

describe('attachWatchdog', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('closes the socket when no messages arrive within staleAfterMs', () => {
    const fake = new FakeWebSocket();
    attachWatchdog(fake as unknown as WebSocket, {
      staleAfterMs: 1000,
      checkIntervalMs: 5000,
    });
    vi.advanceTimersByTime(5001);
    expect(fake.closed).toBe(true);
    expect(fake.closeCode).toBe(4000);
  });

  it('does not close when notifyMessage is called within the window', () => {
    const fake = new FakeWebSocket();
    const wd = attachWatchdog(fake as unknown as WebSocket, {
      staleAfterMs: 1000,
      checkIntervalMs: 5000,
    });
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(800);
      wd.notifyMessage();
    }
    expect(fake.closed).toBe(false);
  });

  it('stop() prevents further close calls', () => {
    const fake = new FakeWebSocket();
    const wd = attachWatchdog(fake as unknown as WebSocket, {
      staleAfterMs: 1000,
      checkIntervalMs: 5000,
    });
    wd.stop();
    vi.advanceTimersByTime(10_000);
    expect(fake.closed).toBe(false);
  });

  it('invokes custom onStale instead of ws.close when provided', () => {
    const fake = new FakeWebSocket();
    const onStale = vi.fn();
    attachWatchdog(fake as unknown as WebSocket, {
      staleAfterMs: 1000,
      checkIntervalMs: 5000,
      onStale,
    });
    vi.advanceTimersByTime(5001);
    expect(onStale).toHaveBeenCalledWith(fake);
    expect(fake.closed).toBe(false);
  });
});
