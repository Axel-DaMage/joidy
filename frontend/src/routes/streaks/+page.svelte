<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { scale } from 'svelte/transition';
  import { X, Snowflake, ChevronRight } from 'lucide-svelte';
  import { Shuffle, CheckCheck } from 'lucide-svelte';
  import StreakListItem from '$lib/components/StreakListItem.svelte';
  import StreakStatsPanel from '$lib/components/StreakStatsPanel.svelte';
  import StreakListPanel from '$lib/components/StreakListPanel.svelte';
  import { api, type PersonalStreak, type StreakStats } from '$lib/api';
  import {
    loadUserSettings,
    patchUserSettings,
    getCachedData,
    setCachedData,
  } from '$lib/utils/userSettings';
  import { captureSnapshot, getSnapshot } from '$lib/stores/pageSnapshots';
  import { locale as localeStore } from '$lib/stores/locale';
  import { openShare } from '$lib/stores/shareAchievement';
  import { logger } from '$lib/utils/logger';
  import { Share2 } from 'lucide-svelte';
  import { t } from 'svelte-i18n';

  // Lazy-load heavy components so they are split into separate chunks and
  // only downloaded when actually needed (#347).
  // StreakCreateModal (558 lines) — loaded when the user opens the create/edit modal.
  let StreakCreateModal: typeof import('$lib/components/StreakCreateModal.svelte').default | null =
    null;
  function ensureStreakCreateModal() {
    if (!StreakCreateModal) {
      import('$lib/components/StreakCreateModal.svelte').then(
        (m) => (StreakCreateModal = m.default)
      );
    }
  }
  // StreakHeatmap (561 lines) — loaded when a streak is selected for detail view.
  let StreakHeatmap: typeof import('$lib/components/StreakHeatmap.svelte').default | null = null;
  function ensureStreakHeatmap() {
    if (!StreakHeatmap) {
      import('$lib/components/StreakHeatmap.svelte').then((m) => (StreakHeatmap = m.default));
    }
  }

  let streaks: PersonalStreak[] = [];
  let stats: StreakStats | null = null;
  let loading = true;
  let error = '';
  let mounted = false;

  // Resizable panel synced with notes
  let panelWidth = 260;

  // ── Selection ─────────────────────────────────────────────────────────────
  let selectedId: number | null = null;
  $: selected = streaks.find((s) => s.id === selectedId) || null;

  // ── Filter / Search ───────────────────────────────────────────────────────
  let searchQuery = '';
  let showArchived = false;

  // ── Delete confirmation ───────────────────────────────────────────────────
  let deleteConfirm: number | null = null;
  let deleteConfirmName: string = '';
  let deleteConfirmTheme = 'solid';

  $: visibleStreaks = streaks.filter((s) => (showArchived ? s.is_archived : !s.is_archived));

  $: filteredStreaks = visibleStreaks.filter((s) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
    }
    return true;
  });

  $: pendingCount = filteredStreaks.filter((s) => !s.today_checked && !s.is_archived).length;
  $: doneCount = filteredStreaks.filter((s) => s.today_checked).length;
  $: activeCheckinCandidates = streaks.filter(
    (s) => !s.is_archived && !s.today_checked && !isStreakCompleted(s)
  );

  // ── Modal ─────────────────────────────────────────────────────────────────
  let showModal = false;
  let editTarget: PersonalStreak | null = null;

  // ── Check-in state ────────────────────────────────────────────────────────
  let busy = new Set<number>();
  let checkinNote = '';
  let showCheckinExtra = false;

  function notifyStreaksUpdated() {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('joidy:streaks-updated'));
    }
  }

  // ── Load ──────────────────────────────────────────────────────────────────
  onMount(async () => {
    mounted = true;

    const savedNotesUi = loadUserSettings().notesUi;
    if (savedNotesUi?.panelWidth !== undefined) {
      panelWidth = Number(savedNotesUi.panelWidth);
    }

    const snap = getSnapshot('/streaks');
    if (snap) {
      selectedId = snap.state.selectedId ?? null;
      showArchived = snap.state.showArchived ?? false;
      searchQuery = snap.state.searchQuery ?? '';
      if (selectedId) ensureStreakHeatmap();
    }

    const cached = getCachedData<PersonalStreak[]>('streaks');
    const cachedStats = getCachedData<StreakStats>('stats');
    if (cached) streaks = cached;
    if (cachedStats) stats = cachedStats;
    if (cached) loading = false;

    try {
      const [s, st] = await Promise.all([
        api.personalStreaks.list({ include_archived: true }),
        api.personalStreaks.stats(),
      ]);
      streaks = s;
      stats = st;
      setCachedData('streaks', s);
      setCachedData('stats', st);
    } catch (e) {
      if (!cached || !cachedStats) {
        error = $t('streaks.connectionError');
        logger.error('[streaks]', e);
      }
    } finally {
      loading = false;
      if (selectedId && !streaks.find((s) => s.id === selectedId))
        selectedId = streaks[0]?.id ?? null;
      if (selectedId) ensureStreakHeatmap();
    }

    window.addEventListener('beforeunload', handleBeforeUnload);
  });

  onDestroy(() => window.removeEventListener('beforeunload', handleBeforeUnload));

  function handleBeforeUnload() {
    const scrollEl = document.getElementById('streaks-list');
    captureSnapshot('/streaks', { selectedId, showArchived, searchQuery }, [
      { id: 'streaks-list', scrollTop: scrollEl?.scrollTop ?? 0 },
    ]);
  }

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
        streaks = streaks.map((s) => (s.id === targetId ? updated : s));
      } else {
        const created = await api.personalStreaks.create(data);
        streaks = [...streaks, created];
        // Force reactivity
        streaks = streaks;
        selectedId = created.id;
        ensureStreakHeatmap();
      }
      stats = await api.personalStreaks.stats();
      notifyStreaksUpdated();
    } catch (e) {
      logger.error('[streaks] save error:', e);
    }
  }

  async function archiveStreak(id: number, archived: boolean) {
    try {
      const streak = streaks.find((s) => s.id === id);
      if (!streak) return;
      const updated = await api.personalStreaks.update(id, { is_archived: archived });
      streaks = streaks.map((s) => (s.id === id ? updated : s));
      if (selectedId === id) selectedId = null;
      stats = await api.personalStreaks.stats();
      notifyStreaksUpdated();
      showModal = false;
      editTarget = null;
    } catch (e) {
      logger.error('[streaks] archive error:', e);
    }
  }

  async function checkin(id: number) {
    if (busy.has(id)) return;
    busy = new Set(busy).add(id);
    try {
      const today = new Date();
      const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

      const updated = await api.personalStreaks.checkin(id, {
        note: checkinNote || undefined,
        check_date: localDate,
      });
      streaks = streaks.map((s) => (s.id === id ? updated : s));
      checkinNote = '';
      showCheckinExtra = false;
      stats = await api.personalStreaks.stats();
      notifyStreaksUpdated();
    } finally {
      busy.delete(id);
      busy = new Set(busy);
    }
  }

  async function checkinAllCurrent() {
    if (activeCheckinCandidates.length === 0) return;
    try {
      const today = new Date();
      const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

      const results = await Promise.all(
        activeCheckinCandidates.map((s) =>
          api.personalStreaks.checkin(s.id, { check_date: localDate })
        )
      );
      const updatedById = new Map(results.map((s) => [s.id, s]));
      streaks = streaks.map((s) => updatedById.get(s.id) ?? s);
      stats = await api.personalStreaks.stats();
      notifyStreaksUpdated();
    } catch (e) {
      logger.error('[streaks] bulk checkin error:', e);
    }
  }

  function openRandomStreak() {
    if (filteredStreaks.length === 0) return;
    const next = filteredStreaks[Math.floor(Math.random() * filteredStreaks.length)];
    selectedId = next.id;
    ensureStreakHeatmap();
  }

  function toggleArchivedView() {
    showArchived = !showArchived;
    selectedId = null;
    deleteConfirm = null;
    deleteConfirmName = '';
  }

  async function undo(id: number) {
    if (busy.has(id)) return;
    busy = new Set(busy).add(id);
    try {
      const updated = await api.personalStreaks.undo(id);
      streaks = streaks.map((s) => (s.id === id ? updated : s));
      stats = await api.personalStreaks.stats();
      notifyStreaksUpdated();
    } finally {
      busy.delete(id);
      busy = new Set(busy);
    }
  }

  async function useFreeze(id: number) {
    if (busy.has(id)) return;
    busy = new Set(busy).add(id);
    try {
      const updated = await api.personalStreaks.freeze(id);
      streaks = streaks.map((s) => (s.id === id ? updated : s));
      notifyStreaksUpdated();
    } catch (e: any) {
      logger.error('[streaks] freeze error:', e);
    } finally {
      busy.delete(id);
      busy = new Set(busy);
    }
  }

  let deleteTimeoutId: ReturnType<typeof setTimeout> | null = null;

  async function deleteStreak(id: number) {
    if (deleteConfirm !== id) {
      const streak = streaks.find((s) => s.id === id);
      deleteConfirm = id;
      deleteConfirmName = streak?.name || $t('streaks.noName');
      deleteConfirmTheme = streak?.theme || 'solid';
      return;
    }
    if (deleteTimeoutId) clearTimeout(deleteTimeoutId);
    try {
      await api.personalStreaks.delete(id);
      streaks = streaks.filter((s) => s.id !== id);
      if (selectedId === id) selectedId = null;
      stats = await api.personalStreaks.stats();
      notifyStreaksUpdated();
      deleteConfirm = null;
      deleteConfirmName = '';
      deleteConfirmTheme = 'solid';
    } catch (e) {
      logger.error('[streaks] delete error:', e);
      deleteConfirm = null;
      deleteConfirmName = '';
      deleteConfirmTheme = 'solid';
    }
  }

  function cancelDelete() {
    deleteConfirm = null;
    deleteConfirmName = '';
    deleteConfirmTheme = 'solid';
  }

  function openCreate() {
    editTarget = null;
    showModal = true;
    ensureStreakCreateModal();
  }

  function openEdit(s: PersonalStreak) {
    editTarget = s;
    showModal = true;
    ensureStreakCreateModal();
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function streakLabel(n: number): string {
    if (n === 0) return '0';
    return String(n);
  }

  function freqLabel(s: PersonalStreak): string {
    return (
      s.description?.trim() ||
      (s.frequency === 'every_n' && s.frequency_days > 1 ? `cada ${s.frequency_days}d` : 'diaria')
    );
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

  // Streak milestones that are shareable.
  const STREAK_MILESTONES = [7, 30, 100, 365];

  function isStreakMilestone(s: PersonalStreak): boolean {
    return STREAK_MILESTONES.includes(s.current_streak);
  }

  function shareStreak(s: PersonalStreak) {
    openShare({
      title: s.name,
      icon: 'Flame',
      value: `${s.current_streak}`,
      subtitle: $t('streaks.streakDays'),
      color: s.color || 'var(--xp)',
    });
  }
</script>

<div class="streaks-page">
  {#if mounted}
    <div class="streaks-layout" style="--panel-w: {panelWidth}px">
      <!-- ═══ LEFT PANEL: LIST ═══ -->
      <StreakListPanel
        {streaks}
        {filteredStreaks}
        {loading}
        {error}
        {selectedId}
        bind:searchQuery
        bind:showArchived
        {doneCount}
        {streakLabel}
        {freqLabel}
        {isStreakCompleted}
        {getDaysForCompletion}
        onToggleArchive={toggleArchivedView}
        onCreate={openCreate}
        onSelect={(id) => {
          selectedId = id;
          ensureStreakHeatmap();
        }}
        onEdit={openEdit}
        onDelete={deleteStreak}
      />

      <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
      <div class="resize-handle static"></div>

      <!-- ═══ RIGHT PANEL: DETAIL ═══ -->
      <div class="detail-panel">
        {#if selected}
          <div
            class="detail-content"
            class:completed={isStreakCompleted(selected)}
            style="--theme-ac: {selected.color || 'var(--xp)'};"
          >
            <button
              class="detail-exit-btn"
              onclick={() => (selectedId = null)}
              title={$t('streaks.backToMenu')}
              aria-label={$t('streaks.backToMenu')}
            >
              <X size={14} />
            </button>

            {#if !isStreakCompleted(selected) && isStreakMilestone(selected)}
              <button
                class="streak-share-btn"
                onclick={() => shareStreak(selected)}
                title={$t('streaks.shareMilestone')}
                aria-label={$t('streaks.shareStreak', { values: { name: selected.name } })}
              >
                <Share2 size={13} />
                <span>{$t('streaks.share')}</span>
              </button>
            {/if}

            <div class="top-metrics">
              <!-- Streak counter -->
              <div class="counter-section">
                <div class="counter-stack">
                  <h2
                    class="counter-title mono"
                    style="--title-accent: {isStreakCompleted(selected)
                      ? 'var(--target)'
                      : selected.color || 'var(--xp)'};"
                    title={selected.name}
                  >
                    {selected.name}
                  </h2>
                  <button
                    class="counter-ring"
                    style="--ring-color: {isStreakCompleted(selected)
                      ? 'var(--target)'
                      : selected.color || 'var(--xp)'};"
                    onclick={() =>
                      !selected.is_archived &&
                      !selected.today_checked &&
                      !isStreakCompleted(selected) &&
                      checkin(selected.id)}
                    disabled={selected.is_archived ||
                      selected.today_checked ||
                      busy.has(selected.id) ||
                      isStreakCompleted(selected)}
                    title={isStreakCompleted(selected)
                      ? $t('streaks.streakCompleted')
                      : selected.today_checked
                        ? $t('streaks.alreadyCheckedIn')
                        : $t('streaks.checkIn')}
                    aria-label={isStreakCompleted(selected)
                      ? $t('streaks.streakCompleted')
                      : selected.today_checked
                        ? $t('streaks.alreadyCheckedIn')
                        : $t('streaks.checkIn')}
                  >
                    {#if isStreakCompleted(selected)}
                      <span class="counter-num mono" style="color: var(--target);">✓</span>
                      <span class="counter-label mono">{$t('streaks.finished')}</span>
                    {:else}
                      <span class="counter-num mono">{selected.current_streak}</span>
                      <span class="counter-label mono">{$t('streaks.days')}</span>
                    {/if}
                  </button>
                </div>
              </div>

              <!-- Vertical stats panel -->
              <div class="detail-stats">
                <div class="dstat-row">
                  <span class="dstat-lbl">{$t('streaks.current')}</span>
                  <span class="dstat-val mono">{selected.current_streak}</span>
                </div>
                <div class="dstat-row">
                  <span class="dstat-lbl">{$t('streaks.best')}</span>
                  <span class="dstat-val mono">{selected.longest_streak}</span>
                </div>
                <div class="dstat-row">
                  <span class="dstat-lbl">{$t('streaks.checkIns')}</span>
                  <span class="dstat-val mono">{selected.total_checkins}</span>
                </div>
              </div>
            </div>

            <!-- Activity calendar -->
            <div class="heatmap-section">
              {#if StreakHeatmap}
                <StreakHeatmap
                  history={selected.history}
                  color={selected.color || 'var(--xp)'}
                  startDate={selected.start_date}
                  targetDate={selected.target_date}
                />
              {:else}
                <div
                  class="caption"
                  style="padding: 24px; text-align: center; color: var(--text-muted);"
                >
                  {$t('streaks.loadingCalendar')}
                </div>
              {/if}
            </div>

            <!-- Footer: dates + actions, sticky at bottom -->
            <div class="detail-footer">
              <div class="dates-info">
                {#if selected.start_date}
                  <div class="date-item">
                    <span class="date-label">{$t('streaks.startDate')}</span>
                    <span class="date-val mono"
                      >{new Date(selected.start_date).toLocaleDateString($localeStore, {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}</span
                    >
                  </div>
                {/if}
                {#if selected.target_date}
                  <div class="date-item">
                    <span class="date-label">{$t('streaks.targetDate')}</span>
                    <span class="date-val mono"
                      >{new Date(selected.target_date).toLocaleDateString($localeStore, {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}</span
                    >
                  </div>
                {/if}
                <div class="date-item">
                  <span class="date-label">{$t('streaks.createdDate')}</span>
                  <span class="date-val mono"
                    >{new Date(selected.created_at).toLocaleDateString($localeStore, {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}</span
                  >
                </div>
              </div>
            </div>
          </div>
        {:else}
          <!-- No selection state -->
          <div class="no-selection">
            {#if stats}
              <div class="no-selection-actions">
                <button
                  class="action-pill"
                  onclick={checkinAllCurrent}
                  disabled={activeCheckinCandidates.length === 0}
                  title={$t('streaks.checkInAll')}
                >
                  <CheckCheck size={14} />
                  <span>{$t('streaks.checkInAllBtn')}</span>
                </button>
                <button
                  class="action-pill"
                  onclick={openRandomStreak}
                  disabled={filteredStreaks.length === 0}
                  title={$t('streaks.randomStreak')}
                >
                  <Shuffle size={14} />
                  <span>{$t('streaks.randomStreakBtn')}</span>
                </button>
              </div>
              <StreakStatsPanel {stats} />
            {/if}
            <div class="no-sel-hint">
              <ChevronRight size={14} />
              <span>{$t('streaks.selectStreakHint')}</span>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- Delete confirmation modal -->
<svelte:window onkeydown={(e) => e.key === 'Escape' && (deleteConfirm = null)} />
{#if deleteConfirm !== null}
  <div class="modal-backdrop">
    <div
      class="delete-modal"
      class:theme-sketch={deleteConfirmTheme === 'sketch'}
      class:theme-glow={deleteConfirmTheme === 'glow'}
      class:theme-gradient={deleteConfirmTheme === 'gradient'}
      class:theme-neon={deleteConfirmTheme === 'neon'}
      class:theme-lcd={deleteConfirmTheme === 'lcd'}
      transition:scale={{ duration: 200 }}
    >
      <div class="delete-modal-content">
        <div class="delete-modal-icon">
          <X size={32} />
        </div>
        <h2 class="delete-modal-title">{$t('streaks.deleteStreak')}</h2>
        <p class="delete-modal-text">
          {$t('streaks.deleteConfirmPrefix')} <strong>{deleteConfirmName}</strong>{$t(
            'streaks.deleteConfirmSuffix'
          )}
        </p>
        <p class="delete-modal-warning">{$t('streaks.deleteWarning')}</p>
      </div>
      <div class="delete-modal-buttons">
        <button class="btn-cancel" onclick={cancelDelete}>{$t('common.cancel')}</button>
        <button
          class="btn-danger"
          onclick={() => deleteConfirm !== null && deleteStreak(deleteConfirm)}
          >{$t('common.delete')}</button
        >
      </div>
    </div>
  </div>
{/if}

{#if StreakCreateModal}
  <StreakCreateModal
    bind:open={showModal}
    editStreak={editTarget}
    on:close={() => {
      showModal = false;
      editTarget = null;
    }}
    on:save={handleSave}
    on:archive={() =>
      editTarget?.id != null && archiveStreak(editTarget.id, !editTarget.is_archived)}
  />
{/if}

<style>
  .streaks-page {
    height: 100%;
    width: 100%;
    background: var(--bg);
    overflow: hidden;
  }

  .streaks-layout {
    display: grid;
    grid-template-columns: var(--panel-w) 5px 1fr;
    height: 100%;
  }

  .detail-content.completed {
    --theme-ac: var(--target);
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     RIGHT PANEL
     ═══════════════════════════════════════════════════════════════════════ */
  .detail-panel {
    height: 100%;
    overflow: hidden;
  }

  .detail-content {
    padding: 0 20px 2px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    height: 100%;
    overflow: hidden;
    position: relative;
    isolation: isolate;
  }

  .detail-exit-btn {
    position: absolute;
    top: 16px;
    right: 16px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
    z-index: var(--z-base);
  }

  .detail-exit-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
    background: var(--elevated);
    transform: scale(1.04);
  }

  /* Top metrics */
  .top-metrics {
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
    margin-top: -8px;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    aspect-ratio: 2 / 0.68;
    gap: 0;
    flex-shrink: 0;
  }

  /* Counter */
  .counter-section {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
  }

  .counter-stack {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    width: min(220px, 100%);
  }

  .streak-share-btn {
    position: absolute;
    bottom: 16px;
    left: 16px;
    z-index: var(--z-base);
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .streak-share-btn:hover {
    border-color: var(--theme-ac, var(--xp));
    color: var(--text-primary);
  }

  .counter-title {
    margin: 0;
    width: 100%;
    font-size: 10px;
    line-height: 1.1;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--title-accent);
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .counter-ring {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 96px;
    height: 96px;
    border-radius: 50%;
    border: 2px solid var(--ring-color);
    box-shadow:
      0 0 30px color-mix(in srgb, var(--ring-color) 15%, transparent),
      inset 0 0 20px color-mix(in srgb, var(--ring-color) 5%, transparent);
    background: var(--surface);
    cursor: pointer;
    padding: 0;
    appearance: none;
    -webkit-appearance: none;
    transition:
      opacity 0.3s ease,
      border-color 0.3s ease,
      box-shadow 0.3s ease;
  }
  .counter-ring:disabled {
    cursor: default;
    opacity: 0.95;
  }
  .counter-ring:focus-visible {
    outline: 1px solid var(--ring-color);
    outline-offset: 3px;
  }

  .counter-num {
    font-size: 36px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
    transition:
      opacity 0.25s ease,
      transform 0.25s ease;
  }
  .counter-label {
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.15em;
    margin-top: 2px;
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
  .dstat-row + .dstat-row {
    border-top: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
  }
  .dstat-val {
    font-size: 17px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1;
  }
  .dstat-lbl {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Heatmap section */
  .heatmap-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    width: 100%;
    flex: 1;
    min-height: 0;
  }

  /* Footer (dates + actions) */
  .detail-footer {
    margin-top: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
    border-top: 1px solid var(--border-light);
    padding-top: 4px;
  }

  /* Dates */
  .dates-info {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .date-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    align-items: center;
  }
  .date-label {
    font-size: 9px;
    color: var(--text-disabled);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .date-val {
    font-size: 11px;
    color: var(--text-secondary);
  }

  /* No selection */
  .no-selection {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px;
    gap: 24px;
  }

  .no-selection-actions {
    width: min(360px, 100%);
    display: flex;
    gap: 10px;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: -8px;
  }

  .action-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-primary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-pill:hover {
    background: var(--elevated);
    border-color: var(--text-muted);
    transform: translateY(-1px);
  }

  .action-pill:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
  }

  .no-sel-hint {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-disabled);
    animation: pulse-hint 2s ease-in-out infinite;
  }

  @keyframes pulse-hint {
    0%,
    100% {
      opacity: 0.4;
    }
    50% {
      opacity: 0.8;
    }
  }

  /* Delete confirmation modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-overlay);
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .delete-modal {
    width: 90%;
    max-width: 400px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
  }

  .delete-modal-content {
    padding: 32px 24px 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-items: center;
    text-align: center;
  }

  .delete-modal-icon {
    color: var(--error);
    opacity: 0.8;
    display: flex;
  }

  .delete-modal-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .delete-modal-text {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.5;
  }

  .delete-modal-text strong {
    color: var(--text-primary);
    font-weight: 600;
  }

  .delete-modal-warning {
    font-size: 12px;
    color: var(--text-disabled);
    margin: 0;
    line-height: 1.4;
    font-style: italic;
  }

  .delete-modal-buttons {
    display: flex;
    gap: 8px;
    padding: 16px 24px;
    border-top: 1px solid var(--border-light);
    background: var(--elevated);
  }

  .btn-cancel {
    flex: 1;
    padding: 10px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-cancel:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .btn-danger {
    flex: 1;
    padding: 10px 16px;
    background: var(--error);
    border: none;
    border-radius: 6px;
    color: white;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-danger:hover {
    opacity: 0.9;
  }

  /* Sketch theme for delete modal */
  .delete-modal.theme-sketch {
    border: 1px dashed var(--text-muted);
    border-radius: 2px;
  }
  .delete-modal.theme-sketch .btn-danger,
  .delete-modal.theme-sketch .btn-cancel {
    border: 1px dashed var(--text-muted);
    border-radius: 2px;
    background: transparent;
    color: var(--text-primary);
  }
  .delete-modal.theme-sketch .btn-danger {
    border-color: var(--error);
    color: var(--error);
  }
  .delete-modal.theme-sketch .btn-danger:hover {
    background: color-mix(in srgb, var(--error) 10%, transparent);
  }
  .delete-modal.theme-sketch .btn-cancel:hover {
    background: color-mix(in srgb, var(--text-muted) 10%, transparent);
  }

  /* Glow, Gradient & Neon theme for delete modal */
  .delete-modal.theme-glow .btn-danger,
  .delete-modal.theme-glow .btn-cancel,
  .delete-modal.theme-gradient .btn-danger,
  .delete-modal.theme-gradient .btn-cancel,
  .delete-modal.theme-neon .btn-danger,
  .delete-modal.theme-neon .btn-cancel {
    border-color: transparent;
    background: transparent;
    color: var(--text-primary);
  }
  .delete-modal.theme-glow .btn-danger,
  .delete-modal.theme-gradient .btn-danger,
  .delete-modal.theme-neon .btn-danger {
    color: var(--error);
  }
  .delete-modal.theme-glow .btn-danger:hover,
  .delete-modal.theme-gradient .btn-danger:hover,
  .delete-modal.theme-neon .btn-danger:hover {
    border-color: transparent;
    background: color-mix(in srgb, var(--error) 10%, transparent);
  }
  .delete-modal.theme-glow .btn-cancel:hover,
  .delete-modal.theme-gradient .btn-cancel:hover,
  .delete-modal.theme-neon .btn-cancel:hover {
    border-color: transparent;
    background: color-mix(in srgb, var(--text-muted) 10%, transparent);
  }

  /* LCD theme for delete modal */
  .delete-modal.theme-lcd {
    background-color: var(--theme-ac);
    background-image:
      linear-gradient(rgba(0, 0, 0, 0.1) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 0, 0, 0.1) 1px, transparent 1px);
    background-size: 3px 3px;
    border: 1px solid color-mix(in srgb, var(--theme-ac) 70%, black);
    box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.15);
  }
  .delete-modal.theme-lcd .delete-modal-icon,
  .delete-modal.theme-lcd .delete-modal-title,
  .delete-modal.theme-lcd .delete-modal-text,
  .delete-modal.theme-lcd .delete-modal-text strong,
  .delete-modal.theme-lcd .delete-modal-warning {
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
    text-shadow: none;
    opacity: 1;
  }
  .delete-modal.theme-lcd .delete-modal-icon {
    filter: grayscale(1) brightness(0) opacity(0.8);
  }
  .delete-modal.theme-lcd .delete-modal-buttons {
    background: transparent;
    border-top: 1px solid color-mix(in srgb, var(--theme-ac) 70%, black);
  }
  .delete-modal.theme-lcd .btn-danger,
  .delete-modal.theme-lcd .btn-cancel {
    border-color: color-mix(in srgb, var(--theme-ac) 70%, black);
    background: transparent;
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
    font-weight: 700;
  }
  .delete-modal.theme-lcd .btn-danger:hover {
    border-color: color-mix(in srgb, var(--theme-ac) 20%, black);
    background: color-mix(in srgb, black 30%, transparent);
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
  }
  .delete-modal.theme-lcd .btn-cancel:hover {
    border-color: color-mix(in srgb, var(--theme-ac) 20%, black);
    background: color-mix(in srgb, black 15%, transparent);
    color: color-mix(in srgb, var(--theme-ac) 20%, black);
  }

  /* ── Responsive ── */

  /* Tablet — narrow the list panel */
  @media (max-width: 1024px) {
    .streaks-layout {
      grid-template-columns: minmax(200px, 240px) 5px 1fr;
    }
  }

  @media (max-width: 768px) {
    .streaks-layout {
      grid-template-columns: 1fr;
      grid-template-rows: auto;
    }

    .resize-handle.static {
      display: none;
    }

    .detail-content {
      padding: 0 var(--s3) var(--s2);
    }

    .top-metrics {
      max-width: 100%;
      grid-template-columns: 1fr;
      aspect-ratio: unset;
      gap: var(--s3);
    }

    .counter-section {
      padding-top: var(--s3);
    }

    .counter-ring {
      width: 80px;
      height: 80px;
    }

    .counter-num {
      font-size: 28px;
    }

    .detail-stats {
      flex-direction: row;
      justify-content: space-around;
      padding: var(--s2) 0;
      gap: var(--s3);
    }

    .dstat-row + .dstat-row {
      border-top: none;
      border-left: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
      padding-left: var(--s3);
    }

    .no-selection {
      padding: var(--s4) var(--s3);
    }

    .no-selection-actions {
      width: 100%;
    }

    .delete-modal {
      width: 95%;
    }
  }

  @media (max-width: 480px) {
    .detail-content {
      padding: 0 var(--s2) var(--s2);
    }

    .counter-ring {
      width: 68px;
      height: 68px;
    }

    .counter-num {
      font-size: 22px;
    }

    .counter-title {
      font-size: 9px;
    }

    .detail-stats {
      gap: var(--s2);
      padding: var(--s1) 0;
    }

    .dstat-val {
      font-size: 14px;
    }

    .no-selection {
      padding: var(--s3) var(--s2);
      gap: var(--s3);
    }

    .action-pill {
      padding: var(--s2) var(--s3);
      font-size: 11px;
    }

    .delete-modal-content {
      padding: var(--s4) var(--s3) var(--s3);
    }
  }

  @media (max-width: 360px) {
    .no-selection {
      padding: var(--s3) var(--s2);
      gap: var(--s3);
    }
    .counter-ring {
      width: 60px;
      height: 60px;
    }
    .counter-num {
      font-size: 18px;
    }
  }
</style>
