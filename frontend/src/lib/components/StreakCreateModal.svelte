<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { fade, slide } from 'svelte/transition';
  import { X, Calendar, Snowflake, Target, Clock, Archive } from 'lucide-svelte';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import type { PersonalStreak } from '$lib/api';
  import { liquidGlass } from '$lib/actions/liquidGlass';

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
    { name: 'Gold',      hex: '#c8a96e' },
    { name: 'Esmeralda', hex: '#10b981' },
    { name: 'Cyan',      hex: '#06b6d4' },
    { name: 'Azul',      hex: '#3b82f6' },
    { name: 'Violeta',   hex: '#8b5cf6' },
    { name: 'Rosa',      hex: '#ec4899' },
    { name: 'Ámbar',     hex: '#f59e0b' },
    { name: 'Coral',     hex: '#ef4444' },
    { name: 'Lima',      hex: '#84cc16' },
    { name: 'Slate',     hex: '#64748b' },
    { name: 'Teal',      hex: '#14b8a6' },
    { name: 'Blanco',    hex: '#e2e8f0' },
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

  const ICON_OPTIONS = Array.from(new Set([
    'Flame', 'Zap', 'Activity', 'Heart', 'Pill', 'Droplet', 'Cloud',
    'BookOpen', 'Book', 'Bookmark', 'FileText', 'Layers', 'Grid',
    'Palette', 'Pen', 'PenTool', 'Music', 'Music2', 'Music3', 'Music4',
    'Briefcase', 'Code', 'Code2', 'Cpu', 'Database', 'HardDrive', 'Monitor',
    'Dumbbell', 'Bike', 'Target', 'Trophy', 'Award', 'Medal',
    'Leaf', 'Flower', 'Clover', 'Sprout', 'Tree', 'CloudRain', 'Sun',
    'Plane', 'Map', 'Navigation', 'Compass', 'Anchor', 'Waves',
    'MessageSquare', 'MessageCircle', 'Send', 'Phone', 'Share', 'Share2',
    'Clock', 'Watch', 'Timer', 'Hourglass', 'Calendar', 'CalendarDays', 'Moon',
    'Star', 'Smile', 'Eye', 'Lightbulb', 'Shield', 'Lock', 'Unlock', 'Key',
    'Wifi', 'Settings', 'Bell', 'BellOff', 'Volume2', 'VolumeX', 'Mic', 'MicOff',
    'Camera', 'Video', 'Play', 'Pause', 'SkipBack', 'SkipForward',
    'ThumbsUp', 'ThumbsDown', 'Hand', 'CheckCircle', 'AlertCircle', 'HelpCircle',
    'Info', 'Package', 'Gift', 'Inbox', 'Layout', 'LayoutGrid', 'Columns',
    'Brain', 'Gauge', 'Sliders', 'Gamepad2', 'Coffee', 'Pencil', 'GraduationCap'
  ]));

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

