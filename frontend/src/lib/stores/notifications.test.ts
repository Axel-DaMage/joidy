import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/env so `browser` is true and the SESSION_RESET listener registers.
vi.mock('$app/env', () => ({ browser: true, dev: false }));
// session.ts pulls in api/auth deps unrelated to this store.
vi.mock('./session', () => ({ SESSION_RESET_EVENT: 'joidy:session-reset' }));

import { notifications, showNotification, clearAllNotificationTimers } from './notifications';

describe('notifications store', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    notifications.set([]);
  });

  afterEach(() => {
    clearAllNotificationTimers();
    notifications.set([]);
    vi.useRealTimers();
  });

  it('assigns unique ids to notifications emitted in the same millisecond (#1500)', () => {
    // Fake timers pin Date.now() — the old `notif-${Date.now()}` ids collided
    // here, producing duplicate {#each} keys in Toast during WS bursts.
    for (let i = 0; i < 5; i++) showNotification(`msg-${i}`, 'info');
    const ids = get(notifications).map((n) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('caps the visible toast list at 6, keeping the newest (#1500)', () => {
    for (let i = 0; i < 10; i++) showNotification(`msg-${i}`, 'info');
    const list = get(notifications);
    expect(list).toHaveLength(6);
    expect(list.map((n) => n.message)).toEqual([
      'msg-4',
      'msg-5',
      'msg-6',
      'msg-7',
      'msg-8',
      'msg-9',
    ]);
  });

  it('still deduplicates an identical active message', () => {
    showNotification('same', 'info');
    showNotification('same', 'info');
    expect(get(notifications)).toHaveLength(1);
  });

  it('auto-dismisses after 4s', () => {
    showNotification('bye', 'info');
    vi.advanceTimersByTime(4000);
    expect(get(notifications)).toHaveLength(0);
  });
});
