<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { accentColors, MAX_COLORS } from '$lib/stores/settings';

  function onColorPicker(i: number, e: Event) {
    accentColors.setColor(i, (e.target as HTMLInputElement).value);
  }

  function onHex(i: number, e: Event) {
    const raw = (e.target as HTMLInputElement).value.trim();
    const full = raw.startsWith('#') ? raw : '#' + raw;
    if (/^#[0-9a-fA-F]{6}$/.test(full)) accentColors.setColor(i, full);
  }

  $: gradientPreview =
    $accentColors.length === 1
      ? $accentColors[0]
      : `linear-gradient(to right, ${$accentColors.join(', ')})`;

  let offsetPx = 0;
  let isDragging = false;
  let startX = 0;
  let baseColors: string[] = [];

  function getFloatedColors(): string[] {
    if (baseColors.length < 2) return $accentColors;
    const n = baseColors.length;
    const pxPerColor = 120;
    const fullShift = offsetPx / pxPerColor;
    const result: string[] = [];
    for (let i = 0; i < n; i++) {
      const targetIdx = i + fullShift;
      const lo = Math.floor(targetIdx);
      const hi = lo + 1;
      const t = targetIdx - lo;
      const loIdx = ((lo % n) + n) % n;
      const hiIdx = ((hi % n) + n) % n;
      result.push(lerp(baseColors[loIdx], baseColors[hiIdx], t));
    }
    return result;
  }

  function lerp(c1: string, c2: string, t: number): string {
    const r1 = parseInt(c1.slice(1, 3), 16);
    const g1 = parseInt(c1.slice(3, 5), 16);
    const b1 = parseInt(c1.slice(5, 7), 16);
    const r2 = parseInt(c2.slice(1, 3), 16);
    const g2 = parseInt(c2.slice(3, 5), 16);
    const b2 = parseInt(c2.slice(5, 7), 16);
    const r = Math.round(r1 + (r2 - r1) * t);
    const g = Math.round(g1 + (g2 - g1) * t);
    const b = Math.round(b1 + (b2 - b1) * t);
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }

  function onGradientMouseDown(e: MouseEvent) {
    isDragging = true;
    startX = e.clientX;
    baseColors = [...$accentColors];
    window.addEventListener('mousemove', onGradientMouseMove);
    window.addEventListener('mouseup', onGradientMouseUp);
  }

  function onGradientMouseMove(e: MouseEvent) {
    if (!isDragging) return;
    offsetPx = e.clientX - startX;
  }

  function onGradientMouseUp() {
    isDragging = false;
    const pxPerColor = 120;
    const steps = Math.round(offsetPx / pxPerColor);
    if (steps !== 0 && baseColors.length > 0) {
      const n = baseColors.length;
      const rotated: string[] = [];
      for (let i = 0; i < n; i++) {
        rotated.push(baseColors[(i + steps) % n]);
      }
      rotated.forEach((c, i) => accentColors.setColor(i, c));
    }
    offsetPx = 0;
    baseColors = [];
    window.removeEventListener('mousemove', onGradientMouseMove);
    window.removeEventListener('mouseup', onGradientMouseUp);
  }
</script>

<!-- Gradient preview bar -->
<div
  class="gradient-preview"
  role="slider"
  tabindex="0"
  aria-valuenow={$accentColors.length}
  aria-valuemin={1}
  aria-valuemax={MAX_COLORS}
  aria-label="Color gradient preview"
  style="background: {gradientPreview}; cursor: grab;"
  onmousedown={onGradientMouseDown}
  class:dragging={isDragging}
></div>
<p class="color-limit-note mono">Máximo {MAX_COLORS} colores</p>

<!-- Per-color rows -->
<div class="color-list">
  {#each $accentColors as color, i}
    <div class="color-entry">
      <span class="color-idx mono">{i + 1}</span>
      <input type="color" class="color-swatch" value={color} oninput={(e) => onColorPicker(i, e)} />
      <input
        type="text"
        class="hex-input mono"
        maxlength="7"
        value={color}
        oninput={(e) => onHex(i, e)}
        placeholder="#c8a96e"
      />
      {#if $accentColors.length > 1}
        <button
          class="color-rm"
          onclick={() => accentColors.removeColor(i)}
          title="Quitar"
          aria-label="Quitar"
        >
          <DynamicIcon name="Minus" size={10} />
        </button>
      {/if}
    </div>
  {/each}
</div>

{#if $accentColors.length < MAX_COLORS}
  <button class="add-color-btn mono" onclick={() => accentColors.addColor()}>
    <DynamicIcon name="Plus" size={10} /> agregar color
  </button>
{/if}

<style>
  /* ── Accent gradient builder ── */
  .gradient-preview {
    height: 24px;
    border-radius: 4px;
    margin: 8px 0 10px;
    transition: background 300ms ease;
    overflow-x: auto;
    overflow-y: hidden;
    white-space: nowrap;
    scrollbar-width: thin;
    scrollbar-color: var(--text-disabled) transparent;
  }

  .gradient-preview::-webkit-scrollbar {
    height: 4px;
  }

  .gradient-preview::-webkit-scrollbar-track {
    background: transparent;
  }

  .gradient-preview::-webkit-scrollbar-thumb {
    background: var(--text-disabled);
    border-radius: 2px;
  }

  .gradient-preview.dragging {
    cursor: grabbing;
  }

  .color-limit-note {
    margin: -4px 0 10px;
    font-size: 10px;
    color: var(--text-disabled);
    letter-spacing: 0.04em;
  }

  .color-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .color-entry {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .color-idx {
    font-size: 9px;
    color: var(--text-disabled);
    width: 10px;
    text-align: right;
  }

  .color-swatch {
    width: 26px;
    height: 26px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: none;
    cursor: pointer;
    padding: 2px;
    flex-shrink: 0;
  }

  .hex-input {
    flex: 1;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 7px;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
  }
  .hex-input:focus {
    border-color: var(--text-muted);
  }

  .color-rm {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .color-rm:hover {
    color: var(--error);
    border-color: var(--error);
  }

  .add-color-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 8px;
    background: none;
    border: 1px dashed var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    font-size: 10px;
    padding: 4px 10px;
    cursor: pointer;
    width: 100%;
    justify-content: center;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .add-color-btn:hover {
    color: var(--text-secondary);
    border-color: var(--text-muted);
  }
  .add-color-btn:focus-visible {
    outline: none;
    border-color: var(--xp);
    color: var(--xp);
  }
</style>
