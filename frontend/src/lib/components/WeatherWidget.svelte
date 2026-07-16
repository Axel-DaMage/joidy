<script lang="ts">
  import { onMount } from 'svelte';
  import { logger } from '$lib/utils/logger';

  interface WeatherData {
    temp: number;
    code: number;
    isDay: boolean;
    location: string;
  }

  interface CacheEntry<T> {
    data: T;
    timestamp: number;
  }

  let weather: WeatherData | null = null;
  let loading = true;
  let error = '';

  const LOCATION_CACHE_KEY = 'joidy-weather-location';
  const WEATHER_CACHE_KEY = 'joidy-weather-cache';
  const LOCATION_TTL = 24 * 60 * 60 * 1000;
  const WEATHER_TTL = 15 * 60 * 1000;

  const WEATHER_CODES: Record<number, string> = {
    0: '☀️',   1: '🌤',   2: '⛅',   3: '☁️',
    45: '🌫',  48: '🌫',
    51: '🌧',  53: '🌧',  55: '🌧',
    61: '🌧',  63: '🌧',  65: '🌧',
    71: '🌨',  73: '🌨',  75: '🌨',
    77: '🌨',  80: '🌧',  81: '🌧',  82: '🌧',
    85: '🌨',  86: '🌨',
    95: '⛈',  96: '⛈',  99: '⛈',
  };

  function getEmoji(code: number, isDay: boolean): string {
    const base = WEATHER_CODES[code] || '🌡';
    if (!isDay && code === 0) return '🌙';
    return base;
  }

  function getCache<T>(key: string, ttl: number): T | null {
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
    const entry: CacheEntry<T> = { data, timestamp: Date.now() };
    localStorage.setItem(key, JSON.stringify(entry));
  }

  async function getPosition(): Promise<GeolocationPosition> {
    const cached = getCache<{ lat: number; lon: number }>(LOCATION_CACHE_KEY, LOCATION_TTL);
    if (cached) {
      return {
        coords: { latitude: cached.lat, longitude: cached.lon, accuracy: 0, altitude: null, altitudeAccuracy: null, heading: null, speed: null },
        timestamp: Date.now(),
      } as GeolocationPosition;
    }

    const position = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        timeout: 10000,
        maximumAge: 3600000,
      });
    });

    setCache(LOCATION_CACHE_KEY, {
      lat: position.coords.latitude,
      lon: position.coords.longitude,
    });

    return position;
  }

  async function fetchWeather() {
    loading = true;
    error = '';

    const cached = getCache<WeatherData>(WEATHER_CACHE_KEY, WEATHER_TTL);
    if (cached) {
      weather = cached;
      loading = false;
      return;
    }

    try {
      const position = await getPosition();
      const { latitude, longitude } = position.coords;
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,is_day&timezone=auto`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Weather API error');
      const data = await res.json();

      weather = {
        temp: Math.round(data.current.temperature_2m),
        code: data.current.weather_code,
        isDay: data.current.is_day === 1,
        location: data.timezone || 'Mi ubicación',
      };

      setCache(WEATHER_CACHE_KEY, weather);
    } catch (e) {
      error = 'No disponible';
      logger.warn('[Weather] fetch failed:', e);
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchWeather();
  });
</script>

<div class="weather-widget">
  {#if loading}
    <div class="weather-loading">
      <span class="weather-icon">🌡</span>
      <span class="weather-temp">...</span>
    </div>
  {:else if error}
    <div class="weather-error">
      <span class="weather-icon">💤</span>
      <span class="weather-label">{error}</span>
    </div>
  {:else if weather}
    <div class="weather-content">
      <span class="weather-icon">{getEmoji(weather.code, weather.isDay)}</span>
      <span class="weather-temp">{weather.temp}°</span>
      <span class="weather-location">{weather.location}</span>
      <button class="weather-refresh" on:click={fetchWeather} title="Actualizar">↻</button>
    </div>
  {/if}
</div>

<style>
  .weather-widget {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 10px 0;
    border-top: 1px solid var(--border-light, var(--border));
    border-bottom: 1px solid var(--border-light, var(--border));
  }

  .weather-loading,
  .weather-content,
  .weather-error {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .weather-icon {
    font-size: 20px;
  }

  .weather-temp {
    font-size: 22px;
    font-weight: 300;
    color: var(--text-secondary);
    letter-spacing: 0.08em;
    font-family: var(--font-mono);
  }

  .weather-location {
    font-size: 10px;
    color: var(--text-muted);
  }

  .weather-refresh {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    color: var(--text-muted);
    padding: 2px;
    line-height: 1;
    transition: transform 0.2s;
  }

  .weather-refresh:hover {
    transform: rotate(45deg);
  }

  .weather-error {
    opacity: 0.5;
  }

  .weather-label {
    font-size: 11px;
    color: var(--text-muted);
  }
</style>
