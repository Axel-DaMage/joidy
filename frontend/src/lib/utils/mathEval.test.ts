import { describe, it, expect } from 'vitest';
import { evaluateExpression } from './mathEval';

describe('evaluateExpression — arithmetic', () => {
  it('evaluates basic operations with correct precedence', () => {
    expect(evaluateExpression('2+3')).toBe(5);
    expect(evaluateExpression('10-4')).toBe(6);
    expect(evaluateExpression('3*4')).toBe(12);
    expect(evaluateExpression('10/4')).toBe(2.5);
    expect(evaluateExpression('2+3*4')).toBe(14);
    expect(evaluateExpression('(2+3)*4')).toBe(20);
  });

  it('handles decimals and unary signs', () => {
    expect(evaluateExpression('1.5+2.25')).toBe(3.75);
    expect(evaluateExpression('-3+5')).toBe(2);
    expect(evaluateExpression('-(2+2)')).toBe(-4);
    expect(evaluateExpression('3*-2')).toBe(-6);
  });

  it('evaluates exponentiation right-associatively', () => {
    expect(evaluateExpression('2**3')).toBe(8);
    expect(evaluateExpression('2**3**2')).toBe(512); // 2**(3**2)
    expect(evaluateExpression('4**0.5')).toBe(2);
  });

  it('evaluates postfix factorials', () => {
    expect(evaluateExpression('5!')).toBe(120);
    expect(evaluateExpression('0!')).toBe(1);
    expect(evaluateExpression('(2+3)!')).toBe(120);
    expect(evaluateExpression('3!+2')).toBe(8);
  });

  it('tolerates whitespace around operators', () => {
    expect(evaluateExpression(' 2 + 3 * 4 ')).toBe(14);
    expect(evaluateExpression('Math.max( 1 , 2 )')).toBe(2);
  });
});

describe('evaluateExpression — Math namespace', () => {
  it('resolves whitelisted constants', () => {
    expect(evaluateExpression('Math.PI')).toBeCloseTo(Math.PI, 10);
    expect(evaluateExpression('Math.E')).toBeCloseTo(Math.E, 10);
    expect(evaluateExpression('Math.PI*2')).toBeCloseTo(Math.PI * 2, 10);
  });

  it('calls whitelisted functions', () => {
    expect(evaluateExpression('Math.sqrt(9)')).toBe(3);
    expect(evaluateExpression('Math.log(Math.E)')).toBeCloseTo(1, 10);
    expect(evaluateExpression('Math.sin(0)')).toBe(0);
    expect(evaluateExpression('Math.log10(100)')).toBe(2);
    expect(evaluateExpression('Math.pow(2,10)')).toBe(1024);
    expect(evaluateExpression('Math.max(2,7)')).toBe(7);
  });
});

describe('evaluateExpression — rejects non-arithmetic input', () => {
  it('throws on identifiers outside the Math whitelist', () => {
    expect(() => evaluateExpression('alert(1)')).toThrow();
    expect(() => evaluateExpression('Math.random()')).toThrow();
    expect(() => evaluateExpression('Math.constructor')).toThrow();
    expect(() => evaluateExpression('Math.')).toThrow();
  });

  it('throws on malformed expressions', () => {
    expect(() => evaluateExpression('')).toThrow();
    expect(() => evaluateExpression('2+')).toThrow();
    expect(() => evaluateExpression('(2+3')).toThrow();
    expect(() => evaluateExpression('2 3')).toThrow();
    expect(() => evaluateExpression('2.5!')).toThrow();
    expect(() => evaluateExpression('(-1)!')).toThrow();
    expect(() => evaluateExpression('Math.sqrt(9')).toThrow();
    expect(() => evaluateExpression('Math.max(1,)')).toThrow();
    expect(() => evaluateExpression('2**')).toThrow();
    expect(() => evaluateExpression('*2')).toThrow();
  });

  it('cannot execute code hidden in the expression', () => {
    // The sanitized caller already strips most chars, but the parser must
    // reject anything that survives — no path to property access or calls
    // outside the whitelist.
    expect(() => evaluateExpression('Math.sin.call(null,0)')).toThrow();
    expect(() => evaluateExpression('globalThis')).toThrow();
  });
});
