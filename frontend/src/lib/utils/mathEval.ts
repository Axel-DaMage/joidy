/**
 * Safe arithmetic evaluator for the scientific calculator.
 *
 * Replaces the previous `new Function('return ' + expr)()` sink (audit F-10)
 * so the frontend CSP can ship `script-src 'self'` without 'unsafe-eval'
 * (#1283). The input is already pre-sanitized by the caller to arithmetic
 * characters, `Math.<name>` references and `!` postfix factorials; this
 * parser evaluates that grammar recursively — nothing else can execute.
 *
 * Grammar (recursive descent):
 *   expr    := term (('+' | '-') term)*
 *   term    := power (('*' | '/') power)*
 *   power   := unary ('**' power)?            // right-associative
 *   unary   := ('+' | '-')* postfix
 *   postfix := primary '!'*
 *   primary := number
 *            | 'Math.' ident
 *            | 'Math.' ident '(' expr (',' expr)* ')'
 *            | '(' expr ')'
 */

const MATH_FUNCTIONS: Record<string, typeof Math.min> = {
  abs: Math.abs,
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  asin: Math.asin,
  acos: Math.acos,
  atan: Math.atan,
  exp: Math.exp,
  log: Math.log,
  log2: Math.log2,
  log10: Math.log10,
  sqrt: Math.sqrt,
  cbrt: Math.cbrt,
  pow: Math.pow,
  floor: Math.floor,
  ceil: Math.ceil,
  round: Math.round,
  min: Math.min,
  max: Math.max,
};

const MATH_CONSTANTS: Record<string, number> = {
  PI: Math.PI,
  E: Math.E,
  LN2: Math.LN2,
  LN10: Math.LN10,
  SQRT1_2: Math.SQRT1_2,
  SQRT2: Math.SQRT2,
};

function factorial(n: number): number {
  if (n < 0 || !Number.isInteger(n)) throw new Error('factorial requires a non-negative integer');
  if (n > 170) return Infinity; // 171! overflows double precision anyway
  let result = 1;
  for (let i = 2; i <= n; i++) result *= i;
  return result;
}

class Parser {
  private pos = 0;
  private readonly input: string;

  constructor(input: string) {
    this.input = input;
  }

  parse(): number {
    const value = this.expr();
    this.skipSpaces();
    if (this.pos < this.input.length) {
      throw new Error(`unexpected character '${this.input[this.pos]}'`);
    }
    return value;
  }

  private skipSpaces(): void {
    while (this.input[this.pos] === ' ') this.pos++;
  }

  private peek(): string | undefined {
    this.skipSpaces();
    return this.input[this.pos];
  }

  private expr(): number {
    let value = this.term();
    for (;;) {
      const ch = this.peek();
      if (ch === '+') {
        this.pos++;
        value += this.term();
      } else if (ch === '-') {
        this.pos++;
        value -= this.term();
      } else {
        return value;
      }
    }
  }

  private term(): number {
    let value = this.power();
    for (;;) {
      const ch = this.peek();
      if (ch === '*') {
        // '**' is handled by power(); a second '*' belongs to it.
        if (this.input[this.pos + 1] === '*') return value;
        this.pos++;
        value *= this.power();
      } else if (ch === '/') {
        this.pos++;
        value /= this.power();
      } else {
        return value;
      }
    }
  }

  private power(): number {
    const base = this.unary();
    this.skipSpaces();
    if (this.input[this.pos] === '*' && this.input[this.pos + 1] === '*') {
      this.pos += 2;
      // Right-associative: 2**3**2 === 2**(3**2).
      return Math.pow(base, this.power());
    }
    return base;
  }

  private unary(): number {
    const ch = this.peek();
    if (ch === '+') {
      this.pos++;
      return this.unary();
    }
    if (ch === '-') {
      this.pos++;
      return -this.unary();
    }
    return this.postfix();
  }

  private postfix(): number {
    let value = this.primary();
    while (this.peek() === '!') {
      this.pos++;
      value = factorial(value);
    }
    return value;
  }

  private primary(): number {
    const ch = this.peek();
    if (ch === undefined) throw new Error('unexpected end of expression');

    if (ch === '(') {
      this.pos++;
      const value = this.expr();
      if (this.peek() !== ')') throw new Error('missing closing parenthesis');
      this.pos++;
      return value;
    }

    if ((ch >= '0' && ch <= '9') || ch === '.') return this.number();

    if (this.input.startsWith('Math.', this.pos)) {
      this.pos += 5;
      return this.mathReference();
    }

    throw new Error(`unexpected character '${ch}'`);
  }

  private number(): number {
    const match = /^[0-9]*\.?[0-9]+/.exec(this.input.slice(this.pos));
    if (!match) throw new Error(`invalid number at position ${this.pos}`);
    this.pos += match[0].length;
    return Number.parseFloat(match[0]);
  }

  private identifier(): string {
    const match = /^[A-Za-z_][A-Za-z0-9_]*/.exec(this.input.slice(this.pos));
    if (!match) throw new Error(`expected identifier at position ${this.pos}`);
    this.pos += match[0].length;
    return match[0];
  }

  private mathReference(): number {
    const name = this.identifier();
    if (this.peek() === '(') {
      this.pos++;
      // Object.hasOwn — a bare index lookup would resolve 'constructor' et al.
      // through the prototype chain and silently return non-functions.
      if (!Object.hasOwn(MATH_FUNCTIONS, name)) {
        throw new Error(`unknown function Math.${name}`);
      }
      const fn = MATH_FUNCTIONS[name];
      const args: number[] = [this.expr()];
      while (this.peek() === ',') {
        this.pos++;
        args.push(this.expr());
      }
      if (this.peek() !== ')') throw new Error('missing closing parenthesis');
      this.pos++;
      return fn(...args);
    }
    if (!Object.hasOwn(MATH_CONSTANTS, name)) {
      throw new Error(`unknown constant Math.${name}`);
    }
    return MATH_CONSTANTS[name];
  }
}

/**
 * Evaluate an arithmetic expression. Supports + - * / ** unary +/-,
 * parentheses, postfix `!` factorials, and a whitelist of Math functions
 * (`Math.sqrt`, `Math.log`, `Math.pow(a, b)`, ...) and constants
 * (`Math.PI`, `Math.E`, ...).
 *
 * @throws Error on any syntax error or unknown identifier.
 */
export function evaluateExpression(input: string): number {
  return new Parser(input).parse();
}
