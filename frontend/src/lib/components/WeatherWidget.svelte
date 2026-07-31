<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchWeather, type WeatherData } from '$lib/services/weatherService';

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

  async function loadWeather() {
    loading = true;
    error = '';
    const data = await fetchWeather();
    if (data) {
      weather = data;
    } else {
      error = 'No disponible';
    }
    loading = false;
  }

  onMount(() => {
    loadWeather();
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
      <button class="weather-refresh" onclick={loadWeather} title="Actualizar" aria-label="Actualizar">↻</button>
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
