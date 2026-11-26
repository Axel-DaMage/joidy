import { describe, it, expect } from 'vitest';
import {
  API_PORT_FALLBACK_SPAN,
  API_PORT_RANGE,
  DEFAULT_API_PORT,
  augmentCspWithApiPort,
  augmentCspWithApiUrl,
  resolveBrowserApiBase,
  wsUrlForApiBase,
} from './apiBase';

const loc = { protocol: 'http:', hostname: '192.168.1.50' };

describe('resolveBrowserApiBase (#1487, #1582)', () => {
  it('prefers the runtime PUBLIC_API_PORT over the baked VITE_API_URL', () => {
    // The production image always bakes VITE_API_URL=http://localhost:8000 —
    // a port-fallback'd API (e.g. 8003) must still win.
    expect(resolveBrowserApiBase(undefined, '8003', 'http://localhost:8000', loc)).toBe(
      'http://192.168.1.50:8003'
    );
  });

  it('uses the page hostname, not localhost (LAN access)', () => {
    expect(resolveBrowserApiBase(undefined, '8000', undefined, loc)).toBe(
      'http://192.168.1.50:8000'
    );
  });

  it('keeps the page protocol', () => {
    expect(
      resolveBrowserApiBase(undefined, '8001', undefined, {
        protocol: 'https:',
        hostname: 'joidy.lan',
      })
    ).toBe('https://joidy.lan:8001');
  });

  it('falls back to VITE_API_URL when PUBLIC_API_PORT is unset (vite dev)', () => {
    expect(resolveBrowserApiBase(undefined, undefined, 'http://localhost:8000', loc)).toBe(
      'http://localhost:8000'
    );
    expect(resolveBrowserApiBase(undefined, '', 'http://localhost:8002', loc)).toBe(
      'http://localhost:8002'
    );
  });

  it('ignores a malformed PUBLIC_API_PORT and keeps the order', () => {
    expect(resolveBrowserApiBase(undefined, 'not-a-port', 'http://localhost:8000', loc)).toBe(
      'http://localhost:8000'
    );
    expect(resolveBrowserApiBase(undefined, '99999', 'http://localhost:8000', loc)).toBe(
      'http://localhost:8000'
    );
  });

  it('normalizes whitespace/zero-padded PUBLIC_API_PORT before interpolating (#1582)', () => {
    // isValidPort accepts these via Number(), but the raw string would
    // produce `http://host: 8003` — the normalized number must be used.
    expect(resolveBrowserApiBase(undefined, ' 8003 ', 'http://localhost:8000', loc)).toBe(
      'http://192.168.1.50:8003'
    );
    expect(resolveBrowserApiBase(undefined, '08003', 'http://localhost:8000', loc)).toBe(
      'http://192.168.1.50:8003'
    );
  });

  it('falls back to <page-host>:8000 when nothing is configured', () => {
    expect(resolveBrowserApiBase(undefined, undefined, undefined, loc)).toBe(
      'http://192.168.1.50:8000'
    );
    expect(resolveBrowserApiBase(undefined, undefined, '', loc)).toBe('http://192.168.1.50:8000');
  });
});

describe('PUBLIC_API_URL precedence (#1582)', () => {
  it('takes top precedence over PUBLIC_API_PORT and VITE_API_URL', () => {
    // Reverse-proxy/TLS deployments always have PUBLIC_API_PORT injected by
    // compose — the full URL must still win.
    expect(
      resolveBrowserApiBase('https://api.example.com', '8003', 'http://localhost:8000', loc)
    ).toBe('https://api.example.com');
  });

  it('keeps a reverse-proxy subpath', () => {
    expect(
      resolveBrowserApiBase('https://example.com/api', undefined, undefined, loc)
    ).toBe('https://example.com/api');
  });

  it('strips trailing slashes', () => {
    expect(
      resolveBrowserApiBase('https://example.com/api/', undefined, undefined, loc)
    ).toBe('https://example.com/api');
    expect(
      resolveBrowserApiBase('https://api.example.com/', undefined, undefined, loc)
    ).toBe('https://api.example.com');
  });

  it('accepts http URLs and explicit ports', () => {
    expect(
      resolveBrowserApiBase('http://joidy-api.internal:9000', '8003', undefined, loc)
    ).toBe('http://joidy-api.internal:9000');
  });

  it('rejects malformed or non-http(s) URLs and falls through to the port branch', () => {
    expect(
      resolveBrowserApiBase('not a url', '8003', 'http://localhost:8000', loc)
    ).toBe('http://192.168.1.50:8003');
    expect(
      resolveBrowserApiBase('ftp://example.com', '8003', 'http://localhost:8000', loc)
    ).toBe('http://192.168.1.50:8003');
    expect(
      resolveBrowserApiBase('wss://example.com', '8003', 'http://localhost:8000', loc)
    ).toBe('http://192.168.1.50:8003');
    // Relative URL — no scheme/host — must not resolve to a broken base.
    expect(
      resolveBrowserApiBase('/api', '8003', 'http://localhost:8000', loc)
    ).toBe('http://192.168.1.50:8003');
  });

  it('falls through to VITE_API_URL when the URL is invalid and no port is set', () => {
    expect(
      resolveBrowserApiBase('::not-a-url::', undefined, 'http://localhost:8000', loc)
    ).toBe('http://localhost:8000');
  });
});

