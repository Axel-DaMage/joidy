import { describe, it, expect } from 'vitest';
import { clockSegments, segmentText } from './segments';

function parts(h: number, m = 25, s = 0) {
  return {
    hours: String(h).padStart(2, '0'),
    minutes: String(m).padStart(2, '0'),
    seconds: String(s).padStart(2, '0'),
    h,
  };
}

describe('clockSegments', () => {
  it('wall clock always renders the full HH:MM:SS skeleton', () => {
    const l = clockSegments(parts(14, 5, 9), 'clock');
    expect(l.groups).toEqual(['14', '05', '09']);
    expect(l.ghostLead).toBe(0);
  });

  it('wall clock keeps the full skeleton even at h = 0', () => {
    const l = clockSegments(parts(0), 'clock');
    expect(l.ghostLead).toBe(0);
  });

  it('timer with hours renders all groups visible', () => {
    const l = clockSegments(parts(2), 'timer');
    expect(l.groups).toEqual(['02', '25', '00']);
    expect(l.ghostLead).toBe(0);
  });

  it('sub-hour timer ghosts only the leading hours group', () => {
    const l = clockSegments(parts(0), 'timer');
    expect(l.groups).toEqual(['00', '25', '00']);
    expect(l.ghostLead).toBe(1);
  });

  it('keeps the group count constant across the h = 0 ↔ h > 0 crossing', () => {
    const before = clockSegments(parts(0), 'timer');
    const after = clockSegments(parts(1), 'timer');
    expect(before.groups).toHaveLength(after.groups.length);
  });
});

describe('segmentText', () => {
  it('ghosts "HH:" and keeps MM:SS visible for sub-hour timers', () => {
    const t = segmentText(clockSegments(parts(0), 'timer'));
    expect(t.ghost).toBe('00:');
    expect(t.body).toBe('25:00');
  });

  it('renders the full readout once hours appear', () => {
    const t = segmentText(clockSegments(parts(2, 5, 9), 'timer'));
    expect(t.ghost).toBe('');
    expect(t.body).toBe('02:05:09');
  });

  it('wall clock text is the full HH:MM:SS readout', () => {
    const t = segmentText(clockSegments(parts(14, 5, 9), 'clock'));
    expect(t.ghost).toBe('');
    expect(t.body).toBe('14:05:09');
  });
});
