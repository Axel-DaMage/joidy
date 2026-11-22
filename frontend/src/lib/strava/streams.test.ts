import { describe, it, expect } from 'vitest';
import {
  buildElevationGeometry,
  buildRoutePath,
  decodePolyline,
  deriveMetrics,
  getLatLngSeries,
  getNumberSeries,
  getTimeSeries,
} from './streams';
import type { StravaStreams } from './types';

describe('decodePolyline', () => {
  it('decodes the canonical Google example', () => {
    // Standard test vector from the polyline algorithm docs.
    const points = decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@');
    expect(points.length).toBe(3);
    expect(points[0][0]).toBeCloseTo(38.5, 4);
    expect(points[0][1]).toBeCloseTo(-120.2, 4);
    expect(points[1][0]).toBeCloseTo(40.7, 4);
    expect(points[1][1]).toBeCloseTo(-120.95, 4);
    expect(points[2][0]).toBeCloseTo(43.252, 4);
    expect(points[2][1]).toBeCloseTo(-126.453, 4);
  });

  it('returns [] for empty input', () => {
    expect(decodePolyline('')).toEqual([]);
  });
});

describe('stream extraction', () => {
  const streams: StravaStreams = {
    time: { data: [0, 1, 2, 3] },
    latlng: { data: [[40.0, -3.7], [40.1, -3.8]] },
    altitude: { data: [600, 610, null, 620] as unknown as number[] },
    heartrate: { data: [140, 145] },
  };

  it('extracts numeric series, coercing non-numbers to NaN', () => {
    const alt = getNumberSeries(streams, 'altitude');
    expect(alt).toHaveLength(4);
    expect(alt[0]).toBe(600);
    expect(Number.isNaN(alt[2])).toBe(true);
  });

  it('extracts latlng pairs and drops malformed entries', () => {
    const pts = getLatLngSeries({
      latlng: { data: [[1, 2], [3], 'bad', [4, 5]] as unknown as [number, number][] },
    });
    expect(pts).toEqual([
      [1, 2],
      [4, 5],
    ]);
  });

  it('returns [] for missing keys or non-array data', () => {
    expect(getNumberSeries(streams, 'watts')).toEqual([]);
    expect(getNumberSeries(null, 'time')).toEqual([]);
    expect(getNumberSeries({ time: { data: 'nope' as unknown as number[] } }, 'time')).toEqual([]);
    expect(getTimeSeries(streams)).toEqual([0, 1, 2, 3]);
    expect(getLatLngSeries(null)).toEqual([]);
  });
});

describe('buildRoutePath', () => {
  it('builds an SVG path normalized into the viewBox', () => {
    const points: [number, number][] = [
      [40.0, -3.7],
      [40.01, -3.71],
      [40.02, -3.72],
    ];
    const d = buildRoutePath(points, 200, 100, 8);
    expect(d.startsWith('M')).toBe(true);
    expect(d).toContain('L');
    // All coordinates must stay inside the padded viewBox.
    const coords = d.match(/-?[\d.]+/g)!.map(Number);
    for (let i = 0; i < coords.length; i += 2) {
      expect(coords[i]).toBeGreaterThanOrEqual(0);
      expect(coords[i]).toBeLessThanOrEqual(200);
      expect(coords[i + 1]).toBeGreaterThanOrEqual(0);
      expect(coords[i + 1]).toBeLessThanOrEqual(100);
    }
  });

  it('returns empty string for degenerate input', () => {
    expect(buildRoutePath([], 200, 100)).toBe('');
    expect(buildRoutePath([[1, 2]], 200, 100)).toBe('');
    expect(buildRoutePath([[1, 2], [1, 2]], 0, 100)).toBe('');
  });
});

describe('buildElevationGeometry', () => {
  it('produces line + closed area paths with min/max', () => {
    const geo = buildElevationGeometry([100, 110, 105, 120], 200, 80, 4);
    expect(geo.line.startsWith('M')).toBe(true);
    expect(geo.line).toContain('L');
    expect(geo.area).toContain('Z');
    expect(geo.min).toBe(100);
    expect(geo.max).toBe(120);
  });

  it('handles flat profiles without dividing by zero', () => {
    const geo = buildElevationGeometry([50, 50, 50], 200, 80);
    expect(geo.line).not.toBe('');
    expect(Number.isFinite(geo.min)).toBe(true);
  });

  it('skips NaN samples as gaps', () => {
    const geo = buildElevationGeometry([100, NaN, 110, 120], 200, 80);
    expect(geo.line).toContain('M');
    // Two contiguous segments → two M commands in the line path.
    expect((geo.line.match(/M/g) || []).length).toBe(2);
  });

  it('returns empty geometry for insufficient data', () => {
    expect(buildElevationGeometry([], 200, 80).line).toBe('');
    expect(buildElevationGeometry([5], 200, 80).line).toBe('');
    expect(buildElevationGeometry([NaN, NaN], 200, 80).line).toBe('');
  });
});

describe('deriveMetrics', () => {
  it('derives avg speed and route availability', () => {
    const m = deriveMetrics(
      { distance: 10000, moving_time: 3000, total_elevation_gain: 120 },
      [[1, 2], [3, 4]]
    );
    expect(m.avgSpeedKmh).toBeCloseTo(12, 5);
    expect(m.elevationGain).toBe(120);
    expect(m.hasRoute).toBe(true);
  });

  it('detects route from summary_polyline when no stream points', () => {
    const m = deriveMetrics({ map: { summary_polyline: '_p~iF~ps|U' } }, []);
    expect(m.hasRoute).toBe(true);
  });

  it('handles missing activity', () => {
    const m = deriveMetrics(null, []);
    expect(m.avgSpeedKmh).toBe(0);
    expect(m.hasRoute).toBe(false);
  });
});
