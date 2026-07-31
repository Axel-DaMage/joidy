import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// The logger computes `currentLevel` once at module load from `$app/environment`
// (`browser`, `dev`) and `localStorage`. To test each mode we use `vi.doMock`
// (not hoisted) + `vi.resetModules()` + dynamic `import()` so the module
// re-evaluates with the new mock values.

const LEVELS = { error: 0, warn: 1, info: 2, log: 3, debug: 4 } as const;

async function loadLogger(env: { browser: boolean; dev: boolean }, logLevel?: string) {
  vi.resetModules();
  if (logLevel !== undefined) {
    localStorage.setItem('joidy-log-level', logLevel);
  } else {
    localStorage.removeItem('joidy-log-level');
  }
  vi.doMock('$app/environment', () => env);
  const mod = await import('./logger');
  return mod.logger;
}

describe('logger — log levels', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'info').mockImplementation(() => {});
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'debug').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    vi.doUnmock('$app/environment');
    vi.resetModules();
  });

  it('in dev mode all levels are active', async () => {
    const logger = await loadLogger({ browser: true, dev: true });
    logger.debug('d');
    logger.log('l');
    logger.info('i');
    logger.warn('w');
    logger.error('e');
    expect(console.debug).toHaveBeenCalled();
    expect(console.log).toHaveBeenCalled();
    expect(console.info).toHaveBeenCalled();
    expect(console.warn).toHaveBeenCalled();
    expect(console.error).toHaveBeenCalled();
  });

  it('in production (dev=false) default level is warn: error+warn active, info/log/debug noop', async () => {
    const logger = await loadLogger({ browser: true, dev: false });
    logger.debug('d');
    logger.log('l');
    logger.info('i');
    logger.warn('w');
    logger.error('e');
    expect(console.debug).not.toHaveBeenCalled();
    expect(console.log).not.toHaveBeenCalled();
    expect(console.info).not.toHaveBeenCalled();
    expect(console.warn).toHaveBeenCalledWith('w');
    expect(console.error).toHaveBeenCalledWith('e');
  });

  it('on the server (browser=false) only error is active', async () => {
    const logger = await loadLogger({ browser: false, dev: true });
    logger.error('e');
    logger.warn('w');
    logger.info('i');
    logger.log('l');
    logger.debug('d');
    expect(console.error).toHaveBeenCalledWith('e');
    expect(console.warn).not.toHaveBeenCalled();
    expect(console.info).not.toHaveBeenCalled();
    expect(console.log).not.toHaveBeenCalled();
    expect(console.debug).not.toHaveBeenCalled();
  });

  it('respects localStorage log level override (info) over dev default', async () => {
    const logger = await loadLogger({ browser: true, dev: true }, 'info');
    logger.debug('d');
    logger.log('l');
    logger.info('i');
    logger.warn('w');
    logger.error('e');
    expect(console.debug).not.toHaveBeenCalled();
    expect(console.log).not.toHaveBeenCalled();
    expect(console.info).toHaveBeenCalledWith('i');
    expect(console.warn).toHaveBeenCalledWith('w');
    expect(console.error).toHaveBeenCalledWith('e');
  });

  it('respects localStorage log level override (error) — only error active', async () => {
    const logger = await loadLogger({ browser: true, dev: true }, 'error');
    logger.error('e');
    logger.warn('w');
    logger.info('i');
    expect(console.error).toHaveBeenCalledWith('e');
    expect(console.warn).not.toHaveBeenCalled();
    expect(console.info).not.toHaveBeenCalled();
  });

  it('ignores an invalid localStorage log level and falls back to default', async () => {
    const logger = await loadLogger({ browser: true, dev: false }, 'bogus');
    logger.warn('w');
    logger.info('i');
    expect(console.warn).toHaveBeenCalledWith('w');
    expect(console.info).not.toHaveBeenCalled();
  });

  it('each method forwards multiple arguments to the matching console method', async () => {
    const logger = await loadLogger({ browser: true, dev: true });
    logger.error('msg', 1, { a: 2 });
    expect(console.error).toHaveBeenCalledWith('msg', 1, { a: 2 });
  });
});
