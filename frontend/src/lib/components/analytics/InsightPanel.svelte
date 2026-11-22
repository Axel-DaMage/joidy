<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { t } from 'svelte-i18n';
  import type { Insight } from '$lib/utils/insights';

  // Side panel of plain-language findings for each analytics slide (#1499).
  // Items come from the deterministic rules in lib/utils/insights.ts — each
  // is an i18n key + interpolation values rendered through $t.
  let { items = [] }: { items?: Insight[] } = $props();
</script>

<aside class="ip-card">
  <span class="ip-title">{$t('goalsAnalytics.insightsTitle')}</span>
  {#if items.length === 0}
    <span class="ip-empty">{$t('goalsAnalytics.insightsEmpty')}</span>
  {:else}
    <ul class="ip-list">
      {#each items as item (item.key + JSON.stringify(item.values ?? {}))}
        <li class="ip-item">
          <span class="ip-icon"><DynamicIcon name={item.icon} size={14} /></span>
          <span class="ip-text">{$t(`goalsAnalytics.insights.${item.key}`, { values: item.values })}</span>
        </li>
      {/each}
    </ul>
  {/if}
</aside>

<style>
  .ip-card {
    width: 272px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    backdrop-filter: blur(10px);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-height: 0;
    overflow-y: auto;
    box-sizing: border-box;
  }
  .ip-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    flex-shrink: 0;
  }
  .ip-empty {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.5;
  }
  .ip-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }
  .ip-item {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .ip-icon {
    color: var(--xp);
    flex-shrink: 0;
    margin-top: 1px;
    display: flex;
  }
  .ip-text {
    font-size: 11.5px;
    line-height: 1.45;
    color: var(--text-secondary);
  }
  .ip-text :global(b) {
    color: var(--text-primary);
  }
  @media (max-width: 700px) {
    .ip-card {
      width: 100%;
    }
  }
</style>
