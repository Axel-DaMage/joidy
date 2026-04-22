<script lang="ts">
  import { onMount } from 'svelte';
  import { fly, fade, slide, scale } from 'svelte/transition';
  import { flip } from 'svelte/animate';
  import { Plus, Check, X, Flame, Settings, Snowflake, Search, ChevronRight } from 'lucide-svelte';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import StreakCreateModal from '$lib/components/StreakCreateModal.svelte';
  import StreakHeatmap from '$lib/components/StreakHeatmap.svelte';
  import StreakStatsPanel from '$lib/components/StreakStatsPanel.svelte';
  import { api, type PersonalStreak, type StreakStats } from '$lib/api';

  let streaks: PersonalStreak[] = [];
  let stats: StreakStats | null = null;
  let loading = true;
  let error = '';
  let mounted = false;

  // ── Selection ─────────────────────────────────────────────────────────────
  let selectedId: number | null = null;
  $: selected = streaks.find(s => s.id === selectedId) || null;

  // ── Filter / Search ───────────────────────────────────────────────────────
  let searchQuery = '';

  // ── Delete confirmation ───────────────────────────────────────────────────
  let deleteConfirm: number | null = null;
  let deleteConfirmName: string = '';

  $: filteredStreaks = streaks.filter(s => {
    if (s.is_archived) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
    }
    return true;
  });

  $: pendingCount = filteredStreaks.filter(s => !s.today_checked && !s.is_archived).length;
  $: doneCount = filteredStreaks.filter(s => s.today_checked).length;

  // ── Modal ─────────────────────────────────────────────────────────────────
  let showModal = false;
  let editTarget: PersonalStreak | null = null;

  // ── Check-in state ────────────────────────────────────────────────────────
  let busy = new Set<number>();
  let checkinNote = '';
  let showCheckinExtra = false;

  // ── Load ──────────────────────────────────────────────────────────────────
  onMount(async () => {
    mounted = true;
    try {
      const [s, st] = await Promise.all([
        api.personalStreaks.list(),
        api.personalStreaks.stats(),
      ]);
      streaks = s;
      stats = st;
    } catch (e) {
      error = 'Error de conexión con el sistema de rachas.';
      console.error('[streaks]', e);
    } finally {
      loading = false;
    }
  });

  // ── Actions ───────────────────────────────────────────────────────────────
  async function handleSave(e: CustomEvent) {
    const data = e.detail;
    const targetId = editTarget?.id ?? null;
    // Close modal immediately
    showModal = false;
    editTarget = null;
    try {
      if (targetId !== null) {
        const updated = await api.personalStreaks.update(targetId, data);
        streaks = streaks.map(s => s.id === targetId ? updated : s);
      } else {
        const created = await api.personalStreaks.create(data);
        streaks = [...streaks, created];
        // Force reactivity
        streaks = streaks;
        selectedId = created.id;
      }
      stats = await api.personalStreaks.stats();
    } catch (e) {
      console.error('[streaks] save error:', e);
    }
  }

  async function checkin(id: number) {
    if (busy.has(id)) return;
    busy = new Set(busy).add(id);
    try {
      const updated = await api.personalStreaks.checkin(id, {
        note: checkinNote || undefined,
      });
      streaks = streaks.map(s => s.id === id ? updated : s);
      checkinNote = '';
      showCheckinExtra = false;
      stats = await api.personalStreaks.stats();
    } finally {
      busy.delete(id); busy = new Set(busy);
    }
  }

  async function undo(id: number) {
    if (busy.has(id)) return;
    busy = new Set(busy).add(id);
    try {
      const updated = await api.personalStreaks.undo(id);
      streaks = streaks.map(s => s.id === id ? updated : s);
      stats = await api.personalStreaks.stats();
    } finally {
      busy.delete(id); busy = new Set(busy);
    }
  }

  async function useFreeze(id: number) {
    if (busy.has(id)) return;
    busy = new Set(busy).add(id);
    try {
      const updated = await api.personalStreaks.freeze(id);
      streaks = streaks.map(s => s.id === id ? updated : s);
    } catch (e: any) {
      console.error('[streaks] freeze error:', e);
    } finally {
      busy.delete(id); busy = new Set(busy);
    }
  }

  let deleteTimeoutId: NodeJS.Timeout | null = null;

  async function deleteStreak(id: number) {
    if (deleteConfirm !== id) {
      const streak = streaks.find(s => s.id === id);
      deleteConfirm = id;
      deleteConfirmName = streak?.name || 'Sin nombre';
      return;
    }
    if (deleteTimeoutId) clearTimeout(deleteTimeoutId);
    try {
      await api.personalStreaks.delete(id);
      streaks = streaks.filter(s => s.id !== id);
      if (selectedId === id) selectedId = null;
      stats = await api.personalStreaks.stats();
      deleteConfirm = null;
      deleteConfirmName = '';
    } catch (e) {
      console.error('[streaks] delete error:', e);
      deleteConfirm = null;
      deleteConfirmName = '';
    }
  }

  function cancelDelete() {
    deleteConfirm = null;
    deleteConfirmName = '';
  }

  function openCreate() {
    editTarget = null;
    showModal = true;
  }

  function openEdit(s: PersonalStreak) {
    editTarget = s;
    showModal = true;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function streakLabel(n: number): string {
    if (n === 0) return '0';
    return String(n);
  }

  function freqLabel(s: PersonalStreak): string {
    if (s.frequency === 'every_n' && s.frequency_days > 1) return `cada ${s.frequency_days}d`;
    return 'diaria';
  }

  function cardThemeStyle(s: PersonalStreak): string {
    const c = s.color || 'var(--xp)';
    const t = s.theme || 'solid';
    if (t === 'gradient') return `box-shadow: inset 0 0 0 1px color-mix(in srgb, ${c} 30%, transparent); border-color: color-mix(in srgb, ${c} 30%, transparent);`;
    if (t === 'glow') return `box-shadow: 0 0 10px color-mix(in srgb, ${c} 10%, transparent), inset 0 0 0 1px color-mix(in srgb, ${c} 14%, transparent); border-color: color-mix(in srgb, ${c} 20%, transparent); background: var(--surface);`;
    if (t === 'minimal') return `background: var(--bg); border: 1px solid color-mix(in srgb, ${c} 12%, var(--border)); opacity: 0.82;`;
    return ``;
  }

  function detailThemeStyle(s: PersonalStreak): string {
    const c = s.color || 'var(--xp)';
    const t = s.theme || 'solid';
    if (t === 'gradient') return `box-shadow: inset 0 0 0 1px color-mix(in srgb, ${c} 26%, transparent);`;
    if (t === 'glow') return `box-shadow: 0 0 16px color-mix(in srgb, ${c} 12%, transparent);`;
    if (t === 'minimal') return `opacity: 0.9;`;
    return '';
  }

  // Completion detection
  function isStreakCompleted(s: PersonalStreak): boolean {
    if (!s.target_date) return false;
    const today = new Date();
    const targetDate = new Date(s.target_date);
    return today >= targetDate;
  }

  function getDaysForCompletion(s: PersonalStreak): string {
    if (!s.target_date || !s.start_date) return '';
    const start = new Date(s.start_date);
    const target = new Date(s.target_date);
    const diffTime = Math.abs(target.getTime() - start.getTime());
    const totalDays = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1;
    return `${s.current_streak}/${totalDays}`;
  }
</script>

<div class="streaks-page">
  {#if mounted}
    <div class="streaks-layout" transition:fade>
      <!-- ═══ LEFT PANEL: LIST ═══ -->
      <div class="list-panel">
        <!-- Header -->
        <div class="list-header">
          <div class="list-header-top">
            <div>
              <h1 class="list-title">Rachas</h1>
              <span class="list-sub mono">
                {#if loading}cargando...
                {:else}{doneCount}/{filteredStreaks.length} hoy
                {/if}
              </span>
            </div>
            <button class="new-btn" on:click={openCreate}>
              <Plus size={13} />
            </button>
          </div>

          <!-- Search -->
          <div class="search-row">
            <Search size={12} />
            <input
              class="search-input"
              bind:value={searchQuery}
              placeholder="Buscar racha..."
            />
          </div>
        </div>

        <!-- Streak list -->
        <div class="list-body">
          {#if error}
            <div class="error-msg">{error}</div>
          {:else if loading}
            <div class="empty-state mono">Cargando...</div>
          {:else if filteredStreaks.length === 0}
            <div class="empty-state">
              <Flame size={24} style="opacity:.25; margin-bottom:8px;" />
              <p>No hay rachas. ¡Crea una para comenzar!</p>
              <button class="link-btn" on:click={openCreate}>Crear una nueva</button>
            </div>
          {:else}
            {#each filteredStreaks as streak (streak.id)}
              <div
                class="streak-item"
                class:theme-gradient={streak.theme === 'gradient'}
                class:theme-glow={streak.theme === 'glow'}
                class:theme-minimal={streak.theme === 'minimal'}
                class:selected={selectedId === streak.id}
                class:checked={streak.today_checked}
                class:archived={streak.is_archived}
                class:completed={isStreakCompleted(streak)}
                style="--theme-ac: {streak.color || 'var(--xp)'};"
                on:click={() => selectedId = streak.id}
                on:keydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectedId = streak.id;
                  }
                }}
                role="button"
                tabindex="0"
                animate:flip={{ duration: 200 }}
              >
                <div class="item-icon">
                  {#if streak.icon && streak.icon.length > 0}
                    <StreakIcon name={streak.icon} size={18} color={streak.color || undefined} />
                  {:else}
                    <span class="item-emoji">{streak.emoji || '🔥'}</span>
                  {/if}
                </div>
                <div class="item-info">
                  <span class="item-name">{streak.name}</span>
                  <span class="item-meta mono">
                    {#if isStreakCompleted(streak)}
                      Finalizado {getDaysForCompletion(streak)} días
                    {:else}
                      {freqLabel(streak)}
                      {#if streak.target_date}
                        · {streak.days_remaining}d left
                      {/if}
                    {/if}
                  </span>
                </div>
                <div class="item-count" style="color: {streak.color || 'var(--xp)'};">
                  <span class="item-num mono">{streakLabel(streak.current_streak)}</span>
                  {#if streak.today_checked}
                    <Check size={10} style="color: {streak.color || 'var(--xp)'};" />
                  {/if}
                </div>
                <div class="item-actions">
                  <button
                    class="item-action-btn"
                    on:click|stopPropagation={() => openEdit(streak)}
                    title="Editar racha"
                  >
                    <Settings size={12} />
                  </button>
                  <button
                    class="item-action-btn danger"
                    on:click|stopPropagation={() => deleteStreak(streak.id)}
                    title="Eliminar racha"
                  >
                    <X size={12} />
                  </button>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>

      <!-- ═══ RIGHT PANEL: DETAIL ═══ -->
      <div class="detail-panel">
        {#if selected}
          <div
            class="detail-content"
            class:theme-gradient={selected.theme === 'gradient'}
            class:theme-glow={selected.theme === 'glow'}
            class:theme-minimal={selected.theme === 'minimal'}
            class:completed={isStreakCompleted(selected)}
            style="--theme-ac: {selected.color || 'var(--xp)'};"
            transition:fade={{ duration: 150 }}
          >
            <div class="top-metrics">
              <!-- Streak counter -->
              <div class="counter-section">
                <button
                  class="counter-ring"
                  style="--ring-color: {isStreakCompleted(selected) ? '#10b981' : (selected.color || 'var(--xp)')};"
                  on:click={() => !selected.is_archived && !selected.today_checked && !isStreakCompleted(selected) && checkin(selected.id)}
                  disabled={selected.is_archived || selected.today_checked || busy.has(selected.id) || isStreakCompleted(selected)}
                  title={isStreakCompleted(selected) ? 'Racha completada' : (selected.today_checked ? 'Ya hiciste check-in hoy' : 'Hacer check-in')}
                >
                  {#if isStreakCompleted(selected)}
                    <span class="counter-num mono" style="color: #10b981;">✓</span>
                    <span class="counter-label mono">FINALIZADO</span>
                  {:else}
                    <span class="counter-num mono">{selected.current_streak}</span>
                    <span class="counter-label mono">DÍAS</span>
                  {/if}
                </button>
              </div>

              <!-- Vertical stats panel -->
              <div class="detail-stats">
                <div class="dstat-row">
                  <span class="dstat-lbl">Actual</span>
                  <span class="dstat-val mono">{selected.current_streak}</span>
                </div>
                <div class="dstat-row">
                  <span class="dstat-lbl">Mejor</span>
                  <span class="dstat-val mono">{selected.longest_streak}</span>
                </div>
                <div class="dstat-row">
                  <span class="dstat-lbl">Check-ins</span>
                  <span class="dstat-val mono">{selected.total_checkins}</span>
                </div>
              </div>
            </div>

            <!-- Activity calendar -->
            <div class="heatmap-section">
              <StreakHeatmap
                history={selected.history}
                color={selected.color || '#c8a96e'}
                startDate={selected.start_date}
              />
            </div>

            <!-- Footer: dates + actions, sticky at bottom -->
            <div class="detail-footer">
              <div class="dates-info">
                {#if selected.start_date}
                  <div class="date-item">
                    <span class="date-label">Inicio</span>
                    <span class="date-val mono">{new Date(selected.start_date).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                  </div>
                {/if}
                {#if selected.target_date}
                  <div class="date-item">
                    <span class="date-label">Objetivo</span>
                    <span class="date-val mono">{new Date(selected.target_date).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                  </div>
                {/if}
                <div class="date-item">
                  <span class="date-label">Creada</span>
                  <span class="date-val mono">{new Date(selected.created_at).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                </div>
              </div>


            </div>
          </div>
        {:else}
          <!-- No selection state -->
          <div class="no-selection">
            {#if stats}
              <StreakStatsPanel {stats} />
            {/if}
            <div class="no-sel-hint">
              <ChevronRight size={14} />
              <span>Selecciona una racha para ver detalles</span>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- Delete confirmation modal -->
{#if deleteConfirm !== null}
  <div class="modal-backdrop" transition:fade={{ duration: 150 }}>
    <div class="delete-modal" transition:scale={{ duration: 200 }}>
      <div class="delete-modal-content">
        <div class="delete-modal-icon">
          <X size={32} />
        </div>
        <h2 class="delete-modal-title">Eliminar racha</h2>
        <p class="delete-modal-text">
          ¿Estás seguro de que quieres eliminar <strong>{deleteConfirmName}</strong>?
        </p>
        <p class="delete-modal-warning">Esta acción no se puede deshacer.</p>
      </div>
      <div class="delete-modal-buttons">
        <button class="btn-cancel" on:click={cancelDelete}>Cancelar</button>
        <button class="btn-danger" on:click={() => deleteStreak(deleteConfirm)}>Eliminar</button>
      </div>
    </div>
  </div>
{/if}

<StreakCreateModal
  bind:open={showModal}
  editStreak={editTarget}
  on:close={() => { showModal = false; editTarget = null; }}
  on:save={handleSave}
/>

<style>
  .streaks-page {
    height: 100%; width: 100%; background: var(--bg);
    overflow: hidden;
  }

  .streaks-layout {
    display: grid;
    grid-template-columns: 340px 1fr;
    height: 100%;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     LEFT PANEL
     ═══════════════════════════════════════════════════════════════════════ */
  .list-panel {
    display: flex; flex-direction: column;
    border-right: 1px solid var(--border);
    height: 100%;
  }

  .list-header {
    padding: 20px 16px 12px;
    display: flex; flex-direction: column; gap: 10px;
    border-bottom: 1px solid var(--border-light);
    flex-shrink: 0;
  }

  .list-header-top {
    display: flex; align-items: flex-start; justify-content: space-between;
  }

  .list-title {
    font-size: 20px; font-weight: 700; color: var(--text-primary);
    letter-spacing: -0.02em;
  }
  .list-sub { font-size: 11px; color: var(--text-muted); }

  .new-btn {
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    background: var(--text-primary); color: var(--bg);
    border: none; border-radius: 8px;
    cursor: pointer; transition: all 0.15s;
  }
  .new-btn:hover { opacity: 0.85; transform: scale(1.05); }

  /* Search */
  .search-row {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text-muted);
    transition: border-color 0.15s;
  }
  .search-row:focus-within { border-color: var(--text-muted); }

  .search-input {
    flex: 1; background: none; border: none; outline: none;
    color: var(--text-primary); font-size: 12px;
  }

  /* Category tabs */
  .cat-tabs {
    display: flex; gap: 2px; overflow: hidden;
  }

  .cat-tab {
    display: flex; align-items: center; gap: 4px;
    padding: 4px 8px; font-size: 10px;
    background: none; border: 1px solid transparent;
    border-radius: 4px; color: var(--text-disabled);
    cursor: pointer; transition: all 0.15s;
    white-space: nowrap; flex-shrink: 0;
  }
  .cat-tab:hover { color: var(--text-muted); }
  .cat-tab.active { border-color: var(--border); color: var(--text-primary); background: var(--elevated); }
  .cat-tab-label { display: none; }
  .cat-tab.active .cat-tab-label { display: inline; }

  .archive-toggle {
    display: flex; align-items: center; gap: 5px;
    padding: 3px 8px; font-size: 9px;
    background: none; border: none; color: var(--text-disabled);
    cursor: pointer; transition: color 0.15s;
    font-family: var(--font-mono); letter-spacing: 0.03em;
    align-self: flex-start;
  }
  .archive-toggle:hover { color: var(--text-muted); }
  .archive-toggle.active { color: var(--text-secondary); }

  /* List body */
  .list-body {
    flex: 1; overflow: hidden; padding: 8px;
    display: flex; flex-direction: column; gap: 4px;
  }

  .streak-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; cursor: pointer;
    transition: all 0.15s; text-align: left; width: 100%;
    position: relative;
    overflow: hidden;
    isolation: isolate;
  }

  .streak-item > * {
    position: relative;
    z-index: 1;
  }

  .streak-item::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s ease;
    z-index: 0;
  }

  .streak-item.theme-gradient {
    border-color: color-mix(in srgb, var(--theme-ac) 30%, var(--border));
  }

  .streak-item.theme-gradient::before {
    opacity: 1;
    background:
      linear-gradient(
        125deg,
        color-mix(in srgb, var(--theme-ac) 16%, transparent) 0%,
        transparent 45%,
        color-mix(in srgb, var(--theme-ac) 10%, transparent) 100%
      );
  }

  .streak-item.theme-glow {
    border-color: color-mix(in srgb, var(--theme-ac) 22%, var(--border));
    box-shadow:
      0 0 14px color-mix(in srgb, var(--theme-ac) 12%, transparent),
      inset 0 0 0 1px color-mix(in srgb, var(--theme-ac) 14%, transparent);
  }

  .streak-item.theme-glow::before {
    opacity: 1;
    background:
      radial-gradient(
        120% 90% at 50% 50%,
        color-mix(in srgb, var(--theme-ac) 12%, transparent) 0%,
        transparent 70%
      );
  }

  .streak-item.theme-minimal {
    background: var(--bg);
    border-color: color-mix(in srgb, var(--theme-ac) 12%, var(--border));
    opacity: 0.88;
  }

  .streak-item:hover { background: var(--elevated); }
  .streak-item.selected { background: var(--elevated); border-color: var(--text-muted); }
  .streak-item.completed {
    border-color: #10b981;
    background: rgba(16, 185, 129, 0.05);
  }
  .streak-item.completed .item-count { color: #10b981 !important; }

  .streak-item.archived { opacity: 0.5; }

  .streak-item.theme-gradient:hover,
  .streak-item.theme-glow:hover,
  .streak-item.theme-minimal:hover {
    background: var(--surface);
  }

  .streak-item.theme-gradient.selected,
  .streak-item.theme-glow.selected {
    border-color: color-mix(in srgb, var(--theme-ac) 40%, var(--text-muted));
    background: var(--surface);
  }

  .streak-item.theme-minimal.selected {
    border-color: color-mix(in srgb, var(--theme-ac) 20%, var(--text-muted));
    background: var(--bg);
  }

  .streak-item.theme-minimal,
  .detail-content.theme-minimal {
    filter: saturate(0.9) brightness(0.95);
  }

  .detail-content.completed {
    --theme-ac: #10b981;
  }

  .item-icon { font-size: 20px; flex-shrink: 0; width: 28px; text-align: center; }
  .item-emoji { font-size: 20px; }

  .item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .item-name { font-size: 13px; font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .item-meta { font-size: 9px; color: var(--text-disabled); }

  .item-count {
    display: flex; align-items: center; gap: 4px; flex-shrink: 0;
    padding-right: 26px;
  }
  .item-num { font-size: 18px; font-weight: 700; line-height: 1; }

  .item-actions {
    display: flex; flex-direction: column; gap: 3px;
    position: absolute; top: 6px; right: 6px;
    opacity: 0; pointer-events: none;
    transition: opacity 0.15s;
  }

  .streak-item:hover .item-actions {
    opacity: 1;
    pointer-events: auto;
  }

  .item-action-btn {
    width: 20px; height: 20px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--border); border-radius: 5px;
    background: var(--surface); color: var(--text-muted);
    padding: 0; cursor: pointer;
    transition: all 0.15s;
  }

  .item-action-btn:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .item-action-btn.danger:hover {
    border-color: var(--error);
    color: var(--error);
  }

  .item-action-btn.confirm {
    border-color: var(--error);
    color: var(--error);
    background: color-mix(in srgb, var(--error) 10%, var(--surface));
  }

  .error-msg { color: var(--error); padding: 15px; font-size: 13px; }
  .empty-state {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    color: var(--text-muted); text-align: center;
    padding: 40px 20px; gap: 4px; font-size: 12px;
  }
  .link-btn {
    background: none; border: none; color: var(--xp);
    font-size: 12px; cursor: pointer; margin-top: 8px;
    text-decoration: underline;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     RIGHT PANEL
     ═══════════════════════════════════════════════════════════════════════ */
  .detail-panel {
    height: 100%; overflow: hidden;
  }

  .detail-content {
    padding: 0 20px 2px;
    display: flex; flex-direction: column; gap: 2px;
    height: 100%;
    overflow: hidden;
    position: relative;
    isolation: isolate;
  }

  /* Top metrics */
  .top-metrics {
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
    margin-top: -10px;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    aspect-ratio: 2 / 0.72;
    gap: 0;
  }

  /* Counter */
  .counter-section {
    display: flex; align-items: center; justify-content: center;
    height: 100%;
  }

  .counter-ring {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center;
    width: 102px; height: 102px;
    border-radius: 50%;
    border: 2px solid var(--ring-color);
    box-shadow: 0 0 30px color-mix(in srgb, var(--ring-color) 15%, transparent),
                inset 0 0 20px color-mix(in srgb, var(--ring-color) 5%, transparent);
    background: var(--surface);
    cursor: pointer;
    padding: 0;
    appearance: none;
    -webkit-appearance: none;
  }
  .counter-ring:disabled { cursor: default; opacity: 0.95; }
  .counter-ring:focus-visible { outline: 1px solid var(--ring-color); outline-offset: 3px; }

  .counter-num {
    font-size: 40px; font-weight: 700;
    color: var(--text-primary); line-height: 1;
  }
  .counter-label {
    font-size: 9px; color: var(--text-muted);
    letter-spacing: 0.15em; margin-top: 2px;
  }

  /* Stats panel */
  .detail-stats {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: center;
    height: 100%;
    gap: 0;
    padding: 0 20px;
    background: transparent;
  }

  .dstat-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding: 0;
    min-height: 28px;
  }
  .dstat-row + .dstat-row { border-top: 1px solid color-mix(in srgb, var(--border) 70%, transparent); }
  .dstat-val { font-size: 17px; font-weight: 600; color: var(--text-primary); line-height: 1; }
  .dstat-lbl { font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

  /* Heatmap section */
  .heatmap-section {
    display: flex; flex-direction: column; gap: 4px;
  }

  .section-label {
    display: flex; align-items: center; gap: 5px;
    font-size: 10px; color: var(--text-muted);
    font-family: var(--font-mono); letter-spacing: 0.05em;
  }

  /* Footer (dates + actions) */
  .detail-footer {
    margin-top: auto;
    display: flex; flex-direction: column; gap: 4px;
    border-top: 1px solid var(--border-light);
    padding-top: 4px;
  }

  /* Dates */
  .dates-info {
    display: flex; gap: 16px; flex-wrap: wrap; justify-content: center;
  }

  .date-item { display: flex; flex-direction: column; gap: 2px; align-items: center; }
  .date-label { font-size: 9px; color: var(--text-disabled); text-transform: uppercase; letter-spacing: 0.05em; }
  .date-val { font-size: 11px; color: var(--text-secondary); }



  /* No selection */
  .no-selection {
    height: 100%;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 40px; gap: 24px;
  }

  .no-sel-hint {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: var(--text-disabled);
    animation: pulse-hint 2s ease-in-out infinite;
  }

  @keyframes pulse-hint {
    0%, 100% { opacity: 0.4; }
    50%      { opacity: 0.8; }
  }

  /* Delete confirmation modal */
  .modal-backdrop {
    position: fixed; inset: 0; z-index: 300;
    background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
  }

  .delete-modal {
    width: 90%; max-width: 400px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    display: flex; flex-direction: column;
  }

  .delete-modal-content {
    padding: 32px 24px 24px;
    display: flex; flex-direction: column; gap: 12px;
    align-items: center; text-align: center;
  }

  .delete-modal-icon {
    color: var(--error); opacity: 0.8; display: flex;
  }

  .delete-modal-title {
    font-size: 18px; font-weight: 600;
    color: var(--text-primary); margin: 0;
  }

  .delete-modal-text {
    font-size: 14px; color: var(--text-secondary);
    margin: 0; line-height: 1.5;
  }

  .delete-modal-text strong {
    color: var(--text-primary); font-weight: 600;
  }

  .delete-modal-warning {
    font-size: 12px; color: var(--text-disabled);
    margin: 0; line-height: 1.4; font-style: italic;
  }

  .delete-modal-buttons {
    display: flex; gap: 8px; padding: 16px 24px;
    border-top: 1px solid var(--border-light);
    background: var(--elevated);
  }

  .btn-cancel {
    flex: 1; padding: 10px 16px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text-secondary);
    font-size: 13px; font-weight: 500;
    cursor: pointer; transition: all 0.15s;
  }
  .btn-cancel:hover { border-color: var(--text-muted); color: var(--text-primary); }

  .btn-danger {
    flex: 1; padding: 10px 16px;
    background: var(--error); border: none;
    border-radius: 6px; color: white;
    font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all 0.15s;
  }
  .btn-danger:hover { opacity: 0.9; }
</style>
