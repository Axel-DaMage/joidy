<script lang="ts">
  import ChartCard from './ChartCard.svelte';
  import FolderGit2 from 'lucide-svelte/icons/folder-git-2';
  import Lock from 'lucide-svelte/icons/lock';
  import type { GithubSummary } from '$lib/api';
  import { t } from 'svelte-i18n';

  // Top repositories by commits in the window (GitHub GraphQL summary).
  let { summary, loading = false }: { summary?: GithubSummary | null; loading?: boolean } = $props();

  let repos = $derived(summary?.repos ?? []);
  let maxCommits = $derived(Math.max(1, ...repos.map((r) => r.commits)));
</script>

<ChartCard title={$t('analyticsPage.github.reposTitle')}>
  {#snippet icon()}<FolderGit2 size={13} />{/snippet}
  {#if loading}
    <div class="chart-empty"><span>{$t('analyticsPage.github.loadingShort')}</span></div>
  {:else if repos.length === 0}
    <div class="chart-empty"><span>{$t('analyticsPage.github.summaryNeedToken')}</span></div>
  {:else}
    <div class="gr-list">
      {#each repos as repo (repo.name)}
        <div class="gr-row">
          <span
            class="gr-dot"
            style="background: {repo.color ?? 'var(--text-muted)'}"
          ></span>
          <span class="gr-name">
            <a
              class="gr-link"
              href="https://github.com/{repo.name}"
              target="_blank"
              rel="noopener noreferrer"
              title="{repo.name}"
              >{repo.name}</a
            >
            {#if repo.private}<Lock size={9} style="color: var(--text-muted)" />{/if}
          </span>
          <span class="gr-bar"
            ><span
              class="gr-fill"
              style="width: {(repo.commits / maxCommits) * 100}%; background: {repo.color ??
                'var(--text-muted)'}"
            ></span></span
          >
          <span class="gr-count mono">{repo.commits}</span>
        </div>
      {/each}
    </div>
  {/if}
</ChartCard>

<style>
  .gr-list {
    display: flex;
    flex-direction: column;
    gap: 7px;
    min-height: 0;
    overflow: hidden;
  }
  .gr-row {
    display: flex;
    align-items: center;
    gap: var(--s2);
    min-width: 0;
  }
  .gr-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
  .gr-name {
    flex: 0 1 auto;
    max-width: 46%;
    min-width: 0;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .gr-link {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .gr-link:hover {
    color: var(--xp);
    text-decoration: underline;
  }
  .gr-bar {
    flex: 1;
    min-width: 20px;
    height: 4px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    overflow: hidden;
  }
  .gr-fill {
    display: block;
    height: 100%;
    border-radius: 2px;
    opacity: 0.85;
    transition: width 0.5s cubic-bezier(0.2, 0.7, 0.2, 1);
  }
  .gr-count {
    flex: none;
    width: 30px;
    text-align: right;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }

  @media (max-height: 800px) {
    .gr-list {
      gap: 4px;
    }
    .gr-row {
      gap: var(--s1);
    }
    .gr-link {
      font-size: 10px;
    }
    .gr-count {
      font-size: 10px;
    }
  }

  @media (max-height: 760px) {
    .gr-list {
      gap: 3px;
    }
  }
</style>
