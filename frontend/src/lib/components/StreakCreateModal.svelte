<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { X, Calendar, Snowflake, Target, Clock, Archive } from 'lucide-svelte';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import LazyIconPicker from '$lib/components/LazyIconPicker.svelte';
  import type { PersonalStreak } from '$lib/api';
  import { liquidGlass } from '$lib/actions/liquidGlass';
  import { getContrastColor } from '$lib/stores/settings';
  import { t } from 'svelte-i18n';

  export let open = false;
  export let editStreak: PersonalStreak | null = null;

  const dispatch = createEventDispatcher<{
    close: void;
    save: {
      name: string; emoji: string; icon: string; description: string;
      color: string; theme: string; category: string;
      start_date: string | null; target_date: string | null;
      offset: number; frequency: string; frequency_days: number;
      freeze_count: number;
    };
    archive: void;
  }>();

  // ── Form state ──────────────────────────────────────────────────────────────
  let name = '';
  let emoji = '🔥';
  let icon = '';
  let description = '';
  let color = '#c8a96e';
  let theme = 'solid';
  let category = 'general';
  let startDate = new Date().toISOString().split('T')[0];
  let targetDate = '';
  let offset = 0;
  let frequency = 'daily';
  let frequencyDays = 1;
  let freezeCount = 0;
  let useIcon = false;

  // ── Presets ─────────────────────────────────────────────────────────────────
  const COLOR_PRESETS = [
    { name: 'Rojo',     hex: '#ef4444' },
    { name: 'Coral',    hex: '#f97316' },
    { name: 'Ámbar',    hex: '#f59e0b' },
    { name: 'Lima',     hex: '#84cc16' },
    { name: 'Esmeralda',hex: '#10b981' },
    { name: 'Cian',     hex: '#06b6d4' },
    { name: 'Azul',     hex: '#3b82f6' },
    { name: 'Violeta',  hex: '#8b5cf6' },
    { name: 'Rosa',     hex: '#ec4899' },
    { name: 'Slate',    hex: '#64748b' },
  ];

  const EMOJIS = Array.from(new Set([
    '🔥','💪','🏃','🚴','🏊','🏋️','🤸','🧘','⛹️','🤾','🏌️','⛷️','🏂','🪂',
    '❤️','💚','💙','💛','🧠','👁️','👂','👃','💊','💉','🩹','🩺',
    '📚','📖','📝','✍️','📓','📔','📕','📗','📘','🖊️','🖍️','📜','📋','🗂️',
    '🎨','🎭','🎬','🎤','🎧','🎵','🎶','🎸','🎹','🎺','🎷','📸','🖼️',
    '🌿','🍀','🌱','🌲','🌳','🌴','🌵','🌾','🌻','🌺','🌸','🌼','🌷','🌹','🌎',
    '🍎','🍊','🍋','🍌','🍇','🍓','🥗','🥙','🍕','🍔','🍟','🌮','☕','🍵',
    '💻','📱','⌚','🎮','🧩','🪀','🪁','🎯','🔐','🔒','🔓','🔑','⚙️','🔧','🔨','⚒️',
    '✈️','🚂','🚗','🚙','🚕','🚌','🚎','🏎️','🚓','🚑','🚒','🚐','🛻','🚚','🚛','🚜',
    '☀️','🌤️','⛅','🌥️','☁️','🌦️','🌧️','⛈️','🌩️','🌨️','❄️','☃️','⛄','🌊','💧','💦',
    '😀','😃','😄','😁','😆','😊','☺️','😉','😌','😚','😍','🤩','😘','🥰','😏','😐',
    '🥇','🥈','🥉','🏆','🎖️','🏅','⭐','🌟','✨','💫','🎊','🎉','🎁'
  ]));

  // Auto-calculate offset from start_date to today
  function calculateDaysBetween(fromDate: string, toDate: string): number {
    const from = new Date(fromDate);
    const to = new Date(toDate);
    // Use Math.max(0, ...) to ensure we don't have negative offset if date is in the future
    const diffTime = to.getTime() - from.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    return Math.max(0, diffDays);
  }

  $: {
    if (startDate && !editStreak) {
      const today = new Date().toISOString().split('T')[0];
      offset = calculateDaysBetween(startDate, today);
    }
  }

  const CATEGORIES = [
    { id: 'general',     label: 'General',     icon: 'Layers' },
    { id: 'salud',       label: 'Salud',       icon: 'Heart' },
    { id: 'estudio',     label: 'Estudio',     icon: 'BookOpen' },
    { id: 'fitness',     label: 'Fitness',     icon: 'Dumbbell' },
    { id: 'creatividad', label: 'Creatividad', icon: 'Palette' },
    { id: 'habito',      label: 'Hábito',      icon: 'Repeat' },
    { id: 'trabajo',     label: 'Trabajo',     icon: 'Briefcase' },
  ];

  const THEMES = [
    { id: 'solid',    label: 'Sólido' },
    { id: 'gradient', label: 'Gradiente' },
    { id: 'glow',     label: 'Radiante' },
    { id: 'minimal',  label: 'Minimal' },
    { id: 'lcd',      label: 'Retro' },
    { id: 'neon',     label: 'Neon' },
    { id: 'glass',    label: 'Glass' },
    { id: 'sketch',   label: 'Sketch' },
  ];

  // ── Sections ────────────────────────────────────────────────────────────────
  let activeSection = 'basics';

  // ── Lifecycle ───────────────────────────────────────────────────────────────
  $: if (open) {
    if (editStreak) {
      name = editStreak.name;
      emoji = editStreak.emoji;
      icon = editStreak.icon || '';
      useIcon = !!editStreak.icon;
      description = editStreak.description;
      color = editStreak.color || '#c8a96e';
      theme = editStreak.theme || 'solid';
      category = editStreak.category || 'general';
      startDate = editStreak.start_date || new Date().toISOString().split('T')[0];
      targetDate = editStreak.target_date || '';
      offset = editStreak.offset;
      frequency = editStreak.frequency || 'daily';
      frequencyDays = editStreak.frequency_days || 1;
      freezeCount = editStreak.freeze_count || 0;
    } else {
      resetForm();
    }
    activeSection = 'basics';
  }

  function resetForm() {
    name = ''; emoji = '🔥'; icon = ''; useIcon = false;
    description = ''; color = '#c8a96e'; theme = 'solid';
    category = 'general'; startDate = new Date().toISOString().split('T')[0];
    targetDate = ''; offset = 0; frequency = 'daily';
    frequencyDays = 1; freezeCount = 0;
  }

  function close() { dispatch('close'); }

  function save() {
    if (!name.trim()) return;
    dispatch('save', {
      name: name.trim(),
      emoji: useIcon ? '' : emoji,
      icon: useIcon ? icon : '',
      description,
      color,
      theme,
      category,
      start_date: startDate || null,
      target_date: targetDate || null,
      offset,
      frequency,
      frequency_days: Math.max(1, frequencyDays),
      freeze_count: freezeCount,
    });
    // Don't call close() here — let the parent close after it processes save
  }

  function archive() {
    dispatch('archive');
  }

  function onBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }

  $: isEdit = !!editStreak;
  $: canSave = name.trim().length > 0;

  $: previewStyle = `--theme-ac: ${color};`;

  function previewFreqLabel(): string {
    if (frequency === 'every_n' && frequencyDays > 1) return `cada ${frequencyDays}d`;
    return 'diaria';
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div class="modal-backdrop" role="presentation" onclick={onBackdrop}>
    <div class="modal-panel" role="dialog" aria-modal="true" aria-label={$t('streakCreateModal.createTitle')} onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <span class="modal-title mono">{isEdit ? 'EDITAR RACHA' : 'NUEVA RACHA'}</span>
        <button class="close-btn" onclick={close} aria-label={$t('streakCreateModal.close')}><X size={14} /></button>
      </div>

      <div class="modal-body">
        <div class="modal-grid">
          <!-- Left column: hard data -->
          <div class="modal-col modal-col-data">
            <div class="field">
              <label>{$t('streakCreateModal.name')}</label>
              <input bind:value={name} placeholder={$t('streakCreateModal.namePlaceholder')} autofocus />
            </div>

            <div class="field">
              <label>{$t('streakCreateModal.description')} <span class="optional">{$t('streakCreateModal.optional')}</span></label>
              <input bind:value={description} placeholder={$t('streakCreateModal.descriptionPlaceholder')} />
            </div>

            <div class="field">
              <label>{$t('streakCreateModal.frequency')}</label>
              <div class="freq-row">
                <button class="freq-btn" class:selected={frequency === 'daily'} onclick={() => { frequency = 'daily'; frequencyDays = 1; }}>{$t('streakCreateModal.daily')}</button>
                <button class="freq-btn" class:selected={frequency === 'weekly'} onclick={() => { frequency = 'weekly'; frequencyDays = 1; }}>{$t('streakCreateModal.weekly')}</button>
                <button class="freq-btn" class:selected={frequency === 'monthly'} onclick={() => { frequency = 'monthly'; frequencyDays = 1; }}>{$t('streakCreateModal.monthly')}</button>
                <button class="freq-btn" class:selected={frequency === 'every_n'} onclick={() => { frequency = 'every_n'; }}>cada N</button>
              </div>
            </div>

            {#if frequency === 'every_n'}
              <div class="freq-n-row">
                <span class="freq-n-label">{$t('streakCreateModal.every')}</span>
                <input type="number" bind:value={frequencyDays} min="1" max="365" class="freq-n-input" />
                <span class="freq-n-label">días</span>
              </div>
            {/if}

            <div class="field">
              <label><Calendar size={11} /> Fecha de inicio</label>
              <input type="date" bind:value={startDate} disabled={isEdit} />
            </div>

            <div class="field">
              <label><Target size={11} /> Fecha objetivo <span class="optional">(op.)</span></label>
              <input type="date" bind:value={targetDate} />
            </div>

            <div class="field">
              <label><Clock size={11} /> Días desde inicio</label>
              <input type="number" bind:value={offset} min="0" disabled={isEdit} placeholder={$t('streakCreateModal.offsetPlaceholder')} />
              <span class="field-hint">{isEdit ? 'Este valor no se puede modificar una vez creada la racha' : 'Se calcula automáticamente desde la fecha de inicio'}</span>
            </div>

            <div class="field">
              <label><Snowflake size={11} /> Freezes (escudos)</label>
              <input type="number" bind:value={freezeCount} min="0" max="30" />
              <span class="field-hint">{$t('streakCreateModal.freezeHint')}</span>
            </div>

            <div class="field">
              <label>{$t('streakCreateModal.visualTheme')}</label>
              <div class="theme-grid">
                {#each THEMES as themeOpt}
                  <button class="theme-btn" class:selected={theme === themeOpt.id} onclick={() => theme = themeOpt.id}>
                    {themeOpt.label}
                  </button>
                {/each}
              </div>
            </div>
          </div>

          <!-- Right column: preview + customization -->
          <div class="modal-col modal-col-preview">
            <div
              class="preview-card"
              class:theme-solid={theme === 'solid'}
              class:theme-gradient={theme === 'gradient'}
              class:theme-glow={theme === 'glow'}
              class:theme-minimal={theme === 'minimal'}
              class:theme-lcd={theme === 'lcd'}
              class:theme-neon={theme === 'neon'}
              class:theme-glass={theme === 'glass'}
              class:theme-sketch={theme === 'sketch'}
              style={previewStyle}
            >
              <div class="preview-icon">
                {#if useIcon && icon}
                  <StreakIcon name={icon} size={24} />
                {:else}
                  <span class="preview-emoji">{emoji}</span>
                {/if}
              </div>
              <div class="preview-info">
                <span class="preview-name">{name || 'Nombre de la racha'}</span>
                <span class="preview-meta mono">{name ? previewFreqLabel() : 'frecuencia'}</span>
              </div>
            </div>

            <div class="field">
              <label>{$t('streakCreateModal.icon')}</label>
              <div class="icon-toggle-row">
                <button class="icon-type-btn" class:selected={!useIcon} onclick={() => useIcon = false}>{$t('streakCreateModal.emoji')}</button>
                <button class="icon-type-btn" class:selected={useIcon} onclick={() => { useIcon = true; if (!icon) icon = 'Flame'; }}>{$t('streakCreateModal.icon')}</button>
              </div>
            </div>

            {#if !useIcon}
              <div class="field icon-picker-field">
                <div class="emoji-grid">
                  {#each EMOJIS as e}
                    <button class="emoji-btn" class:selected={emoji === e} onclick={() => emoji = e}>{e}</button>
                  {/each}
                </div>
              </div>
            {:else}
              <div class="field icon-picker-field">
                <LazyIconPicker selected={icon} color={color} onSelect={(ic) => icon = ic} />
              </div>
            {/if}

            <div class="field">
              <label>{$t('streakCreateModal.color')}</label>
              <div class="color-grid">
                {#each COLOR_PRESETS as c}
                  <button
                    class="color-btn"
                    class:selected={color === c.hex}
                    style="--btn-color: {c.hex}; background: {c.hex};"
                    onclick={() => color = c.hex}
                    title={c.name}
                    aria-label={c.name}
                  />
                {/each}
              </div>
              <div class="color-manual-row">
                <div class="color-swatch-wrapper" style="background: {color};">
                  <input
                    type="color"
                    class="color-swatch"
                    value={color}
                    oninput={(e) => color = e.currentTarget.value}
                  />
                </div>
                <input
                  type="text"
                  class="hex-input mono"
                  maxlength="7"
                  bind:value={color}
                  placeholder="#c8a96e"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer" class:theme-sketch={theme === 'sketch'} class:theme-glow={theme === 'glow'} class:theme-gradient={theme === 'gradient'} class:theme-neon={theme === 'neon'}>
        {#if isEdit}
          <button class="btn-archive" onclick={archive} title={editStreak?.is_archived ? 'Desarchivar racha' : 'Archivar racha'}>
            <Archive size={14} />
            {editStreak?.is_archived ? 'Desarchivar' : 'Archivar'}
          </button>
        {/if}
        <button class="btn-cancel" onclick={close}>{$t('streakCreateModal.cancel')}</button>
        <button class="btn-save" disabled={!canSave} onclick={save} style="--btn-color: {color};">
          {isEdit ? $t('streakCreateModal.update') : $t('streakCreateModal.create')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed; inset: 0; z-index: var(--z-overlay);
    background: rgba(0,0,0,0.75); backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
  }

  .modal-panel {
    width: 760px;
    height: auto;
    max-width: calc(100vw - 24px);
    max-height: calc(100vh - 24px);
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 12px; display: flex; flex-direction: column;
    overflow: hidden;
    transition: height 0.25s ease;
  }

  .modal-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; border-bottom: 1px solid var(--border);
  }

  .modal-title {
    font-size: 11px; letter-spacing: 0.1em; color: var(--text-secondary);
  }

  .close-btn {
    background: none; border: none; color: var(--text-muted);
    cursor: pointer; padding: 4px; display: flex; border-radius: var(--r);
  }
  .close-btn:hover { color: var(--text-primary); }

  .modal-body {
    overflow-y: auto;
    padding: 20px;
    display: flex; flex-direction: column; gap: 16px;
  }

  .modal-grid {
    display: grid;
    grid-template-columns: 0.85fr 1.15fr;
    gap: 20px;
  }

  .modal-col {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  /* Preview card */
  .preview-card {
    display: flex; align-items: center; gap: 16px;
    padding: 18px 20px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
    position: relative;
    overflow: hidden;
    isolation: isolate;
    transition: all 0.2s ease;
  }

  .preview-card > * {
    position: relative;
    z-index: 1;
  }

  .preview-card::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .preview-card.theme-gradient {
    border-color: color-mix(in srgb, var(--theme-ac) 30%, var(--border));
  }

  .preview-card.theme-gradient::before {
    opacity: 1;
    background:
      linear-gradient(
        125deg,
        color-mix(in srgb, var(--theme-ac) 16%, transparent) 0%,
        transparent 45%,
        color-mix(in srgb, var(--theme-ac) 10%, transparent) 100%
      );
  }

  .preview-card.theme-glow {
    border-color: color-mix(in srgb, var(--theme-ac) 22%, var(--border));
    box-shadow:
      0 0 14px color-mix(in srgb, var(--theme-ac) 12%, transparent),
      inset 0 0 0 1px color-mix(in srgb, var(--theme-ac) 14%, transparent);
  }

  .preview-card.theme-glow::before {
    opacity: 1;
    background:
      radial-gradient(
        120% 90% at 50% 50%,
        color-mix(in srgb, var(--theme-ac) 12%, transparent) 0%,
        transparent 70%
      );
  }

  .preview-card.theme-minimal {
    background: color-mix(in srgb, var(--theme-ac) 8%, transparent);
    border: 1px solid transparent;
  }

  .preview-card.theme-lcd {
    background-color: var(--theme-ac);
    background-image:
      linear-gradient(rgba(0, 0, 0, 0.1) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
    background-size: 3px 3px;
    border: 1px solid color-mix(in srgb, var(--theme-ac) 70%, black);
    box-shadow: inset 0 0 10px rgba(0,0,0,0.15);
  }
  .preview-card.theme-lcd .preview-name {
    color: color-mix(in srgb, var(--theme-ac) 20%, black); font-weight: 700;
  }
  .preview-card.theme-lcd .preview-meta {
    color: color-mix(in srgb, var(--theme-ac) 20%, black); opacity: 0.7; font-weight: 600;
  }
  .preview-card.theme-lcd .preview-emoji,
  .preview-card.theme-lcd .preview-icon :global(svg) {
    filter: grayscale(1) brightness(0) opacity(0.8);
  }

  .preview-card.theme-neon {
    background: color-mix(in srgb, var(--theme-ac) 8%, var(--surface));
    border: 1px solid var(--theme-ac);
    box-shadow: 0 0 10px color-mix(in srgb, var(--theme-ac) 25%, transparent);
  }
  .preview-card.theme-neon .preview-name {
    text-shadow: 0 0 10px var(--theme-ac);
  }

  .preview-card.theme-glass {
    border: 1px solid transparent;
  }

  .preview-card.theme-solid {
    background: transparent;
    border: 1px solid var(--theme-ac);
  }

  .preview-card.theme-sketch {
    border: 1px dashed var(--theme-ac); border-radius: 2px;
  }

  .preview-icon {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-size: 22px;
  }

  .preview-emoji { font-size: 22px; }
  .preview-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .preview-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .preview-meta {
    font-size: 10px;
    color: var(--text-muted);
  }

  /* Fields */
  .field { display: flex; flex-direction: column; gap: 5px; }
  .field label {
    font-size: 11px; color: var(--text-muted); text-transform: uppercase;
    letter-spacing: 0.05em; font-family: var(--font-mono);
    display: flex; align-items: center; justify-content: center; gap: 4px;
    text-align: center;
  }
  .optional { font-size: 9px; color: var(--text-disabled); text-transform: lowercase; }

  .field input {
    background: var(--surface); border: 1px solid var(--border);
    padding: 8px 12px; border-radius: 4px; color: var(--text-primary);
    font-size: 13px; outline: none; transition: border-color 0.15s;
  }
  .field input:focus { border-color: var(--text-muted); }

  .field input[type="number"] {
    -moz-appearance: textfield;
    appearance: textfield;
  }

  .field input[type="number"]::-webkit-outer-spin-button,
  .field input[type="number"]::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  .field-hint {
    font-size: 10px; color: var(--text-disabled); line-height: 1.3;
    min-height: 26px;
  }

  .field-row { display: flex; gap: 12px; align-items: flex-start; }
  .field.half { flex: 1; min-width: 0; }

  /* Frequency */
  .freq-row { display: flex; gap: 6px; }
  .freq-btn {
    flex: 1; padding: 7px; font-size: 12px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted); cursor: pointer;
    transition: all 0.15s; font-family: var(--font-mono);
  }
  .freq-btn:hover { border-color: var(--text-muted); }
  .freq-btn.selected { border-color: var(--text-primary); color: var(--text-primary); }

  .freq-n-row {
    display: flex; align-items: center; gap: 8px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; padding: 8px 12px;
  }
  .freq-n-label {
    font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);
    white-space: nowrap;
  }
  .freq-n-input {
    width: 60px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 4px; padding: 4px 8px; color: var(--text-primary);
    font-size: 13px; outline: none; text-align: center;
    -moz-appearance: textfield; appearance: textfield;
  }
  .freq-n-input:focus { border-color: var(--text-muted); }
  .freq-n-input::-webkit-outer-spin-button,
  .freq-n-input::-webkit-inner-spin-button {
    -webkit-appearance: none; margin: 0;
  }

  /* Icon toggles */
  .icon-toggle-row { display: flex; gap: 6px; }
  .icon-type-btn {
    flex: 1; padding: 6px; font-size: 11px; font-family: var(--font-mono);
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted); cursor: pointer;
    transition: all 0.15s;
  }
  .icon-type-btn.selected { border-color: var(--text-primary); color: var(--text-primary); }

  /* Icon picker field — fixed height container so switching between
     emoji and icon modes does not resize the modal. */
  .icon-picker-field {
    height: 320px;
    min-height: 320px;
    max-height: 320px;
    overflow: hidden;
  }
  .icon-picker-field > :global(*) {
    height: 100%;
    min-height: 0;
    max-height: 100%;
  }

  /* Emoji grid */
  .emoji-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
    height: 100%;
    overflow-y: auto;
    padding: 4px;
    align-content: start;
  }
  .emoji-btn {
    width: 36px; height: 36px; font-size: 18px;
    background: none; border: 1px solid transparent;
    cursor: pointer; border-radius: 4px; display: flex;
    align-items: center; justify-content: center; transition: all 0.15s;
    filter: contrast(1.15) brightness(1.1); color: inherit; line-height: 1;
  }
  .emoji-btn:hover { background: var(--elevated); }
  .emoji-btn.selected { border-color: var(--text-primary); background: var(--elevated); }

  /* Theme selector */
  .theme-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
  }
  .theme-btn {
    padding: 8px 4px; font-size: 11px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted);
    cursor: pointer; transition: all 0.15s; font-family: var(--font-mono);
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .theme-btn:hover { border-color: var(--text-muted); }
  .theme-btn.selected { border-color: var(--text-primary); color: var(--text-primary); }

  /* Color picker */
  .color-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(32px, 1fr));
    gap: 6px;
    padding: 4px;
  }
  .color-btn {
    width: 32px; height: 32px;
    border: 2px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    padding: 0;
  }
  .color-btn:hover {
    transform: scale(1.1);
    border-color: var(--text-muted);
  }
  .color-btn.selected {
    border-color: var(--text-primary);
    box-shadow: 0 0 0 1px var(--bg), 0 0 0 3px var(--text-primary);
  }

  /* Manual color picker */
  .color-manual-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 8px;
  }
  .color-swatch-wrapper {
    width: 36px;
    height: 36px;
    border: 1px solid var(--border);
    border-radius: 6px;
    flex-shrink: 0;
    overflow: hidden;
    position: relative;
    cursor: pointer;
  }
  .color-swatch {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: none;
    padding: 0;
    cursor: pointer;
    opacity: 0;
  }
  .color-swatch::-webkit-color-swatch-wrapper { padding: 0; }
  .color-swatch::-webkit-color-swatch { border: none; }
  .color-swatch::-moz-color-swatch { border: none; }
  .hex-input {
    width: 90px;
    flex: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 13px;
    color: var(--text-primary);
    outline: none;
    transition: border-color 0.15s;
  }
  .hex-input:focus { border-color: var(--text-muted); }

  /* Footer */
  .modal-footer {
    display: flex; justify-content: flex-end; gap: 10px;
    padding: 14px 20px; border-top: 1px solid var(--border);
  }

  .btn-cancel {
    padding: 8px 16px; background: var(--elevated);
    border: 1px solid var(--border); border-radius: 6px;
    color: var(--text-secondary); font-size: 13px; cursor: pointer;
    transition: all 0.2s;
  }
  .btn-cancel:hover { background: var(--surface); }

  .btn-archive {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 14px; background: var(--surface);
    border: 1px solid var(--border); border-radius: 8px;
    color: var(--text-secondary); font-size: 13px; font-weight: 500;
    cursor: pointer; transition: all 0.15s;
  }
  .btn-archive:hover { border-color: var(--text-muted); color: var(--text-primary); background: var(--elevated); }

  .btn-save {
    padding: 8px 20px; background: var(--btn-color, var(--text-primary));
    border: none; border-radius: 6px; color: var(--bg);
    font-size: 13px; font-weight: 600; cursor: pointer;
    transition: all 0.2s;
  }
  .btn-save:hover { opacity: 0.9; transform: translateY(-1px); }
  .btn-save:disabled { opacity: 0.3; pointer-events: none; }

  /* Sketch theme for modal footer */
  .modal-footer.theme-sketch .btn-save,
  .modal-footer.theme-sketch .btn-cancel,
  .modal-footer.theme-sketch .btn-archive {
    border: 1px dashed var(--text-muted);
    border-radius: 2px;
    background: transparent;
    color: var(--text-primary);
  }
  .modal-footer.theme-sketch .btn-save {
    border-color: var(--btn-color, var(--text-primary));
    color: var(--btn-color, var(--text-primary));
  }
  .modal-footer.theme-sketch .btn-save:hover {
    background: color-mix(in srgb, var(--btn-color, var(--text-primary)) 10%, transparent);
  }
  .modal-footer.theme-sketch .btn-cancel:hover,
  .modal-footer.theme-sketch .btn-archive:hover {
    background: color-mix(in srgb, var(--text-muted) 10%, transparent);
  }

  /* Glow, Gradient & Neon theme for modal footer */
  .modal-footer.theme-glow .btn-save,
  .modal-footer.theme-glow .btn-cancel,
  .modal-footer.theme-glow .btn-archive,
  .modal-footer.theme-gradient .btn-save,
  .modal-footer.theme-gradient .btn-cancel,
  .modal-footer.theme-gradient .btn-archive,
  .modal-footer.theme-neon .btn-save,
  .modal-footer.theme-neon .btn-cancel,
  .modal-footer.theme-neon .btn-archive {
    border-color: transparent;
    background: transparent;
    color: var(--text-primary);
  }
  .modal-footer.theme-glow .btn-save,
  .modal-footer.theme-gradient .btn-save,
  .modal-footer.theme-neon .btn-save {
    color: var(--btn-color, var(--text-primary));
  }
  .modal-footer.theme-glow .btn-save:hover,
  .modal-footer.theme-gradient .btn-save:hover,
  .modal-footer.theme-neon .btn-save:hover {
    border-color: transparent;
    background: color-mix(in srgb, var(--btn-color, var(--text-primary)) 10%, transparent);
  }
  .modal-footer.theme-glow .btn-cancel:hover,
  .modal-footer.theme-glow .btn-archive:hover,
  .modal-footer.theme-gradient .btn-cancel:hover,
  .modal-footer.theme-gradient .btn-archive:hover,
  .modal-footer.theme-neon .btn-cancel:hover,
  .modal-footer.theme-neon .btn-archive:hover {
    border-color: transparent;
    background: color-mix(in srgb, var(--text-muted) 10%, transparent);
  }

  @media (max-width: 640px) {
    .modal-panel {
      width: calc(100vw - 16px);
      max-width: none;
      max-height: calc(100vh - 16px);
    }
    .modal-grid {
      grid-template-columns: 1fr;
      gap: 16px;
    }
    .theme-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    /* Preview first on mobile, then data fields */
    .modal-col-preview { order: -1; }
  }
</style>
