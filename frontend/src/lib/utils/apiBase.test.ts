import { describe, it, expect } from 'vitest';
import {
  API_PORT_FALLBACK_SPAN,
  API_PORT_RANGE,
  DEFAULT_API_PORT,
  augmentCspWithApiPort,
  resolveBrowserApiBase,
} from './apiBase';

const loc = { protocol: 'http:', hostname: '192.168.1.50' };

describe('resolveBrowserApiBase (#1487)', () => {
  it('prefers the runtime PUBLIC_API_PORT over the baked VITE_API_URL', () => {
    // The production image always bakes VITE_API_URL=http://localhost:8000 —
    // a port-fallback'd API (e.g. 8003) must still win.
    expect(resolveBrowserApiBase('8003', 'http://localhost:8000', loc)).toBe(
      'http://192.168.1.50:8003'
    );
  });

  it('uses the page hostname, not localhost (LAN access)', () => {
    expect(resolveBrowserApiBase('8000', undefined, loc)).toBe('http://192.168.1.50:8000');
  });

  it('keeps the page protocol', () => {
    expect(
      resolveBrowserApiBase('8001', undefined, { protocol: 'https:', hostname: 'joidy.lan' })
    ).toBe('https://joidy.lan:8001');
  });

  it('falls back to VITE_API_URL when PUBLIC_API_PORT is unset (vite dev)', () => {
    expect(resolveBrowserApiBase(undefined, 'http://localhost:8000', loc)).toBe(
      'http://localhost:8000'
    );
    expect(resolveBrowserApiBase('', 'http://localhost:8002', loc)).toBe('http://localhost:8002');
  });

  it('ignores a malformed PUBLIC_API_PORT and keeps the order', () => {
    expect(resolveBrowserApiBase('not-a-port', 'http://localhost:8000', loc)).toBe(
      'http://localhost:8000'
    );
    expect(resolveBrowserApiBase('99999', 'http://localhost:8000', loc)).toBe(
      'http://localhost:8000'
    );
  });

  it('falls back to <page-host>:8000 when nothing is configured', () => {
    expect(resolveBrowserApiBase(undefined, undefined, loc)).toBe('http://192.168.1.50:8000');
    expect(resolveBrowserApiBase(undefined, '', loc)).toBe('http://192.168.1.50:8000');
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
