<script lang="ts">
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import FlaskConical from 'lucide-svelte/icons/flask-conical';
  import { t } from 'svelte-i18n';
  import type { Insight, InsightTone } from '$lib/utils/insights';
  import { insightIcon } from './insightIcons';

  // Side panel of plain-language findings for each analytics slide (#1499).
  // Every finding is a bordered card — icon chip, headline figure, plain
  // sentence and (for percentages) a thin meter. Cards share the column height
  // equally so the panel never scrolls; a "how it's calculated" note sits at
  // the bottom.
  let { items = [], methodKey }: { items?: Insight[]; methodKey?: string } = $props();

  const TONE: Record<InsightTone, string> = {
    good: 'var(--success)',
    warn: 'var(--today)',
    bad: 'var(--error)',
    info: 'var(--link)',
  };
  const toneColor = (tone?: InsightTone) => (tone ? TONE[tone] : 'var(--xp)');
</script>

<aside class="ip-card" aria-label={$t('analyticsPage.insightsTitle')}>
  <div class="ip-head">
    <Sparkles size={13} />
    <span>{$t('analyticsPage.insightsTitle')}</span>
  </div>

  {#if items.length === 0}
    <span class="ip-empty">{$t('analyticsPage.insightsEmpty')}</span>
  {:else}
    <ul class="ip-list">
      {#each items as item, i (item.key + JSON.stringify(item.values ?? {}))}
        {@const Icon = insightIcon(item.icon)}
        <li class="ip-item" style:--c={toneColor(item.tone)} style:--i={i}>
          <span class="ip-icon" aria-hidden="true"><Icon size={18} /></span>
          <div class="ip-body">
            {#if item.stat}<span class="ip-stat">{item.stat}</span>{/if}
            <span class="ip-text" class:lead={!item.stat}
              >{$t(`analyticsPage.insights.${item.key}`, { values: item.values })}</span
            >
            {#if item.meter !== undefined}
              <span class="ip-meter" aria-hidden="true"
                ><i style:--p={Math.min(1, Math.max(0, item.meter / 100))}></i></span
              >
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}

  {#if methodKey}
    <div class="ip-method">
      <span class="ip-method-head"
        ><FlaskConical size={11} />{$t(`analyticsPage.method.${methodKey}.title`)}</span
      >
      <span class="ip-method-body">{$t(`analyticsPage.method.${methodKey}.body`)}</span>
    </div>
  {/if}
</aside>

<style>
  .ip-card {
    width: 292px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-height: 0;
    overflow: hidden;
    box-sizing: border-box;
    contain: layout paint;
    animation: ip-in 0.45s cubic-bezier(0.2, 0.7, 0.2, 1) 0.08s both;
  }
  .ip-head {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-shrink: 0;
    padding: 0 var(--s1);
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
    padding: 0 var(--s1);
  }
  .ip-list {
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }
  .ip-item {
    --c: var(--xp);
    flex: 1 1 0;
    min-height: 0;
    max-height: 124px;
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: var(--s2) var(--s3);
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: color-mix(in srgb, var(--text-primary) 2%, transparent);
    transition:
      border-color 0.2s,
      background 0.2s;
    animation: ip-in 0.4s cubic-bezier(0.2, 0.7, 0.2, 1) both;
    animation-delay: calc(0.12s + var(--i) * 60ms);
  }
  .ip-item:hover {
    border-color: color-mix(in srgb, var(--c) 45%, var(--border));
    background: color-mix(in srgb, var(--c) 5%, transparent);
  }
  .ip-icon {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    flex-shrink: 0;
    border-radius: var(--r);
    color: var(--c);
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 30%, var(--border));
  }
  .ip-body {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 3px;
    min-width: 0;
    flex: 1;
  }
  .ip-stat {
    font-size: clamp(18px, 2.5vh, 24px);
    font-weight: 700;
    line-height: 1.2;
    font-family: var(--font-mono);
    color: var(--text-primary);
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
  .ip-meter {
    display: block;
    height: 3px;
    margin-top: 3px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
  }
  .ip-meter i {
    display: block;
    height: 100%;
    border-radius: 2px;
    background: var(--c);
    transform-origin: left;
    transform: scaleX(var(--p));
    animation: ip-meter 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) 0.2s both;
  }
  .ip-method {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: var(--s2) var(--s1) 0;
    border-top: 1px solid var(--border);
  }
  .ip-method-head {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
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
  @keyframes ip-meter {
    from {
      transform: scaleX(0);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ip-card,
    .ip-item,
    .ip-meter i {
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
