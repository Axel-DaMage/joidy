import { browser } from '$app/environment';
import { logger } from '$lib/utils/logger';

export interface WeatherData {
  temp: number;
  code: number;
  isDay: boolean;
  location: string;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

const LOCATION_CACHE_KEY = 'joidy-weather-location';
const WEATHER_CACHE_KEY = 'joidy-weather-cache';
const LOCATION_TTL = 24 * 60 * 60 * 1000;
const WEATHER_TTL = 15 * 60 * 1000;

function getCache<T>(key: string, ttl: number): T | null {
  if (!browser) return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.timestamp > ttl) {
      localStorage.removeItem(key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

function setCache<T>(key: string, data: T): void {
  if (!browser) return;
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now() };
    localStorage.setItem(key, JSON.stringify(entry));
  } catch {
    // localStorage may be full or unavailable
  }
}

async function getPosition(): Promise<{ lat: number; lon: number }> {
  const cached = getCache<{ lat: number; lon: number }>(LOCATION_CACHE_KEY, LOCATION_TTL);
  if (cached) return cached;

  const position = await new Promise<GeolocationPosition>((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      timeout: 10000,
      maximumAge: 3600000,
    });
  });

  const coords = {
    lat: position.coords.latitude,
    lon: position.coords.longitude,
  };

  setCache(LOCATION_CACHE_KEY, coords);
  return coords;
}

/**
 * Fetch weather data from Open-Meteo API.
 * Uses a 15-minute cache for weather and 24-hour cache for geolocation.
 * Returns null if weather data cannot be fetched.
 */
export async function fetchWeather(): Promise<WeatherData | null> {
  if (!browser) return null;

  const cached = getCache<WeatherData>(WEATHER_CACHE_KEY, WEATHER_TTL);
  if (cached) return cached;

  try {
    const { lat, lon } = await getPosition();
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,is_day&timezone=auto`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Weather API error: ${res.status}`);
    const data = await res.json();

    const weather: WeatherData = {
      temp: Math.round(data.current.temperature_2m),
      code: data.current.weather_code,
      isDay: data.current.is_day === 1,
      location: data.timezone || 'Mi ubicación',
    };

    setCache(WEATHER_CACHE_KEY, weather);
    return weather;
  } catch (e) {
    logger.warn('[weatherService] fetch failed:', e);
    return null;
  }
}
