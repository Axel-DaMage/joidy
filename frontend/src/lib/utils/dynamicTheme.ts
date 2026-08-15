/**
 * Dynamic visual themes based on season and time of day (#356).
 */

import { browser } from '$app/environment';

export type TimeOfDay = 'dawn' | 'morning' | 'day' | 'afternoon' | 'dusk' | 'night';
export type Season = 'spring' | 'summer' | 'autumn' | 'winter';
export type Hemisphere = 'northern' | 'southern';

export interface ThemeTokens {
  '--bg': string;
  '--fg': string;
  '--surface': string;
  '--border': string;
  '--shadow': string;
  '--accent': string;
}

const CHECK_INTERVAL_MS = 5 * 60 * 1000;

let autoThemeTimer: ReturnType<typeof setInterval> | null = null;

export function getTimeOfDay(hour: number = new Date().getHours()): TimeOfDay {
  if (hour >= 5 && hour < 7) return 'dawn';
  if (hour >= 7 && hour < 11) return 'morning';
  if (hour >= 11 && hour < 15) return 'day';
  if (hour >= 15 && hour < 18) return 'afternoon';
  if (hour >= 18 && hour < 20) return 'dusk';
  return 'night';
}

export function detectHemisphere(): Hemisphere {
  if (!browser) return 'northern';
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const southern = [
      'Australia/', 'Pacific/Auckland', 'Pacific/Fiji', 'Pacific/Port_Moresby',
      'America/Argentina', 'America/Sao_Paulo', 'America/Buenos_Aires',
      'America/Lima', 'America/Santiago', 'America/Montevideo', 'America/Asuncion',
      'America/La_Paz', 'Africa/Johannesburg', 'Africa/Harare', 'Africa/Maputo',
      'Africa/Windhoek', 'Antarctica/',
    ];
    if (southern.some(prefix => tz.startsWith(prefix))) return 'southern';
  } catch { /* ignore */ }
  return 'northern';
}

export function getSeason(month: number = new Date().getMonth(), hemisphere: Hemisphere = detectHemisphere()): Season {
  let season: Season;
  if (month >= 2 && month <= 4) season = 'spring';
  else if (month >= 5 && month <= 7) season = 'summer';
  else if (month >= 8 && month <= 10) season = 'autumn';
  else season = 'winter';

  if (hemisphere === 'southern') {
    const reversed: Record<Season, Season> = {
      spring: 'autumn', summer: 'winter', autumn: 'spring', winter: 'summer',
    };
    season = reversed[season];
  }
  return season;
}

interface Palette { bg: string; fg: string; surface: string; border: string; shadow: string; accent: string; }

