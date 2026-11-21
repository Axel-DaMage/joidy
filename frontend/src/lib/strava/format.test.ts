import { describe, it, expect } from 'vitest';
import {
  formatDistance,
  formatDuration,
  formatDurationLong,
  formatElevation,
  formatPace,
  formatSpeed,
  isoWeekKey,
  mergeSportTotals,
  monthKey,
  sportCategory,
  sportCategoryKey,
  sportIconName,
  summarizeActivities,
} from './format';
import type { StravaActivity } from './types';

describe('formatDistance', () => {
  it('renders meters under 1 km', () => {
    expect(formatDistance(850, 'en')).toBe('850 m');
    expect(formatDistance(0, 'en')).toBe('0 m');
  });

  it('renders km at 1 km and above with trimmed decimals', () => {
    expect(formatDistance(1000, 'en')).toBe('1 km');
    // < 10 km keeps two decimals; ≥ 10 km drops to one.
    expect(formatDistance(9234, 'en')).toBe('9.23 km');
    expect(formatDistance(12340, 'en')).toBe('12.3 km');
    expect(formatDistance(21500, 'en')).toBe('21.5 km');
  });

  it('respects the locale grouping separator', () => {
    // es uses "." for thousands and "," for decimals.
    expect(formatDistance(850, 'es')).toBe('850 m');
    expect(formatDistance(1234, 'es')).toBe('1,23 km');
  });

  it('renders miles in imperial mode', () => {
    expect(formatDistance(1609.344, 'en', { unit: 'imperial' })).toBe('1 mi');
    expect(formatDistance(100, 'en', { unit: 'imperial' })).toContain('ft');
  });

  it('returns a dash for missing values', () => {
    expect(formatDistance(null, 'es')).toBe('—');
    expect(formatDistance(undefined, 'es')).toBe('—');
    expect(formatDistance(NaN, 'es')).toBe('—');
  });
});

describe('formatDuration / formatDurationLong', () => {
  it('formats clock-style durations', () => {
    expect(formatDuration(45 * 60 + 12)).toBe('45:12');
    expect(formatDuration(3600 + 120 + 5)).toBe('1:02:05');
    expect(formatDuration(59)).toBe('0:59');
  });

  it('formats long durations for aggregates', () => {
    expect(formatDurationLong(2 * 3600 + 15 * 60)).toBe('2 h 15 min');
    expect(formatDurationLong(45 * 60)).toBe('45 min');
    expect(formatDurationLong(30)).toBe('30 s');
  });

  it('returns a dash for invalid input', () => {
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(-5)).toBe('—');
  });
});

describe('formatPace', () => {
  it('computes min/km pace', () => {
    // 10 km in 50 min → 5:00 /km
    expect(formatPace(3000, 10000)).toBe('5:00 /km');
    // 5 km in 27.5 min → 5:30 /km
    expect(formatPace(1650, 5000)).toBe('5:30 /km');
  });

  it('computes min/mi pace in imperial mode', () => {
    const pace = formatPace(3600, 10000, { unit: 'imperial' });
    expect(pace).toMatch(/^\d+:\d{2} \/mi$/);
  });

  it('returns null for unusable input', () => {
    expect(formatPace(3000, 0)).toBeNull();
    expect(formatPace(0, 10000)).toBeNull();
    expect(formatPace(null, 10000)).toBeNull();
    expect(formatPace(3000, null)).toBeNull();
  });
});

describe('formatElevation / formatSpeed', () => {
  it('formats elevation gain', () => {
    expect(formatElevation(1234, 'en')).toBe('1,234 m');
    expect(formatElevation(320, 'es')).toBe('320 m');
  });

  it('formats speed', () => {
    expect(formatSpeed(2.5, 'en')).toBe('9 km/h');
    expect(formatSpeed(10, 'en', { unit: 'imperial' })).toBe('22.4 mph');
    expect(formatSpeed(null, 'en')).toBe('—');
  });
});

describe('sportCategory', () => {
  it.each([
    ['Run', undefined, 'run'],
    ['TrailRun', undefined, 'run'],
    ['VirtualRun', undefined, 'run'],
    ['Ride', undefined, 'ride'],
    ['MountainBikeRide', undefined, 'ride'],
    ['EBikeRide', undefined, 'ride'],
    ['Swim', undefined, 'swim'],
    ['OpenWaterSwim', undefined, 'swim'],
    ['Hike', undefined, 'hike'],
    ['Walk', undefined, 'hike'],
    ['RockClimbing', undefined, 'hike'],
    ['AlpineSki', undefined, 'winter'],
    ['Snowboard', undefined, 'winter'],
    ['NordicSki', undefined, 'winter'],
    ['Rowing', undefined, 'water'],
    ['Kayaking', undefined, 'water'],
    ['StandUpPaddling', undefined, 'water'],
    ['Windsurf', undefined, 'water'],
    ['WeightTraining', undefined, 'strength'],
    ['Yoga', undefined, 'strength'],
    ['Workout', undefined, 'strength'],
    ['Golf', undefined, 'other'],
    ['Soccer', undefined, 'other'],
  ])('maps %s → %s', (sportType, legacy, expected) => {
    expect(sportCategory(sportType, legacy)).toBe(expected);
  });

  it('falls back to legacy type when sport_type is absent', () => {
    expect(sportCategory(undefined, 'Ride')).toBe('ride');
  });

  it('returns other for empty input', () => {
    expect(sportCategory(undefined, undefined)).toBe('other');
    expect(sportCategory('', '')).toBe('other');
  });
});

