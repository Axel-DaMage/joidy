/**
 * TypeScript shapes for the Strava integration (#44).
 *
 * These mirror the payloads proxied by `api/routers/integrations/strava.py`
 * (which forwards the upstream Strava API v3 responses almost verbatim).
 * Fields are optional where Strava omits them for certain sport types
 * (e.g. `average_watts` only exists on rides, `laps` only on detail calls).
 */

// ---------------------------------------------------------------------------
// OAuth / status
// ---------------------------------------------------------------------------

export interface StravaAuthUrl {
  url: string;
}

export interface StravaAthleteSummary {
  id?: number;
  firstname?: string;
  lastname?: string;
  username?: string;
  profile?: string;
  profile_medium?: string;
  profile_large?: string;
  city?: string;
  state?: string;
  country?: string;
  sex?: string;
}

export interface StravaStatus {
  /** True when STRAVA_CLIENT_ID/SECRET/REDIRECT_URI are set server-side. */
  configured: boolean;
  connected: boolean;
  athlete: StravaAthleteSummary | null;
}

// ---------------------------------------------------------------------------
// Activities
// ---------------------------------------------------------------------------

export interface StravaMap {
  id?: number;
  summary_polyline?: string;
  polyline?: string;
  resource_state?: string;
}

export interface StravaSplit {
  distance?: number; // meters
  moving_time?: number; // seconds
  elapsed_time?: number; // seconds
  average_speed?: number; // m/s
  average_grade_adjusted_speed?: number;
  pace_zone?: number;
  elevation_difference?: number; // meters
  elevation_high?: number;
  elevation_low?: number;
  heart_rate?: number;
  split?: number;
}

export interface StravaLap extends StravaSplit {
  name?: string;
  lap_index?: number;
  total_elevation_gain?: number;
}

export interface StravaActivity {
  id: number;
  name?: string;
  /** Legacy sport type ("Run", "Ride", …). */
  type?: string;
  /** Granular sport type ("TrailRun", "VirtualRide", "EBikeRide", …). */
  sport_type?: string;
  start_date?: string; // ISO-8601 UTC
  start_date_local?: string;
  timezone?: string;
  elapsed_time?: number; // seconds
  moving_time?: number; // seconds
  distance?: number; // meters
  total_elevation_gain?: number; // meters
  elev_high?: number;
  elev_low?: number;
  average_speed?: number; // m/s
  max_speed?: number;
  calories?: number;
  kilojoules?: number;
  average_heartrate?: number;
  max_heartrate?: number;
  average_cadence?: number;
  average_watts?: number;
  max_watts?: number;
  commute?: boolean;
  trainer?: boolean;
  manual?: boolean;
  private?: boolean;
  map?: StravaMap | null;
  laps?: StravaLap[];
  /** Detail-only: splits_metric uses metric units (meters/seconds). */
  splits_metric?: StravaSplit[];
  splits_standard?: StravaSplit[];
}

// ---------------------------------------------------------------------------
// Streams (GET /activities/{id}/streams — key_by_type=true)
// ---------------------------------------------------------------------------

export interface StravaStream {
  data?: unknown;
  series_type?: string;
  original_size?: number;
  resolution?: string;
}

/** Keyed by stream type: `time`, `latlng`, `altitude`, `heartrate`, … */
export type StravaStreams = Record<string, StravaStream | undefined>;

// ---------------------------------------------------------------------------
// Athlete stats
// ---------------------------------------------------------------------------

export interface StravaSportTotals {
  count?: number;
  distance?: number; // meters
  moving_time?: number; // seconds
  elapsed_time?: number;
  elevation_gain?: number; // meters
}

export interface StravaStats {
  recent_ride_totals?: StravaSportTotals;
  recent_run_totals?: StravaSportTotals;
  recent_swim_totals?: StravaSportTotals;
  ytd_ride_totals?: StravaSportTotals;
  ytd_run_totals?: StravaSportTotals;
  ytd_swim_totals?: StravaSportTotals;
  all_ride_totals?: StravaSportTotals;
  all_run_totals?: StravaSportTotals;
  all_swim_totals?: StravaSportTotals;
  biggest_ride_distance?: number;
  biggest_climb_elevation_gain?: number;
  recent_ride_efforts_count?: number;
  recent_run_efforts_count?: number;
  recent_swim_efforts_count?: number;
  ytd_ride_efforts_count?: number;
  ytd_run_efforts_count?: number;
  ytd_swim_efforts_count?: number;
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export interface StravaRoute {
  id: number;
  name?: string;
  distance?: number; // meters
  elevation_gain?: number; // meters
  /** Strava route type: 1 = ride, 2 = run, 3 = other. */
  type?: number;
  sport_type?: string;
  sub_type?: number;
  created_at?: string;
  updated_at?: string;
  is_gps_based?: boolean;
  private?: boolean;
  athlete?: { id?: number };
  map?: StravaMap | null;
}

// ---------------------------------------------------------------------------
// Sync / gamification
// ---------------------------------------------------------------------------

export interface StravaSyncResult {
  fetched: number;
  new: number;
  /** XP awarded this run (+5/activity + weekly bonuses), dedup-safe. */
  xp_awarded: number;
  weeks: string[];
  bonus_weeks: string[];
}
