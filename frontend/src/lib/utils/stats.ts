/**
 * Statistics helpers for the analytics dashboard charts (#1499).
 * Pure functions — kept here so they are unit-testable without a DOM.
 */

/**
 * Sliding-window moving average. The output has the same length as the
 * input: leading points average the partial window seen so far.
 * Returns [] for empty input or window < 1.
 */
export function movingAverage(values: number[], window = 7): number[] {
  const w = Math.floor(window);
  if (w < 1 || values.length === 0) return [];
  const out: number[] = new Array(values.length);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= w) sum -= values[i - w];
    out[i] = sum / Math.min(i + 1, w);
  }
  return out;
}

export interface LinearRegressionResult {
  slope: number;
  intercept: number;
  /** Predicted y for a given x (index). */
  predict: (x: number) => number;
}

/**
 * Ordinary least-squares regression over `values`, treating each value as
 * y[i] at x = i. Returns null when fewer than 2 points are given (a slope
 * is undefined there) — callers must handle the null case.
 */
export function linearRegression(values: number[]): LinearRegressionResult | null {
  const n = values.length;
  if (n < 2) return null;
  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumXX = 0;
  for (let i = 0; i < n; i++) {
    sumX += i;
    sumY += values[i];
    sumXY += i * values[i];
    sumXX += i * i;
  }
  const denom = n * sumXX - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept, predict: (x: number) => slope * x + intercept };
}
