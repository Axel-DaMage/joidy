<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';

  let calcInput = $state('');
  let calcResult = $state('0');
  let lastResult = $state('');

  function evaluateCalc() {
    try {
      if (!calcInput.trim()) { calcResult = '0'; return; }

      let expr = calcInput
        .replace(/sin\(/g, 'Math.sin(')
        .replace(/cos\(/g, 'Math.cos(')
        .replace(/tan\(/g, 'Math.tan(')
        .replace(/log\(/g, 'Math.log10(')
        .replace(/ln\(/g, 'Math.log(')
        .replace(/√\(/g, 'Math.sqrt(')
        .replace(/π/g, 'Math.PI')
        .replace(/e/g, 'Math.E')
        .replace(/\^/g, '**')
        .replace(/(\d+)!/g, (_match: string, n: string) => {
          let f = 1; for (let i = 1; i <= +n; i++) f *= i; return f + '';
        })
        .replace(/Ans/g, lastResult || '0')
        .replace(/÷/g, '/')
        .replace(/×/g, '*');

      const sanitize = expr.replace(/[^0-9+\-*/(). Math[a-z0-9]!]/g, '');
      const res = new Function('return ' + sanitize)();
      if (typeof res === 'number') {
        calcResult = Number(res.toFixed(8)).toString();
      } else {
        calcResult = res + '';
      }
    } catch {
      calcResult = '...';
    }
  }

  function addCalc(val: string) {
    if (val === '=') {
      evaluateCalc();
      if (calcResult !== '...') lastResult = calcResult;
      return;
    }
    if (val === 'AC') { calcInput = ''; calcResult = '0'; return; }
    if (val === 'Ans') { calcInput += 'Ans'; evaluateCalc(); return; }
    if (val === 'x!') { calcInput += '!'; evaluateCalc(); return; }
    if (val === 'xy') { calcInput += '^'; evaluateCalc(); return; }
    if (val === '√') { calcInput += '√('; evaluateCalc(); return; }

    if (['sin', 'cos', 'tan', 'log', 'ln'].includes(val)) {
      calcInput += val + '(';
    } else {
      calcInput += val;
    }
    evaluateCalc();
  }
</script>

<div class="scientific-calc">
  <div class="calc-display">
    <div class="calc-history"><DynamicIcon name="History" size={10} /></div>
    <input
      class="calc-input"
      bind:value={calcInput}
      oninput={evaluateCalc}
      placeholder="0"
    />
    <div class="calc-res">{calcResult}</div>
  </div>
  <div class="calc-grid">
    <button class="calc-btn sm" onclick={() => {}}>Deg</button>
    <button class="calc-btn sm" onclick={() => addCalc('x!')}>x!</button>
    <button class="calc-btn sm" onclick={() => addCalc('(')}>(</button>
    <button class="calc-btn sm" onclick={() => addCalc(')')}>)</button>
    <button class="calc-btn sm" onclick={() => addCalc('%')}>%</button>
    <button class="calc-btn sm clear" onclick={() => addCalc('AC')}>AC</button>
    <button class="calc-btn op" onclick={() => addCalc('÷')}>÷</button>

    <button class="calc-btn sm" onclick={() => addCalc('inv')}>Inv</button>
    <button class="calc-btn sm" onclick={() => addCalc('sin')}>sin</button>
    <button class="calc-btn sm" onclick={() => addCalc('ln')}>ln</button>
    <button class="calc-btn num" onclick={() => addCalc('7')}>7</button>
    <button class="calc-btn num" onclick={() => addCalc('8')}>8</button>
    <button class="calc-btn num" onclick={() => addCalc('9')}>9</button>
    <button class="calc-btn op" onclick={() => addCalc('×')}>×</button>

    <button class="calc-btn sm" onclick={() => addCalc('π')}>π</button>
    <button class="calc-btn sm" onclick={() => addCalc('cos')}>cos</button>
    <button class="calc-btn sm" onclick={() => addCalc('log')}>log</button>
    <button class="calc-btn num" onclick={() => addCalc('4')}>4</button>
    <button class="calc-btn num" onclick={() => addCalc('5')}>5</button>
    <button class="calc-btn num" onclick={() => addCalc('6')}>6</button>
    <button class="calc-btn op" onclick={() => addCalc('-')}>-</button>

    <button class="calc-btn sm" onclick={() => addCalc('e')}>e</button>
    <button class="calc-btn sm" onclick={() => addCalc('tan')}>tan</button>
    <button class="calc-btn sm" onclick={() => addCalc('√')}>√</button>
    <button class="calc-btn num" onclick={() => addCalc('1')}>1</button>
    <button class="calc-btn num" onclick={() => addCalc('2')}>2</button>
    <button class="calc-btn num" onclick={() => addCalc('3')}>3</button>
    <button class="calc-btn op" onclick={() => addCalc('+')}>+</button>

    <button class="calc-btn sm" onclick={() => addCalc('Ans')}>Ans</button>
    <button class="calc-btn sm" onclick={() => addCalc('EXP')}>EXP</button>
    <button class="calc-btn sm" onclick={() => addCalc('xy')}>x<sup>y</sup></button>
    <button class="calc-btn num" onclick={() => addCalc('0')}>0</button>
    <button class="calc-btn num" onclick={() => addCalc('.')}>.</button>
    <button class="calc-btn equals" onclick={() => addCalc('=')}>=</button>
    <div></div>
  </div>
</div>

<style>
  .scientific-calc {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .calc-display {
    position: relative;
    background: color-mix(in srgb, var(--text-primary) 8%, var(--bg));
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 8px 10px;
    min-height: 70px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }

  .calc-history {
    position: absolute;
    top: 6px;
    right: 8px;
    opacity: 0.2;
  }

  .calc-input {
    background: transparent;
    border: none;
    outline: none;
    font-family: var(--font-mono);
    font-size: 14px;
    text-align: right;
    color: var(--text-primary);
    width: 100%;
    padding: 2px 0;
  }

  .calc-res {
    font-family: var(--font-mono);
    font-size: 20px;
    font-weight: 700;
    text-align: right;
    color: var(--accent);
    min-height: 22px;
  }

  .calc-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
  }

  .calc-btn {
    width: 100%;
    aspect-ratio: 1.2;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 11px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.1s;
    padding: 0;
  }

  .calc-btn:hover {
    background: var(--elevated);
    border-color: var(--text-muted);
  }

  .calc-btn:active {
    transform: scale(0.95);
  }

  .calc-btn.sm { font-size: 9px; }
  .calc-btn.num { font-weight: 600; }
  .calc-btn.op { color: var(--accent); font-weight: 600; }
  .calc-btn.clear { color: var(--error); font-weight: 600; }
  .calc-btn.equals {
    background: var(--accent);
    color: var(--bg);
    font-weight: 700;
  }
  .calc-btn.equals:hover {
    opacity: 0.85;
  }
</style>
