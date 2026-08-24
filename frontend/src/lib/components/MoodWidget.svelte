<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import { todayMood, moodHistory, moodStats, loadMood, saveMood } from '$lib/stores/mood';
  import { showNotification } from '$lib/stores/notifications';

  const MOODS = [
    { score: 1, emoji: '😞' },
    { score: 2, emoji: '😟' },
    { score: 3, emoji: '😐' },
    { score: 4, emoji: '🙂' },
    { score: 5, emoji: '😄' },
  ];

  let selectedScore = $state<number | null>(null);
  let noteText = $state('');
  let saving = $state(false);

  // Sync local state when today's mood loads/changes.
  $effect(() => {
    if ($todayMood) {
      selectedScore = $todayMood.score;
      noteText = $todayMood.note ?? '';
    }
  });

  // Last 7 days of history for the mini bar chart (newest last).
  const recentHistory = $derived($moodHistory.slice(-7));

  function barHeight(score: number): string {
    return `${(score / 5) * 100}%`;
  }

  onMount(() => {
    loadMood();
  });

  async function handleSelect(score: number) {
    selectedScore = score;
    saving = true;
    const entry = await saveMood(score, noteText.trim() || null);
    saving = false;
    if (entry) {
      showNotification($t('mood.saved'), 'success');
    } else {
      showNotification($t('mood.error'), 'error');
    }
  }

  async function handleSaveNote() {
    if (selectedScore === null) return;
    saving = true;
    const entry = await saveMood(selectedScore, noteText.trim() || null);
    saving = false;
    if (entry) {
      showNotification($t('mood.saved'), 'success');
    } else {
      showNotification($t('mood.error'), 'error');
    }
  }
</script>

<div class="mood-widget">
  <span class="mood-title mono">{$t('mood.title')}</span>

  <!-- Emoji selector -->
  <div class="mood-selector">
    {#each MOODS as m}
      <button
        class="mood-btn"
        class:selected={selectedScore === m.score}
        onclick={() => handleSelect(m.score)}
        aria-label={$t('mood.scoreLabel', { values: { score: m.score } })}
        title={$t('mood.scoreLabel', { values: { score: m.score } })}
      >
        <span class="mood-emoji">{m.emoji}</span>
      </button>
    {/each}
  </div>

  <!-- Optional note -->
  <div class="mood-note-wrap">
    <input
      type="text"
      class="mood-note-input"
      bind:value={noteText}
      placeholder={$t('mood.notePlaceholder')}
      aria-label={$t('mood.notePlaceholder')}
    />
    <button
      class="mood-note-save"
      onclick={handleSaveNote}
      disabled={saving || selectedScore === null}
      aria-label={$t('common.save')}
    >
      {$t('common.save')}
    </button>
  </div>

  <!-- 7-day history bar -->
  <div class="mood-history">
    <span class="mood-history-label">{$t('mood.history')}</span>
    <div class="mood-bars">
      {#each recentHistory as entry}
        <div class="mood-bar-col" title={`${entry.entry_date}: ${entry.score}/5`}>
          <div class="mood-bar-track">
            <div class="mood-bar-fill" style="height: {barHeight(entry.score)};"></div>
          </div>
        </div>
      {/each}
      {#if recentHistory.length === 0}
        <span class="mood-empty">{$t('mood.noHistory')}</span>
      {/if}
    </div>
  </div>

  <!-- Stats row -->
  <div class="mood-stats-row">
    <div class="mood-stat">
      <span class="mood-stat-value mono">{$moodStats.average.toFixed(1)}</span>
      <span class="mood-stat-label">{$t('mood.avg')}</span>
    </div>
    <div class="mood-stat-divider"></div>
    <div class="mood-stat">
      <span class="mood-stat-value mono">{$moodStats.streak}</span>
      <span class="mood-stat-label">{$t('mood.streak')}</span>
    </div>
  </div>
</div>

<style>
  .mood-widget {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 12px 0 10px;
    width: 100%;
  }

  .mood-title {
    font-size: 10px;
    font-weight: 500;
    color: var(--text-primary);
    letter-spacing: 0.14em;
  }

  /* ── Emoji selector ── */
  .mood-selector {
    display: flex;
    gap: 4px;
  }

  .mood-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    cursor: pointer;
    transition: all var(--t-fast);
    padding: 0;
    opacity: 0.5;
  }

  .mood-btn:hover {
    opacity: 1;
    border-color: var(--text-muted);
  }

  .mood-btn.selected {
    opacity: 1;
    border-color: var(--xp);
    background: var(--elevated);
    transform: scale(1.1);
  }

  .mood-emoji {
    font-size: 16px;
    line-height: 1;
  }

  /* ── Note input ── */
  .mood-note-wrap {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
    max-width: 220px;
  }

  .mood-note-input {
    flex: 1;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 8px;
    font-size: 11px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
  }

  .mood-note-input::placeholder {
    color: var(--text-muted);
  }

  .mood-note-input:focus {
    border-color: var(--text-muted);
  }

  .mood-note-save {
    padding: 4px 10px;
    font-size: 10px;
    font-family: var(--font-sans);
    border: 1px solid var(--xp);
    border-radius: var(--r);
    background: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
    cursor: pointer;
    transition: all var(--t-fast);
    white-space: nowrap;
  }

  .mood-note-save:hover:not(:disabled) {
    background: var(--xp-2);
    border-color: var(--xp-2);
  }

  .mood-note-save:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* ── History bar ── */
  .mood-history {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    width: 100%;
  }

  .mood-history-label {
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.08em;
  }

  .mood-bars {
    display: flex;
    align-items: flex-end;
    gap: 3px;
    height: 36px;
  }

  .mood-bar-col {
    display: flex;
    align-items: flex-end;
  }

  .mood-bar-track {
    width: 6px;
    height: 36px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    display: flex;
    align-items: flex-end;
  }

  .mood-bar-fill {
    width: 100%;
    background: var(--xp);
    border-radius: 2px;
    transition: height var(--t-normal);
  }

  .mood-empty {
    font-size: 9px;
    color: var(--text-muted);
  }

  /* ── Stats row ── */
  .mood-stats-row {
    display: flex;
    align-items: center;
    gap: var(--s4);
  }

  .mood-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .mood-stat-value {
    font-size: 16px;
    font-weight: 300;
    color: var(--text-primary);
    line-height: 1;
  }

  .mood-stat-label {
    font-size: 9px;
    color: var(--text-muted);
  }

  .mood-stat-divider {
    width: 1px;
    height: 24px;
    background: var(--border);
  }
</style>
