<script lang="ts">
  import { onMount } from 'svelte';
  import { t } from 'svelte-i18n';
  import { fade, slide } from 'svelte/transition';
  import { api } from '$lib/api';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import DynamicIcon from './DynamicIcon.svelte';

  type Issue = {
    id: number;
    number: number;
    title: string;
    repo: string;
    url: string;
    state: string;
    updated_at: string;
    author?: string;
  };
  type PR = {
    id: number;
    number: number;
    title: string;
    repo: string;
    url: string;
    state: string;
    draft: boolean;
    updated_at: string;
    author?: string;
  };

  let connected = false;
  let issues: Issue[] = [];
  let prs: PR[] = [];
  let loading = false;
  let error = '';

  const persisted = loadUserSettings();
  let showIssues = $state(persisted.statusBarUi?.showAssignedIssues ?? false);
  let showPRs = $state(persisted.statusBarUi?.showAssignedPRs ?? false);

  $effect(() => {
    patchUserSettings({
      statusBarUi: { showAssignedIssues: showIssues, showAssignedPRs: showPRs },
    });
  });

  async function loadAll() {
    loading = true;
    error = '';
    try {
      const status = await api.github.status();
      connected = status.connected;
      if (!connected) {
        issues = [];
        prs = [];
        return;
      }
      const [issuesRes, prsRes] = await Promise.all([
        api.github.issues('assigned'),
        api.github.pulls('assigned'),
      ]);
      issues = issuesRes.issues ?? [];
      prs = prsRes.pulls ?? [];
    } catch (e: any) {
      error = e?.message || 'Failed to load GitHub data';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadAll();
  });

  let openIssues = $derived(issues.filter((i) => i.state === 'open'));
  let openPRs = $derived(prs.filter((p) => p.state === 'open'));
</script>

{#if !connected && !loading}
  <!-- GitHub not connected: render nothing to keep the status bar clean -->
{:else}
  <div class="sb-gh">
    <!-- Assigned Issues -->
    <button
      class="sb-gh-pill"
      class:active={showIssues}
      onclick={() => (showIssues = !showIssues)}
      title={$t('widgets.ghAssigned') + ' — ' + $t('widgets.ghIssues')}
      aria-label={$t('widgets.ghAssigned') + ' — ' + $t('widgets.ghIssues')}
    >
      <DynamicIcon name="CircleDot" size={12} color="var(--accent)" />
      <span class="sb-gh-count">{openIssues.length}</span>
      <span class="sb-gh-label">{$t('widgets.ghIssues')}</span>
    </button>
    {#if showIssues}
      <div class="sb-gh-popover" transition:slide={{ duration: 150 }}>
        <div class="sb-gh-popover-header">
          <span>{$t('widgets.ghAssigned')} — {$t('widgets.ghIssues')}</span>
          <button class="sb-gh-close" onclick={() => (showIssues = false)} aria-label={$t('common.close')}>×</button>
        </div>
        {#if loading}
          <div class="sb-gh-empty">{$t('widgets.ghUpdating')}</div>
        {:else if error}
          <div class="sb-gh-empty sb-gh-error">{error}</div>
        {:else if openIssues.length === 0}
          <div class="sb-gh-empty">{$t('widgets.ghNoPending')}</div>
        {:else}
          <ul class="sb-gh-list">
            {#each openIssues as issue (issue.id)}
              <li>
                <a href={issue.url} target="_blank" rel="noopener noreferrer" class="sb-gh-item">
                  <span class="sb-gh-item-repo mono">{issue.repo}</span>
                  <span class="sb-gh-item-title">#{issue.number} — {issue.title}</span>
                </a>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}

    <!-- Assigned PRs -->
    <button
      class="sb-gh-pill"
      class:active={showPRs}
      onclick={() => (showPRs = !showPRs)}
      title={$t('widgets.ghAssigned') + ' — PRs'}
      aria-label={$t('widgets.ghAssigned') + ' — PRs'}
    >
      <DynamicIcon name="GitPullRequest" size={12} color="var(--success)" />
      <span class="sb-gh-count">{openPRs.length}</span>
      <span class="sb-gh-label">PRs</span>
    </button>
    {#if showPRs}
      <div class="sb-gh-popover" transition:slide={{ duration: 150 }}>
        <div class="sb-gh-popover-header">
          <span>{$t('widgets.ghAssigned')} — PRs</span>
          <button class="sb-gh-close" onclick={() => (showPRs = false)} aria-label={$t('common.close')}>×</button>
        </div>
        {#if loading}
          <div class="sb-gh-empty">{$t('widgets.ghUpdating')}</div>
        {:else if error}
          <div class="sb-gh-empty sb-gh-error">{error}</div>
        {:else if openPRs.length === 0}
          <div class="sb-gh-empty">{$t('widgets.ghNoPending')}</div>
        {:else}
          <ul class="sb-gh-list">
            {#each openPRs as pr (pr.id)}
              <li>
                <a href={pr.url} target="_blank" rel="noopener noreferrer" class="sb-gh-item">
                  <span class="sb-gh-item-repo mono">{pr.repo}</span>
                  <span class="sb-gh-item-title">#{pr.number} — {pr.title}{#if pr.draft} (draft){/if}</span>
                </a>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .sb-gh {
    display: flex;
    align-items: center;
    gap: 6px;
    position: relative;
  }
  .sb-gh-pill {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 10px;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all 0.15s;
  }
  .sb-gh-pill:hover {
    background: var(--surface-hover);
  }
  .sb-gh-pill.active {
    background: var(--surface-hover);
    border-color: var(--accent);
  }
  .sb-gh-count {
    font-weight: 700;
    color: var(--text-primary);
  }
  .sb-gh-label {
    color: var(--text-muted);
  }
  .sb-gh-popover {
    position: absolute;
    bottom: calc(100% + 6px);
    right: 0;
    width: 320px;
    max-height: 360px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    z-index: var(--z-popover, 100);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .sb-gh-popover-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    flex-shrink: 0;
  }
  .sb-gh-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    padding: 0 4px;
  }
  .sb-gh-close:hover {
    color: var(--text-primary);
  }
  .sb-gh-list {
    list-style: none;
    margin: 0;
    padding: 4px;
    overflow-y: auto;
    flex: 1;
  }
  .sb-gh-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    border-radius: 4px;
    text-decoration: none;
    color: var(--text-primary);
    transition: background 0.12s;
  }
  .sb-gh-item:hover {
    background: var(--surface-hover);
  }
  .sb-gh-item-repo {
    font-size: 9px;
    color: var(--text-muted);
  }
  .sb-gh-item-title {
    font-size: 11px;
    line-height: 1.4;
  }
  .sb-gh-empty {
    padding: 16px 12px;
    text-align: center;
    font-size: 11px;
    color: var(--text-muted);
  }
  .sb-gh-error {
    color: var(--error);
  }
</style>
