<script lang="ts">
  import { onMount } from 'svelte';
  import { logger } from '$lib/utils/logger';

  interface WeatherData {
    temp: number;
    code: number;
    isDay: boolean;
    location: string;
  }

  let weather: WeatherData | null = null;
  let loading = true;
  let error = '';

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

  async function fetchWeather() {
    loading = true;
    error = '';
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          timeout: 10000,
          maximumAge: 3600000,
        });
      });

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

  .weather-error {
    opacity: 0.5;
  }

  .weather-label {
    font-size: 11px;
    color: var(--text-muted);
  }
</style>