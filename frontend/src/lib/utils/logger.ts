import { dev } from '$app/environment';
import { browser } from '$app/environment';

const noop = () => {};

type LogLevel = 'error' | 'warn' | 'info' | 'log' | 'debug';
const LEVELS: Record<LogLevel, number> = { error: 0, warn: 1, info: 2, log: 3, debug: 4 };

function getLogLevel(): number {
  if (!browser) return LEVELS.error;
  const saved = localStorage.getItem('joidy-log-level') as LogLevel | null;
  if (saved && saved in LEVELS) return LEVELS[saved];
  // Default: debug in dev, warn in production
  return dev ? LEVELS.debug : LEVELS.warn;
}

const currentLevel = getLogLevel();

function makeLog(level: LogLevel): (...args: unknown[]) => void {
  if (LEVELS[level] > currentLevel) return noop;
  switch (level) {
    case 'error': return console.error.bind(console);
    case 'warn':  return console.warn.bind(console);
    case 'info':  return console.info.bind(console);
    case 'log':   return console.log.bind(console);
    case 'debug': return console.debug.bind(console);
  }
}

export const logger = {
  error: makeLog('error'),
  warn: makeLog('warn'),
  info: makeLog('info'),
  log: makeLog('log'),
  debug: makeLog('debug'),
};