describe('sportIconName / sportCategoryKey', () => {
  it('maps categories to curated lucide icons', () => {
    expect(sportIconName('run')).toBe('Footprints');
    expect(sportIconName('ride')).toBe('Bike');
    expect(sportIconName('swim')).toBe('Waves');
    expect(sportIconName('hike')).toBe('Mountain');
    expect(sportIconName('winter')).toBe('Snowflake');
    expect(sportIconName('water')).toBe('Sailboat');
    expect(sportIconName('strength')).toBe('Dumbbell');
    expect(sportIconName('other')).toBe('Activity');
  });

  it('builds i18n key suffixes', () => {
    expect(sportCategoryKey('run')).toBe('sports.run');
    expect(sportCategoryKey('other')).toBe('sports.other');
  });
});

function makeActivity(overrides: Partial<StravaActivity> = {}): StravaActivity {
  return {
    id: 1,
    name: 'Test',
    sport_type: 'Run',
    start_date: '2026-03-10T10:00:00Z',
    moving_time: 1800,
    distance: 5000,
    total_elevation_gain: 50,
    calories: 400,
    ...overrides,
  };
}

describe('isoWeekKey / monthKey', () => {
  it('computes ISO week keys', () => {
    // 2026-03-10 is a Tuesday of ISO week 11.
    expect(isoWeekKey('2026-03-10T10:00:00Z')).toBe('2026-W11');
    // Year boundary: 2021-01-01 belongs to ISO week 53 of 2020.
    expect(isoWeekKey('2021-01-01T00:00:00Z')).toBe('2020-W53');
  });

  it('computes month keys', () => {
    expect(monthKey('2026-03-10T10:00:00Z')).toBe('2026-03');
    expect(monthKey('2026-12-31T23:00:00Z')).toBe('2026-12');
  });

  it('returns null for invalid input', () => {
    expect(isoWeekKey(null)).toBeNull();
    expect(isoWeekKey('not-a-date')).toBeNull();
    expect(monthKey(undefined)).toBeNull();
  });
});

describe('summarizeActivities', () => {
  it('aggregates totals per ISO week and month', () => {
    const activities = [
      makeActivity({ id: 1, distance: 5000, moving_time: 1800, calories: 400, total_elevation_gain: 50 }),
      makeActivity({ id: 2, distance: 3000, moving_time: 1200, calories: 250, total_elevation_gain: 20 }),
      makeActivity({ id: 3, distance: 10000, moving_time: 3600, calories: 800, total_elevation_gain: 100 }),
    ];
    const summary = summarizeActivities(activities);

    const week = summary.byWeek.find((w) => w.key === '2026-W11');
    expect(week).toBeDefined();
    expect(week!.totals.count).toBe(3);
    expect(week!.totals.distance).toBe(18000);
    expect(week!.totals.movingTime).toBe(6600);
    expect(week!.totals.calories).toBe(1450);
    expect(week!.totals.elevationGain).toBe(170);

    const month = summary.byMonth.find((m) => m.key === '2026-03');
    expect(month!.totals.count).toBe(3);
    expect(month!.totals.distance).toBe(18000);
  });

  it('sorts weeks and months newest first', () => {
    const activities = [
      makeActivity({ id: 1, start_date: '2026-01-05T10:00:00Z' }), // W02
      makeActivity({ id: 2, start_date: '2026-03-10T10:00:00Z' }), // W11
      makeActivity({ id: 3, start_date: '2026-02-10T10:00:00Z' }), // W07
    ];
    const summary = summarizeActivities(activities);
    expect(summary.byWeek.map((w) => w.key)).toEqual(['2026-W11', '2026-W07', '2026-W02']);
    expect(summary.byMonth.map((m) => m.key)).toEqual(['2026-03', '2026-02', '2026-01']);
  });

  it('handles empty input', () => {
    const summary = summarizeActivities([]);
    expect(summary.thisWeek.count).toBe(0);
    expect(summary.byWeek).toEqual([]);
    expect(summary.byMonth).toEqual([]);
  });
});

describe('mergeSportTotals', () => {
  it('sums ride+run+swim buckets', () => {
    const merged = mergeSportTotals(
      { count: 2, distance: 10000, moving_time: 3600, elevation_gain: 80 },
      { count: 3, distance: 21000, moving_time: 5400, elevation_gain: 40 },
      undefined
    );
    expect(merged.count).toBe(5);
    expect(merged.distance).toBe(31000);
    expect(merged.moving_time).toBe(9000);
    expect(merged.elevation_gain).toBe(120);
  });

  it('handles all-undefined input', () => {
    const merged = mergeSportTotals(undefined, undefined, undefined);
    expect(merged.count).toBe(0);
    expect(merged.distance).toBe(0);
  });
});
