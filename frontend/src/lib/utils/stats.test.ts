import { describe, it, expect } from 'vitest';
import { movingAverage, linearRegression } from './stats';

describe('movingAverage', () => {
  it('returns [] for empty input', () => {
    expect(movingAverage([], 7)).toEqual([]);
  });

  it('returns [] for window < 1', () => {
    expect(movingAverage([1, 2, 3], 0)).toEqual([]);
    expect(movingAverage([1, 2, 3], -2)).toEqual([]);
  });

  it('window of 1 returns the input unchanged', () => {
    expect(movingAverage([3, 1, 4, 1, 5], 1)).toEqual([3, 1, 4, 1, 5]);
  });

  it('uses a partial window for leading points', () => {
    // window 3: [10], [(10+20)/2], [(10+20+30)/3], [(20+30+40)/3], [(30+40+50)/3]
    expect(movingAverage([10, 20, 30, 40, 50], 3)).toEqual([10, 15, 20, 30, 40]);
  });

  it('computes a standard 7-day average', () => {
    // first 7 points are constant 7; the 8th averages the last 7 values
    const values = [7, 7, 7, 7, 7, 7, 7, 14];
    expect(movingAverage(values, 7)).toEqual([7, 7, 7, 7, 7, 7, 7, 8]);
  });

  it('window larger than the series averages everything seen so far', () => {
    expect(movingAverage([2, 4, 6], 10)).toEqual([2, 3, 4]);
  });

  it('handles float windows by flooring', () => {
    expect(movingAverage([1, 3], 1.9)).toEqual([1, 3]);
  });
});

describe('linearRegression', () => {
  it('returns null for fewer than 2 points', () => {
    expect(linearRegression([])).toBeNull();
    expect(linearRegression([42])).toBeNull();
  });

  it('fits a perfect positive slope', () => {
    // y = 2x + 1 over x = 0..4 → [1,3,5,7,9]
    const reg = linearRegression([1, 3, 5, 7, 9]);
    expect(reg).not.toBeNull();
    expect(reg!.slope).toBeCloseTo(2, 10);
    expect(reg!.intercept).toBeCloseTo(1, 10);
    expect(reg!.predict(10)).toBeCloseTo(21, 10);
  });

  it('fits a perfect negative slope', () => {
    // y = -3x + 12 → [12, 9, 6, 3]
    const reg = linearRegression([12, 9, 6, 3]);
    expect(reg!.slope).toBeCloseTo(-3, 10);
    expect(reg!.intercept).toBeCloseTo(12, 10);
  });

  it('fits a constant series (slope 0)', () => {
    const reg = linearRegression([5, 5, 5, 5]);
    expect(reg!.slope).toBeCloseTo(0, 10);
    expect(reg!.intercept).toBeCloseTo(5, 10);
  });

  it('fits two points exactly', () => {
    const reg = linearRegression([0, 10]);
    expect(reg!.slope).toBeCloseTo(10, 10);
    expect(reg!.intercept).toBeCloseTo(0, 10);
  });

  it('fits noisy data close to the known line', () => {
    // y ≈ x + noise
    const reg = linearRegression([0.5, 1.5, 1.8, 3.2, 4.0, 4.6]);
    expect(reg!.slope).toBeGreaterThan(0.7);
    expect(reg!.slope).toBeLessThan(1.1);
  });
});
