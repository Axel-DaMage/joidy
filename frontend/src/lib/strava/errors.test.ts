import { describe, it, expect } from 'vitest';
import { httpStatusOf, isStravaAuthError, stravaErrorKind } from './errors';

// Mirrors the Error format thrown by api.ts `req()`.
const apiError = (status: number) =>
  new Error(`API GET /integrations/strava/activities → ${status}: {"detail":"x"}`);

describe('httpStatusOf', () => {
  it('extracts the status from api errors', () => {
    expect(httpStatusOf(apiError(401))).toBe(401);
    expect(httpStatusOf(apiError(429))).toBe(429);
    expect(httpStatusOf(apiError(502))).toBe(502);
  });

  it('returns null for non-HTTP errors', () => {
    expect(httpStatusOf(new Error('Failed to fetch'))).toBeNull();
    expect(httpStatusOf('random string')).toBeNull();
    expect(httpStatusOf(null)).toBeNull();
  });
});

describe('isStravaAuthError', () => {
  it('is true only for 401', () => {
    expect(isStravaAuthError(apiError(401))).toBe(true);
    expect(isStravaAuthError(apiError(403))).toBe(false);
    expect(isStravaAuthError(new Error('boom'))).toBe(false);
  });
});

describe('stravaErrorKind', () => {
  it('maps statuses per the backend error contract', () => {
    expect(stravaErrorKind(apiError(401))).toBe('auth');
    expect(stravaErrorKind(apiError(429))).toBe('rateLimit');
    expect(stravaErrorKind(apiError(404))).toBe('notFound');
    expect(stravaErrorKind(apiError(502))).toBe('upstream');
    expect(stravaErrorKind(apiError(503))).toBe('upstream');
    expect(stravaErrorKind(apiError(400))).toBe('generic');
    expect(stravaErrorKind(new Error('Failed to fetch'))).toBe('generic');
  });
});
