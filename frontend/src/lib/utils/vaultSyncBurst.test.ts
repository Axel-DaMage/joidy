import { describe, it, expect } from 'vitest';
import { createVaultSyncBurst } from './vaultSyncBurst';

describe('createVaultSyncBurst', () => {
  it('returns 1 for the first file of a burst and increments per file', () => {
    const burst = createVaultSyncBurst();
    expect(burst.recordFile()).toBe(1);
    expect(burst.recordFile()).toBe(2);
    expect(burst.recordFile()).toBe(3);
    expect(burst.fileCount).toBe(3);
  });

  it('accumulates XP across events', () => {
    const burst = createVaultSyncBurst();
    burst.recordXp(10);
    burst.recordXp(5);
    burst.recordXp(0);
    expect(burst.reset().xp).toBe(15);
  });

  it('reset returns the totals and zeroes the tracker', () => {
    const burst = createVaultSyncBurst();
    burst.recordFile();
    burst.recordFile();
    burst.recordXp(10);
    expect(burst.reset()).toEqual({ files: 2, xp: 10 });
    expect(burst.fileCount).toBe(0);
    expect(burst.reset()).toEqual({ files: 0, xp: 0 });
  });

  it('counts a new burst from zero after a reset', () => {
    const burst = createVaultSyncBurst();
    burst.recordFile();
    burst.recordFile();
    burst.reset();
    expect(burst.recordFile()).toBe(1);
  });
});