describe('wsUrlForApiBase (#1582)', () => {
  it('derives ws:// from an http base', () => {
    expect(wsUrlForApiBase('http://192.168.1.50:8003')).toBe('ws://192.168.1.50:8003/ws');
  });

  it('derives wss:// from an https base', () => {
    expect(wsUrlForApiBase('https://api.example.com')).toBe('wss://api.example.com/ws');
  });

  it('preserves a reverse-proxy subpath', () => {
    expect(wsUrlForApiBase('https://example.com/api')).toBe('wss://example.com/api/ws');
    expect(wsUrlForApiBase('https://example.com/api/')).toBe('wss://example.com/api/ws');
  });
});

describe('API port fallback range', () => {
  it('covers default..default+SPAN (mirrors find_free_port in joidy.sh)', () => {
    expect(API_PORT_RANGE).toEqual([8000, 8001, 8002, 8003, 8004, 8005]);
    expect(API_PORT_RANGE[0]).toBe(DEFAULT_API_PORT);
    expect(API_PORT_RANGE.length).toBe(API_PORT_FALLBACK_SPAN + 1);
  });
});

describe('augmentCspWithApiPort (#1487)', () => {
  const csp =
    "default-src 'self'; script-src 'self' 'nonce-abc'; connect-src 'self' data: http://*:8000 ws://*:8000; img-src 'self' data: http://*:8000";

  it('adds the runtime port to connect-src (http/https/ws/wss) and img-src', () => {
    const out = augmentCspWithApiPort(csp, '9002');
    expect(out).toContain('connect-src \'self\' data: http://*:8000 ws://*:8000 http://*:9002 https://*:9002 ws://*:9002 wss://*:9002');
    expect(out).toContain("img-src 'self' data: http://*:8000 http://*:9002 https://*:9002");
  });

  it('normalizes whitespace/zero-padded ports before interpolating (#1582)', () => {
    const out = augmentCspWithApiPort(csp, ' 9002 ');
    expect(out).toContain('http://*:9002');
    expect(out).not.toContain(' 9002');
    expect(augmentCspWithApiPort(csp, '09002')).toContain('http://*:9002');
    expect(augmentCspWithApiPort(csp, '09002')).not.toContain('09002');
  });

  it('leaves other directives — including the script nonce — untouched', () => {
    const out = augmentCspWithApiPort(csp, '9002');
    expect(out).toContain("script-src 'self' 'nonce-abc'");
    expect(out).toContain("default-src 'self'");
  });

  it('does not duplicate sources already in the static range', () => {
    const out = augmentCspWithApiPort(csp, '8000');
    expect(out.match(/http:\/\/\*:8000/g)?.length).toBe(2); // one in connect-src, one in img-src
  });

  it('returns the policy unchanged for missing/invalid ports', () => {
    expect(augmentCspWithApiPort(csp, undefined)).toBe(csp);
    expect(augmentCspWithApiPort(csp, '')).toBe(csp);
    expect(augmentCspWithApiPort(csp, 'abc')).toBe(csp);
    expect(augmentCspWithApiPort(csp, '99999')).toBe(csp);
  });
});

describe('augmentCspWithApiUrl (#1582)', () => {
  const csp =
    "default-src 'self'; script-src 'self' 'nonce-abc'; connect-src 'self' data: http://*:8000 ws://*:8000; img-src 'self' data: http://*:8000";

  it('adds the origin (not the subpath) to connect-src and img-src', () => {
    const out = augmentCspWithApiUrl(csp, 'https://example.com/api');
    expect(out).toContain('connect-src \'self\' data: http://*:8000 ws://*:8000 https://example.com wss://example.com');
    expect(out).toContain("img-src 'self' data: http://*:8000 https://example.com");
    // CSP host-sources cannot carry a path — only the origin is added.
    expect(out).not.toContain('example.com/api');
  });

  it('maps http origins to ws:// for the live-updates socket', () => {
    const out = augmentCspWithApiUrl(csp, 'http://api.internal:9000');
    expect(out).toContain('http://api.internal:9000 ws://api.internal:9000');
  });

  it('leaves other directives — including the script nonce — untouched', () => {
    const out = augmentCspWithApiUrl(csp, 'https://api.example.com');
    expect(out).toContain("script-src 'self' 'nonce-abc'");
    expect(out).toContain("default-src 'self'");
  });

  it('does not duplicate an origin already present', () => {
    const withOrigin = csp.replace(
      "img-src 'self' data: http://*:8000",
      "img-src 'self' data: http://*:8000 https://api.example.com"
    );
    const out = augmentCspWithApiUrl(withOrigin, 'https://api.example.com');
    // One in connect-src (new) + one in img-src (pre-existing, not duplicated).
    expect(out.match(/https:\/\/api\.example\.com/g)?.length).toBe(2);
  });

  it('returns the policy unchanged for missing/invalid URLs', () => {
    expect(augmentCspWithApiUrl(csp, undefined)).toBe(csp);
    expect(augmentCspWithApiUrl(csp, '')).toBe(csp);
    expect(augmentCspWithApiUrl(csp, 'not a url')).toBe(csp);
    expect(augmentCspWithApiUrl(csp, 'ftp://example.com')).toBe(csp);
  });
});