<svelte:window on:keydown={onKey} />

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="modal-backdrop" on:click={onBackdrop} transition:fade={{ duration: 150 }}>
    <div class="modal-panel" transition:slide={{ duration: 200 }}>

      <!-- Header -->
      <div class="modal-header">
        <span class="modal-title mono">{isEdit ? 'EDITAR RACHA' : 'NUEVA RACHA'}</span>
        <button class="close-btn" on:click={close}><X size={14} /></button>
      </div>

      <div class="modal-body">
        <!-- Preview Card -->
        <div
          class="preview-card"
          class:theme-gradient={theme === 'gradient'}
          class:theme-glow={theme === 'glow'}
          class:theme-minimal={theme === 'minimal'}
          class:theme-lcd={theme === 'lcd'}
          class:theme-neon={theme === 'neon'}
          class:theme-glass={theme === 'glass'}
          class:theme-sketch={theme === 'sketch'}
          class:theme-solid={theme === 'solid' || !theme}
          style={previewStyle}
          use:liquidGlass={{ enabled: theme === 'glass' }}
        >
          <div class="preview-icon">
            {#if useIcon && icon}
              <StreakIcon name={icon} size={18} color={color} />
            {:else}
              <span class="preview-emoji">{emoji || '🔥'}</span>
            {/if}
          </div>
          <div class="preview-info">
            <span class="preview-name">{name || 'Nombre...'}</span>
            <span class="preview-meta mono">{previewFreqLabel()}</span>
          </div>
          <div class="preview-count">
            <span class="preview-num mono">{offset || 0}</span>
          </div>
        </div>

        <!-- Section tabs -->
        <div class="section-tabs">
          <button class="sec-tab" class:active={activeSection === 'basics'} on:click={() => activeSection = 'basics'}>Básico</button>
          <button class="sec-tab" class:active={activeSection === 'appearance'} on:click={() => activeSection = 'appearance'}>Apariencia</button>
          <button class="sec-tab" class:active={activeSection === 'advanced'} on:click={() => activeSection = 'advanced'}>Avanzado</button>
        </div>

        <!-- BASICS -->
        {#if activeSection === 'basics'}
          <div class="section-content" in:fade={{ duration: 180 }} out:fade={{ duration: 80 }}>
            <div class="field">
              <label>Nombre</label>
              <input bind:value={name} placeholder="Ej: Meditación, Lectura, Ejercicio..." autofocus />
            </div>

            <div class="field">
              <label>Descripción <span class="optional">(opcional)</span></label>
              <input bind:value={description} placeholder="Mi motivación, mi meta..." />
            </div>

            <div class="field">
              <label>Frecuencia</label>
              <div class="freq-row">
                <button class="freq-btn" class:selected={frequency === 'daily'} on:click={() => { frequency = 'daily'; frequencyDays = 1; }}>
                  Diaria
                </button>
                <button class="freq-btn" class:selected={frequency === 'every_n'} on:click={() => { frequency = 'every_n'; frequencyDays = 2; }}>
                  Cada N días
                </button>
              </div>
              {#if frequency === 'every_n'}
                <div class="freq-n-row" transition:slide={{ duration: 150 }}>
                  <span class="freq-label">Cada</span>
                  <input type="number" class="freq-input" bind:value={frequencyDays} min="2" max="30" />
                  <span class="freq-label">días</span>
                </div>
              {/if}
            </div>
          </div>
        {/if}

        <!-- APPEARANCE -->
        {#if activeSection === 'appearance'}
          <div class="section-content" in:fade={{ duration: 180 }} out:fade={{ duration: 80 }}>
            <div class="field">
              <label>Icono</label>
              <div class="icon-toggle-row">
                <button class="icon-type-btn" class:selected={!useIcon} on:click={() => useIcon = false}>Emoji</button>
                <button class="icon-type-btn" class:selected={useIcon} on:click={() => { useIcon = true; if (!icon) icon = 'Flame'; }}>Icono</button>
              </div>
            </div>

            {#if !useIcon}
              <div class="emoji-grid">
                {#each EMOJIS as e}
                  <button class="emoji-btn" class:selected={emoji === e} on:click={() => emoji = e}>{e}</button>
                {/each}
              </div>
            {:else}
              <div class="icon-grid">
                {#each ICON_OPTIONS as ic}
                  <button class="lucide-btn" class:selected={icon === ic} on:click={() => icon = ic} title={ic}>
                    <StreakIcon name={ic} size={16} color={color} />
                  </button>
                {/each}
              </div>
            {/if}

            <div class="field">
              <label>Color</label>
              <div class="color-presets">
                {#each COLOR_PRESETS as c}
                  <button
                    class="color-dot"
                    class:selected={color === c.hex}
                    style="background: {c.hex};"
                    on:click={() => color = c.hex}
                    title={c.name}
                  ></button>
                {/each}
                <div class="color-custom">
                  <input type="color" bind:value={color} class="color-picker" />
                </div>
              </div>
            </div>

            <div class="field">
              <label>Tema visual</label>
              <div class="theme-row">
                {#each THEMES as t}
                  <button class="theme-btn" class:selected={theme === t.id} on:click={() => theme = t.id}>
                    {t.label}
                  </button>
                {/each}
              </div>
            </div>
          </div>
        {/if}

        <!-- ADVANCED -->
        {#if activeSection === 'advanced'}
          <div class="section-content" in:fade={{ duration: 180 }} out:fade={{ duration: 80 }}>
            <div class="field-row">
              <div class="field half">
                <label><Calendar size={11} /> Fecha de inicio</label>
                <input type="date" bind:value={startDate} disabled={isEdit} />
              </div>
              <div class="field half">
                <label><Target size={11} /> Fecha objetivo <span class="optional">(op.)</span></label>
                <input type="date" bind:value={targetDate} />
              </div>
            </div>

            <div class="field-row">
              <div class="field half">
                <label><Clock size={11} /> Días desde inicio</label>
                <input type="number" bind:value={offset} min="0" disabled={isEdit} placeholder="Calculado automáticamente" />
                <span class="field-hint">{isEdit ? 'Este valor no se puede modificar una vez creada la racha' : 'Se calcula automáticamente desde la fecha de inicio'}</span>
              </div>
              <div class="field half">
                <label><Snowflake size={11} /> Freezes (escudos)</label>
                <input type="number" bind:value={freezeCount} min="0" max="30" />
                <span class="field-hint">Protegen tu racha si fallas un día.</span>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div 
        class="modal-footer" 
        class:theme-sketch={theme === 'sketch'}
        class:theme-glow={theme === 'glow'}
        class:theme-gradient={theme === 'gradient'}
        class:theme-neon={theme === 'neon'}
      >
        {#if isEdit}
          <button
            class="btn-archive"
            on:click={archive}
            title={editStreak?.is_archived ? 'Desarchivar racha' : 'Archivar racha'}
          >
            <Archive size={14} />
            {editStreak?.is_archived ? 'Desarchivar' : 'Archivar'}
          </button>
        {/if}
        <button class="btn-cancel" on:click={close}>Cancelar</button>
        <button class="btn-save" disabled={!canSave} on:click={save} style="--btn-color: {color};">
          {isEdit ? 'Actualizar' : 'Crear Racha'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed; inset: 0; z-index: 200;
    background: rgba(0,0,0,0.75); backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
  }

  .modal-panel {
    width: 520px;
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
    overflow: visible;
    padding: 20px;
    display: flex; flex-direction: column; gap: 16px;
  }

  /* Preview card */
  .preview-card {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
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
  .preview-card.theme-lcd .preview-num {
    font-family: var(--font-mono);
    color: color-mix(in srgb, var(--theme-ac) 20%, black) !important;
    text-shadow: none;
    font-weight: 800;
  }
  .preview-card.theme-lcd .preview-name {
    color: color-mix(in srgb, var(--theme-ac) 20%, black) !important;
    opacity: 0.9;
    font-weight: 700;
  }
  .preview-card.theme-lcd .preview-meta {
    color: color-mix(in srgb, var(--theme-ac) 20%, black) !important;
    opacity: 0.7;
    font-weight: 600;
  }
  .preview-card.theme-lcd .preview-icon,
  .preview-card.theme-lcd .preview-emoji {
    filter: grayscale(1) brightness(0) opacity(0.8);
  }

  .preview-card.theme-neon {
    background: #000;
    border: 1px solid var(--theme-ac);
    box-shadow: 0 0 10px color-mix(in srgb, var(--theme-ac) 25%, transparent);
  }
  .preview-card.theme-neon .preview-name,
  .preview-card.theme-neon .preview-num {
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
    background: transparent;
    border: 1px dashed var(--theme-ac);
    border-radius: 2px;
  }

  .preview-icon {
    flex-shrink: 0;
    width: 28px;
    text-align: center;
    font-size: 20px;
  }

  .preview-emoji { font-size: 20px; }
  .preview-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .preview-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .preview-meta {
    font-size: 9px;
    color: var(--text-disabled);
  }

  .preview-count {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .preview-num {
    font-size: 18px;
    font-weight: 700;
    line-height: 1;
    color: var(--theme-ac, var(--text-primary));
  }

  /* Section tabs */
  .section-tabs {
    display: flex; gap: 2px; background: var(--elevated);
    border-radius: 6px; padding: 2px;
  }

  .sec-tab {
    flex: 1; padding: 6px 0; font-size: 11px; font-family: var(--font-mono);
    background: none; border: none; color: var(--text-muted);
    cursor: pointer; border-radius: 4px; transition: all 0.15s;
    letter-spacing: 0.03em;
  }
  .sec-tab:hover { color: var(--text-secondary); }
  .sec-tab.active { background: var(--surface); color: var(--text-primary); }

  .section-content {
    display: flex;
    flex-direction: column;
    gap: 14px;
    overflow: visible;
    padding-right: 4px;
    animation: none;
  }

  /* Fields */
  .field { display: flex; flex-direction: column; gap: 5px; }
  .field label {
    font-size: 11px; color: var(--text-muted); text-transform: uppercase;
    letter-spacing: 0.05em; font-family: var(--font-mono);
    display: flex; align-items: center; gap: 4px;
  }
  .optional { font-size: 9px; color: var(--text-disabled); text-transform: lowercase; }

  .field input, .field select {
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
  }

  .field-row { display: flex; gap: 12px; }
  .field.half { flex: 1; }

  /* Category grid */
  .category-grid {
    display: flex; flex-wrap: wrap; gap: 6px;
  }

  .cat-chip {
    display: flex; align-items: center; gap: 5px;
    padding: 5px 10px; font-size: 11px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted);
    cursor: pointer; transition: all 0.15s;
  }
  .cat-chip:hover { border-color: var(--text-muted); color: var(--text-secondary); }
  .cat-chip.selected { border-color: var(--text-primary); color: var(--text-primary); background: var(--elevated); }

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
    display: flex; align-items: center; gap: 8px; margin-top: 6px;
  }
  .freq-label { font-size: 12px; color: var(--text-muted); }
  .freq-input {
    width: 60px; text-align: center; padding: 5px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-primary); font-family: var(--font-mono);
    font-size: 13px; outline: none;
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

  /* Emoji grid */
  .emoji-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
    min-height: 220px;
    max-height: 300px;
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

  /* Icon grid */
  .icon-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
    min-height: 220px;
    max-height: 300px;
    overflow-y: auto;
    padding: 4px;
    align-content: start;
  }
  .lucide-btn {
    width: 36px; height: 36px; background: none;
    border: 1px solid transparent; cursor: pointer;
    border-radius: 4px; display: flex; align-items: center;
    justify-content: center; color: var(--text-muted);
    transition: all 0.15s;
  }
  .lucide-btn:hover { background: var(--elevated); color: var(--text-secondary); }
  .lucide-btn.selected { border-color: var(--text-primary); color: var(--text-primary); background: var(--elevated); }

  /* Color presets */
  .color-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    justify-content: center;
    width: 100%;
  }
  .color-dot {
    width: 24px; height: 24px; border-radius: 50%;
    border: 2px solid transparent; cursor: pointer;
    transition: all 0.15s; flex-shrink: 0;
  }
  .color-dot:hover { transform: scale(1.15); }
  .color-dot.selected { border-color: var(--text-primary); box-shadow: 0 0 0 2px var(--bg), 0 0 0 4px currentColor; }

  .color-custom { display: flex; align-items: center; }
  .color-picker {
    width: 24px; height: 24px; border: none; padding: 0;
    background: none; cursor: pointer; border-radius: 4px;
  }

  /* Theme selector */
  .theme-row { display: flex; gap: 6px; }
  .theme-btn {
    flex: 1; padding: 6px; font-size: 11px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted);
    cursor: pointer; transition: all 0.15s; font-family: var(--font-mono);
  }
  .theme-btn:hover { border-color: var(--text-muted); }
  .theme-btn.selected { border-color: var(--text-primary); color: var(--text-primary); }

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
  }
</style>
