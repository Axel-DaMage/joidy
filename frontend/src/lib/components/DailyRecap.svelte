<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import DynamicIcon from './DynamicIcon.svelte';

  let recap = $state<{ status: string; recap: string; suggestions: string[] } | null>(null);
  let loading = $state(true);
  let dismissed = $state(false);

  // Show the recap only after 20:00 local time and if not already dismissed today
  const STORAGE_KEY = 'joidy-daily-recap-dismissed';
  const today = new Date().toISOString().slice(0, 10);

  onMount(() => {
    const hour = new Date().getHours();
    const dismissedDate = localStorage.getItem(STORAGE_KEY);
    if (dismissedDate === today) {
      dismissed = true;
      loading = false;
      return;
    }
    if (hour >= 20) {
      void loadRecap();
    } else {
      loading = false;
    }
  });

  async function loadRecap() {
    try {
      recap = await api.ai.dailyRecap(today);
    } catch {
      recap = null;
    } finally {
      loading = false;
    }
  }

  function dismiss() {
    localStorage.setItem(STORAGE_KEY, today);
    dismissed = true;
  }
</script>

{#if !dismissed && !loading && recap && recap.status === 'success' && recap.recap}
  <div class="daily-recap-card">
    <div class="recap-header">
      <DynamicIcon name="Sparkles" size={16} />
      <span class="recap-title">Resumen del día</span>
      <button class="recap-dismiss" onclick={dismiss} title="Cerrar" aria-label="Cerrar resumen">✕</button>
    </div>
    <p class="recap-text">{recap.recap}</p>
    {#if recap.suggestions.length > 0}
      <div class="recap-suggestions">
        {#each recap.suggestions as suggestion}
          <div class="suggestion-item">
            <span class="suggestion-bullet">→</span>
            <span>{suggestion}</span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .daily-recap-card {
    background: var(--elevated);
    border: 1px solid var(--xp);
    border-radius: var(--r);
    padding: 16px;
    margin-bottom: 16px;
  }

  .recap-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .recap-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--xp);
    flex: 1;
  }

  .recap-dismiss {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    padding: 2px 6px;
  }

  .recap-dismiss:hover {
    color: var(--text-primary);
  }

  .recap-text {
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-secondary);
    margin: 0 0 12px 0;
  }

  .recap-suggestions {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .suggestion-item {
    display: flex;
    gap: 8px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .suggestion-bullet {
    color: var(--xp);
    flex-shrink: 0;
  }
</style>
