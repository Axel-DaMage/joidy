/**
 * Pure helpers for Strava activity streams and route polylines (#44).
 *
 * The detail view renders two SVG visualizations without a chart library:
 *  - a route trace built from the `latlng` stream (or a route's
 *    `summary_polyline`), normalized into a viewBox;
 *  - an elevation profile built from the `altitude` stream.
 *
 * Everything here is deterministic and unit-tested — no DOM, no stores.
 */

import type { StravaStreams } from './types';

// ---------------------------------------------------------------------------
// Stream extraction (defensive — Strava may omit keys or send null data)
// ---------------------------------------------------------------------------

/** Extract a numeric series (altitude, heartrate, watts, …) or []. */
export function getNumberSeries(streams: StravaStreams | null | undefined, key: string): number[] {
  const stream = streams?.[key];
  const data = stream?.data;
  if (!Array.isArray(data)) return [];
  const out: number[] = [];
  for (const v of data) {
    out.push(typeof v === 'number' && Number.isFinite(v) ? v : NaN);
  }
  return out;
}

/** Extract the `time` series (seconds offsets) or []. */
export function getTimeSeries(streams: StravaStreams | null | undefined): number[] {
  return getNumberSeries(streams, 'time');
}

/** Extract the `latlng` series ([[lat, lng], …]) or []. */
export function getLatLngSeries(streams: StravaStreams | null | undefined): [number, number][] {
  const stream = streams?.latlng;
  const data = stream?.data;
  if (!Array.isArray(data)) return [];
  const out: [number, number][] = [];
  for (const pair of data) {
    if (
      Array.isArray(pair) &&
      pair.length >= 2 &&
      typeof pair[0] === 'number' &&
      typeof pair[1] === 'number' &&
      Number.isFinite(pair[0]) &&
      Number.isFinite(pair[1])
    ) {
      out.push([pair[0], pair[1]]);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Polyline decoding (Google/Strava encoded polyline algorithm)
// ---------------------------------------------------------------------------

/**
 * Decode an encoded polyline string into `[lat, lng]` pairs.
 * Algorithm: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
 */
export function decodePolyline(encoded: string): [number, number][] {
  const points: [number, number][] = [];
  if (!encoded) return points;

  let index = 0;
  let lat = 0;
  let lng = 0;

  const readChunk = (): number => {
    let result = 0;
    let shift = 0;
    let byte: number;
    do {
      if (index >= encoded.length) return -1;
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20 && index <= encoded.length);
    return result & 1 ? ~(result >> 1) : result >> 1;
  };

  while (index < encoded.length) {
    const dLat = readChunk();
    const dLng = readChunk();
    if (dLat === -1 || dLng === -1) break;
    lat += dLat;
    lng += dLng;
    points.push([lat / 1e5, lng / 1e5]);
  }
  return points;
}

// ---------------------------------------------------------------------------
// SVG geometry
// ---------------------------------------------------------------------------

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/**
 * Build an SVG path `d` for a lat/lng trace fitted into `width`×`height`
 * with `padding`. Points are `[lat, lng]` pairs; longitude drives the
 * horizontal axis (scaled by cos(midLat) so the trace isn't horizontally
 * stretched at high latitudes) and latitude the vertical one (north up).
 * Returns '' for <2 points.
 */
export function buildRoutePath(
  points: [number, number][],
  width: number,
  height: number,
  padding = 8
): string {
  if (points.length < 2 || width <= 0 || height <= 0) return '';

  let latMin = Infinity;
  let latMax = -Infinity;
  let lngMin = Infinity;
  let lngMax = -Infinity;
  for (const [lat, lng] of points) {
    if (lat < latMin) latMin = lat;
    if (lat > latMax) latMax = lat;
    if (lng < lngMin) lngMin = lng;
    if (lng > lngMax) lngMax = lng;
  }

  const midLat = ((latMin + latMax) / 2) * (Math.PI / 180);
  const cosLat = Math.max(Math.cos(midLat), 0.01);

  // Horizontal span in "longitude degrees × cos(lat)" units; vertical span
  // in latitude degrees. Both get mapped into the padded viewBox.
  const lngSpan = Math.max((lngMax - lngMin) * cosLat, 1e-9);
  const latSpan = Math.max(latMax - latMin, 1e-9);
  const scale = Math.min((width - padding * 2) / lngSpan, (height - padding * 2) / latSpan);
  const offX = (width - lngSpan * scale) / 2;
  const offY = (height - latSpan * scale) / 2;

  const cmds: string[] = [];
  for (let i = 0; i < points.length; i++) {
    const [lat, lng] = points[i];
    const x = offX + (lng - lngMin) * cosLat * scale;
    const y = height - (offY + (lat - latMin) * scale);
    cmds.push(`${i === 0 ? 'M' : 'L'}${round1(x)} ${round1(y)}`);
  }
  return cmds.join(' ');
}

export interface ElevationGeometry {
  /** SVG path for the elevation line. */
  line: string;
  /** SVG path for the filled area under the line (closes at baseline). */
  area: string;
  min: number;
  max: number;
}

/**
 * Build SVG geometry for an elevation profile. `values` are altitude samples
 * (one per `time` tick); missing/NaN samples break the line into segments —
 * implemented as a single path with M jumps so gaps render as breaks.
 */
export function buildElevationGeometry(
  values: number[],
  width: number,
  height: number,
  padding = 4
): ElevationGeometry {
  const empty: ElevationGeometry = { line: '', area: '', min: 0, max: 0 };
  if (values.length < 2 || width <= 0 || height <= 0) return empty;

  let min = Infinity;
  let max = -Infinity;
  let count = 0;
  for (const v of values) {
    if (typeof v === 'number' && Number.isFinite(v)) {
      if (v < min) min = v;
      if (v > max) max = v;
      count++;
    }
  }
  if (count < 2) return empty;
  if (min === max) {
    // Flat profile — nudge so the line sits mid-chart instead of dividing by 0.
    min -= 1;
    max += 1;
  }

  const span = max - min;
  const stepX = (width - padding * 2) / (values.length - 1);
  const baseline = height - padding;

  const lineCmds: string[] = [];
  const areaParts: string[] = [];
  let penDown = false;
  let segStartX = 0;
  let lastX = 0;

  const closeSegment = () => {
    if (penDown) {
      areaParts.push(`L${round1(lastX)} ${baseline} L${round1(segStartX)} ${baseline} Z`);
    }
    penDown = false;
  };

  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (typeof v !== 'number' || !Number.isFinite(v)) {
      closeSegment();
      continue;
    }
    const x = round1(padding + i * stepX);
    const y = round1(baseline - ((v - min) / span) * (height - padding * 2));
    if (!penDown) {
      lineCmds.push(`M${x} ${y}`);
      areaParts.push(`M${x} ${baseline} L${x} ${y}`);
      segStartX = x;
      penDown = true;
    } else {
      lineCmds.push(`L${x} ${y}`);
      areaParts.push(`L${x} ${y}`);
    }
    lastX = x;
  }
  closeSegment();

  return {
    line: lineCmds.join(' '),
    area: areaParts.join(' '),
    min: Math.round(min),
    max: Math.round(max),
  };
}

// ---------------------------------------------------------------------------
// Derived metrics for the detail header
// ---------------------------------------------------------------------------

export interface ActivityMetrics {
  /** Average speed in km/h derived from distance/moving_time (0 when n/a). */
  avgSpeedKmh: number;
  /** Total ascent meters. */
  elevationGain: number;
  /** Whether the activity has usable GPS points for a route trace. */
  hasRoute: boolean;
}

export function deriveMetrics(
  activity: {
    distance?: number;
    moving_time?: number;
    total_elevation_gain?: number;
    map?: { summary_polyline?: string } | null;
  } | null | undefined,
  latLngPoints: [number, number][] = []
): ActivityMetrics {
  const distance = activity?.distance ?? 0;
  const moving = activity?.moving_time ?? 0;
  const avgSpeedKmh = distance > 0 && moving > 0 ? (distance / moving) * 3.6 : 0;
  const polyline = activity?.map?.summary_polyline;
  const hasRoute = latLngPoints.length >= 2 || (typeof polyline === 'string' && polyline.length > 0);
  return {
    avgSpeedKmh,
    elevationGain: activity?.total_elevation_gain ?? 0,
    hasRoute,
  };
}
