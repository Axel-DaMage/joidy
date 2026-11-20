import { describe, it, expect } from 'vitest';
import { aiStatusFromUsage } from './aiStatus';

describe('aiStatusFromUsage', () => {
  it('maps null/undefined usage to checking', () => {
    expect(aiStatusFromUsage(null)).toBe('checking');
    expect(aiStatusFromUsage(undefined)).toBe('checking');
  });

  it('passes through each known backend status', () => {
    for (const status of ['ok', 'degraded', 'unavailable', 'disabled'] as const) {
      expect(aiStatusFromUsage({ ai_enabled: true, ai_status: status })).toBe(status);
    }
  });

  it('lets the real status override a misleading ai_enabled flag (#1460)', () => {
    // ai_enabled is just the env flag — providers can be down while it's true.
    expect(aiStatusFromUsage({ ai_enabled: true, ai_status: 'unavailable' })).toBe('unavailable');
    expect(aiStatusFromUsage({ ai_enabled: true, ai_status: 'degraded' })).toBe('degraded');
  });

  it('falls back to ai_enabled when ai_status is absent (old backend)', () => {
    expect(aiStatusFromUsage({ ai_enabled: true })).toBe('ok');
    expect(aiStatusFromUsage({ ai_enabled: false })).toBe('disabled');
  });

  it('falls back to ai_enabled on unrecognised status values', () => {
    expect(aiStatusFromUsage({ ai_enabled: true, ai_status: 'weird' })).toBe('ok');
    expect(aiStatusFromUsage({ ai_enabled: false, ai_status: '' })).toBe('disabled');
    expect(aiStatusFromUsage({ ai_enabled: true, ai_status: null })).toBe('ok');
  });
});