const PALETTES: Record<TimeOfDay, Record<Season, Palette>> = {
  dawn: {
    spring: { bg: '#fff5f7', fg: '#2b1a22', surface: '#ffeef2', border: '#f3d4dd', shadow: 'rgba(200,120,140,0.12)', accent: '#e89bb0' },
    summer: { bg: '#fff6f0', fg: '#2e1d16', surface: '#ffeee4', border: '#f4d8c6', shadow: 'rgba(220,140,90,0.12)', accent: '#f0a878' },
    autumn: { bg: '#fff4ee', fg: '#2c1c14', surface: '#ffede2', border: '#f2d2bc', shadow: 'rgba(190,120,70,0.12)', accent: '#d98a5b' },
    winter: { bg: '#f6f8ff', fg: '#1a2233', surface: '#eef2fc', border: '#d4dcf0', shadow: 'rgba(90,120,200,0.12)', accent: '#9bb8e8' },
  },
  morning: {
    spring: { bg: '#f7fff5', fg: '#1a2b1f', surface: '#effff0', border: '#d4f0d8', shadow: 'rgba(80,180,100,0.10)', accent: '#7fc98a' },
    summer: { bg: '#fffef0', fg: '#2b2a16', surface: '#fffae0', border: '#f0e8b8', shadow: 'rgba(220,200,80,0.10)', accent: '#e8d878' },
    autumn: { bg: '#fff8f0', fg: '#2c2014', surface: '#fff2e4', border: '#f2dcc0', shadow: 'rgba(200,150,80,0.10)', accent: '#d8a868' },
    winter: { bg: '#f4f8ff', fg: '#182033', surface: '#ecf2fc', border: '#d0dcf0', shadow: 'rgba(80,110,200,0.10)', accent: '#8aa8e0' },
  },
  day: {
    spring: { bg: '#f4fff4', fg: '#162a1c', surface: '#eafff0', border: '#cde8d2', shadow: 'rgba(60,170,90,0.10)', accent: '#6ec078' },
    summer: { bg: '#fffff2', fg: '#2a2a14', surface: '#fffde2', border: '#ece8a8', shadow: 'rgba(210,190,70,0.10)', accent: '#e0c860' },
    autumn: { bg: '#fffaf2', fg: '#2a1f12', surface: '#fff4e6', border: '#f0d8bc', shadow: 'rgba(190,140,70,0.10)', accent: '#cfa060' },
    winter: { bg: '#f2f6ff', fg: '#141c30', surface: '#eaf0fa', border: '#ccd8ee', shadow: 'rgba(70,100,190,0.10)', accent: '#7ca0d8' },
  },
  afternoon: {
    spring: { bg: '#f6fff2', fg: '#1c2b18', surface: '#efffe8', border: '#d4eccc', shadow: 'rgba(90,170,60,0.10)', accent: '#8cc070' },
    summer: { bg: '#fffef0', fg: '#2c2812', surface: '#fffce0', border: '#f0e6a0', shadow: 'rgba(210,180,60,0.10)', accent: '#e8c860' },
    autumn: { bg: '#fff7ee', fg: '#2c1f10', surface: '#fff2e0', border: '#f0d4b4', shadow: 'rgba(180,130,60,0.10)', accent: '#d09858' },
    winter: { bg: '#f0f5ff', fg: '#101a30', surface: '#e8f0f8', border: '#c8d4ec', shadow: 'rgba(60,90,180,0.10)', accent: '#7098d0' },
  },
  dusk: {
    spring: { bg: '#2a2230', fg: '#f0e8f2', surface: '#332a3a', border: '#4a3d54', shadow: 'rgba(180,120,200,0.20)', accent: '#c890d8' },
    summer: { bg: '#2e2418', fg: '#f4ecd8', surface: '#382c1e', border: '#50402a', shadow: 'rgba(220,160,80,0.20)', accent: '#e8b870' },
    autumn: { bg: '#2c1f14', fg: '#f2e4d0', surface: '#382818', border: '#4e3a26', shadow: 'rgba(200,130,60,0.20)', accent: '#d8985a' },
    winter: { bg: '#1c2030', fg: '#e8eef8', surface: '#242a3a', border: '#3a4258', shadow: 'rgba(100,130,210,0.20)', accent: '#8aa8e0' },
  },
  night: {
    spring: { bg: '#161a24', fg: '#e8eef0', surface: '#1c2230', border: '#2a3242', shadow: 'rgba(80,180,120,0.16)', accent: '#5fa878' },
    summer: { bg: '#181a22', fg: '#f0eeea', surface: '#1e2230', border: '#2c3040', shadow: 'rgba(120,110,200,0.16)', accent: '#7a78c8' },
    autumn: { bg: '#1a1612', fg: '#f0e8df', surface: '#221e18', border: '#302a22', shadow: 'rgba(180,120,60,0.16)', accent: '#c08850' },
    winter: { bg: '#121622', fg: '#e8eef8', surface: '#181e2c', border: '#262e42', shadow: 'rgba(90,120,210,0.16)', accent: '#6a8cd8' },
  },
};

export function getThemeTokens(timeOfDay: TimeOfDay, season: Season): ThemeTokens {
  const p = PALETTES[timeOfDay][season];
  return {
    '--bg': p.bg, '--fg': p.fg, '--surface': p.surface,
    '--border': p.border, '--shadow': p.shadow, '--accent': p.accent,
  };
}

export function applyDynamicTheme(tokens: ThemeTokens): void {
  if (!browser) return;
  const root = document.documentElement;
  root.style.setProperty('--bg', tokens['--bg']);
  root.style.setProperty('--surface', tokens['--surface']);
  root.style.setProperty('--border', tokens['--border']);
  root.style.setProperty('--shadow', tokens['--shadow']);
  root.style.setProperty('--text-primary', tokens['--fg']);
  // Preserve custom accent colors set by the user via settings.
  // Only set dynamic theme accent if the user hasn't customized it.
  const accentVars = ['--accent', '--xp', '--xp-2', '--xp-3', '--xp-dark',
    '--plant', '--plant-secondary', '--plant-tertiary', '--plant-glow'];
  const hasCustomAccent = root.style.getPropertyValue('--accent').trim().length > 0;
  if (!hasCustomAccent) {
    root.style.setProperty('--accent', tokens['--accent']);
  }
  // Ensure custom accent vars are never overwritten by the dynamic theme.
  // If they exist as inline styles (set by applyColors), they are preserved.
  // If they don't exist, they fall through to :root defaults which is fine.
}

export function clearDynamicTheme(): void {
  if (!browser) return;
  const root = document.documentElement;
  root.style.removeProperty('--bg');
  root.style.removeProperty('--surface');
  root.style.removeProperty('--border');
  root.style.removeProperty('--shadow');
  root.style.removeProperty('--text-primary');
}

function updateNow(): void {
  const tokens = getThemeTokens(getTimeOfDay(), getSeason());
  applyDynamicTheme(tokens);
}

export function startAutoTheme(): void {
  if (!browser) return;
  stopAutoTheme();
  updateNow();
  autoThemeTimer = setInterval(updateNow, CHECK_INTERVAL_MS);
}

export function stopAutoTheme(): void {
  if (autoThemeTimer !== null) {
    clearInterval(autoThemeTimer);
    autoThemeTimer = null;
  }
}
