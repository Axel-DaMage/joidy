<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import FlaskConical from 'lucide-svelte/icons/flask-conical';
  import { t } from 'svelte-i18n';
  import type { Insight, InsightTone } from '$lib/utils/insights';

  // Side panel of plain-language findings for each analytics slide (#1499).
  // Rows share the column height equally (no scrolling), each with a headline
  // figure; a "how it's calculated" note is pinned at the bottom.
  let { items = [], methodKey }: { items?: Insight[]; methodKey?: string } = $props();

  const TONE: Record<InsightTone, string> = {
    good: 'var(--success)',
    warn: 'var(--today)',
    bad: 'var(--error)',
    info: 'var(--link)',
  };
  const toneColor = (tone?: InsightTone) => (tone ? TONE[tone] : 'var(--text-primary)');
</script>

<aside class="ip-card">
  <div class="ip-head">
    <Sparkles size={13} />
    <span class="ip-title">{$t('goalsAnalytics.insightsTitle')}</span>
    
  </div>

  {#if items.length === 0}
    <span class="ip-empty">{$t('goalsAnalytics.insightsEmpty')}</span>
  {:else}
    <ul class="ip-list">
      {#each items as item, i (item.key + JSON.stringify(item.values ?? {}))}
        <li class="ip-item" style:--c={toneColor(item.tone)} style:--i={i}>
          <span class="ip-icon"><DynamicIcon name={item.icon} size={14} /></span>
          <div class="ip-body">
            {#if item.stat}<span class="ip-stat">{item.stat}</span>{/if}
            <span class="ip-text" class:lead={!item.stat}
              >{$t(`goalsAnalytics.insights.${item.key}`, { values: item.values })}</span
            >
          </div>
        </li>
      {/each}
    </ul>
  {/if}

  {#if methodKey}
    <div class="ip-method">
      <span class="ip-method-head"
        ><FlaskConical size={11} />{$t(`goalsAnalytics.method.${methodKey}.title`)}</span
      >
      <span class="ip-method-body">{$t(`goalsAnalytics.method.${methodKey}.body`)}</span>
    </div>
  {/if}
</aside>

<style>
  .ip-card {
    width: 280px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    backdrop-filter: blur(10px);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    min-height: 0;
    overflow: hidden;
    box-sizing: border-box;
    animation: ip-in 0.45s cubic-bezier(0.2, 0.7, 0.2, 1) 0.08s both;
  }
  .ip-head {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-shrink: 0;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
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
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .ip-item {
    flex: 1 1 0;
    min-height: 0;
    max-height: 132px;
    display: flex;
    gap: var(--s3);
    align-items: center;
    border-top: 1px solid var(--border);
    animation: ip-in 0.4s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(0.12s + var(--i) * 60ms);
  }
  .ip-icon {
    display: flex;
    flex-shrink: 0;
    color: var(--text-muted);
  }
  .ip-body {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }
  .ip-stat {
    font-size: clamp(17px, 2.4vh, 24px);
    font-weight: 700;
    line-height: 1.25;
    font-family: var(--font-mono);
    color: var(--c, var(--text-primary));
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ip-text {
    font-size: 11.5px;
    line-height: 1.4;
    color: var(--text-secondary);
  }
  .ip-text.lead {
    font-size: 12.5px;
    color: var(--text-primary);
  }
  .ip-method {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-top: var(--s3);
    border-top: 1px solid var(--border);
  }
  .ip-method-head {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .ip-method-body {
    font-size: 10.5px;
    line-height: 1.45;
    color: var(--text-muted);
  }
  @keyframes ip-in {
    from {
      opacity: 0;
      transform: translateX(10px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ip-card,
    .ip-item {
      animation: none;
    }
  }
  @media (max-width: 1100px) {
    .ip-card {
      width: 100%;
    }
    .ip-item {
      max-height: none;
    }
  }
</style>
