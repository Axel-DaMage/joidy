<script lang="ts">
  import ChartCard from './ChartCard.svelte';
  import CodeXml from 'lucide-svelte/icons/code-xml';
  import type { GithubSummary } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Languages weighted by commits in the window (primary language per repo).
  let { summary, loading = false }: { summary?: GithubSummary | null; loading?: boolean } = $props();

  let langs = $derived(summary?.languages ?? []);
  // Legend stays bounded: top 5 + an "Other" row aggregating the tail.
  let shown = $derived(langs.slice(0, 5));
  let rest = $derived.by(() => {
    const tail = langs.slice(5);
    if (tail.length === 0) return null;
    return {
      commits: tail.reduce((a, l) => a + l.commits, 0),
      share: Math.round(tail.reduce((a, l) => a + l.share, 0) * 10) / 10,
    };
  });
  let langLabel = (name: string | null) => name ?? $t('analyticsPage.github.noLanguage');
</script>

<ChartCard title={$t('analyticsPage.github.langsTitle')}>
  {#snippet icon()}<CodeXml size={13} />{/snippet}
  {#if loading}
    <div class="chart-empty"><span>{$t('analyticsPage.github.loadingShort')}</span></div>
  {:else if langs.length === 0}
    <div class="chart-empty"><span>{$t('analyticsPage.github.summaryNeedToken')}</span></div>
  {:else}
    <div class="gl-body">
      <div
        class="gl-stack"
        role="img"
        aria-label={$t('analyticsPage.github.langsTitle')}
      >
        {#each langs as lang (lang.name ?? 'none')}
          <span
            class="gl-seg"
            style="width: {lang.share}%; background: {lang.color ?? 'var(--text-muted)'}"
            title="{langLabel(lang.name)} · {lang.share}%"
          ></span>
        {/each}
      </div>
      <div class="gl-list">
        {#each shown as lang (lang.name ?? 'none')}
          <div class="gl-row">
            <span
              class="gl-dot"
              style="background: {lang.color ?? 'var(--text-muted)'}"
            ></span>
            <span class="gl-name" title={langLabel(lang.name)}>{langLabel(lang.name)}</span>
            <span class="gl-share mono">{lang.share}%</span>
            <span class="gl-count mono">{lang.commits}</span>
          </div>
        {/each}
        {#if rest}
          <div class="gl-row">
            <span class="gl-dot" style="background: var(--text-muted)"></span>
            <span class="gl-name">{$t('analyticsPage.github.other')}</span>
            <span class="gl-share mono">{rest.share}%</span>
            <span class="gl-count mono">{rest.commits}</span>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</ChartCard>

<style>
  .gl-body {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    min-height: 0;
  }
  .gl-stack {
    display: flex;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
    flex: none;
  }
  .gl-seg {
    display: block;
    height: 100%;
    min-width: 2px;
    opacity: 0.9;
  }
  .gl-list {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-height: 0;
    overflow: hidden;
  }
  .gl-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
    min-width: 0;
  }
  .gl-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
  .gl-name {
    flex: 1;
    min-width: 0;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .gl-share {
    flex: none;
    width: 38px;
    text-align: right;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }
  .gl-count {
    flex: none;
    width: 34px;
    text-align: right;
    font-size: 10px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  @media (max-height: 800px) {
    .gl-list {
      gap: 4px;
    }
    .gl-row {
      gap: var(--s1);
    }
    .gl-name {
      font-size: 10px;
    }
    .gl-share, .gl-count {
      font-size: 10px;
    }
  }

  @media (max-height: 760px) {
    .gl-stack {
      height: 6px;
    }
    .gl-list {
      gap: 3px;
    }
    .gl-row {
      line-height: 1.15;
    }
  }
</style>
