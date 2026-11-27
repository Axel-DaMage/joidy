<script lang="ts">
  import { onMount } from 'svelte';
  import { resolve } from '$app/paths';
  import { t } from 'svelte-i18n';
  import { fade, slide } from 'svelte/transition';
  import { api } from '$lib/api';
  import { getGithubStatus } from '$lib/stores/github';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { CircleDot, GitPullRequest } from 'lucide-svelte';

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

  let connected = $state(false);
  let issues = $state<Issue[]>([]);
  let prs = $state<PR[]>([]);
  let loading = $state(false);
  let error = $state('');

  const persisted = loadUserSettings();
  let showIssues = $state(persisted.statusBarUi?.showAssignedIssues ?? false);
  let showPRs = $state(persisted.statusBarUi?.showAssignedPRs ?? false);

  $effect(() => {
    patchUserSettings({
      statusBarUi: { showAssignedIssues: showIssues, showAssignedPRs: showPRs },
    });
  });

  // #1512 — only the connection check is eager; the issue/PR lists fan out
  // into upstream GitHub calls, so they load on first popover open.
  let listsLoaded = $state(false);

  async function loadAll() {
    loading = true;
    error = '';
    try {
      const status = await getGithubStatus();
      connected = status.connected;
      if (!connected) {
        issues = [];
        prs = [];
      }
    } catch (e: any) {
      error = e?.message || 'Failed to load GitHub data';
    } finally {
      loading = false;
    }
  }

  async function ensureLists() {
    if (listsLoaded || !connected) return;
    listsLoaded = true;
    loading = true;
    error = '';
    try {
      const [issuesRes, prsRes] = await Promise.all([
        api.github.issues('assigned', 30, 'all', { silent: true }),
        api.github.pulls('assigned', 30, 'all', { silent: true }),
      ]);
      issues = issuesRes.issues ?? [];
      prs = prsRes.pulls ?? [];
    } catch (e: any) {
      listsLoaded = false;
      error = e?.message || 'Failed to load GitHub data';
    } finally {
      loading = false;
    }
  }

  function toggleIssues() {
    showIssues = !showIssues;
    if (showIssues) ensureLists();
  }

  function togglePRs() {
    showPRs = !showPRs;
    if (showPRs) ensureLists();
  }

  onMount(() => {
    loadAll();
  });

  let openIssues = $derived(issues.filter((i) => i.state === 'open'));
  let openPRs = $derived(prs.filter((p) => p.state === 'open'));

  let issuesBtn = $state<HTMLButtonElement | null>(null);
  let prsBtn = $state<HTMLButtonElement | null>(null);

  // Non-modal popovers: Escape closes the open one and returns focus to its
  // pill toggle (#1307).
  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== 'Escape') return;
    if (showIssues) {
      e.preventDefault();
      showIssues = false;
      issuesBtn?.focus();
    } else if (showPRs) {
      e.preventDefault();
      showPRs = false;
      prsBtn?.focus();
    }
  }
</script>

{#if !connected && !loading}
  <!-- GitHub not connected: render nothing to keep the status bar clean -->
{:else}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="sb-gh" onkeydown={handleKeydown}>
    <!-- Assigned Issues -->
    <button
      class="sb-gh-pill"
      class:active={showIssues}
      bind:this={issuesBtn}
      onclick={toggleIssues}
      title={$t('widgets.ghAssigned') + ' — ' + $t('widgets.ghIssues')}
      aria-label={$t('widgets.ghAssigned') + ' — ' + $t('widgets.ghIssues')}
      aria-haspopup="dialog"
      aria-expanded={showIssues}
      aria-controls="sb-gh-issues-popover"
    >
      <CircleDot size={12} color="var(--accent)" />
      <span class="sb-gh-count">{listsLoaded ? openIssues.length : '–'}</span>
      <span class="sb-gh-label">{$t('widgets.ghIssues')}</span>
    </button>
    {#if showIssues}
      <div
        id="sb-gh-issues-popover"
        class="sb-gh-popover"
        role="dialog"
        aria-label="{$t('widgets.ghAssigned')} — {$t('widgets.ghIssues')}"
        transition:slide={{ duration: 150 }}
      >
        <div class="sb-gh-popover-header">
          <span>{$t('widgets.ghAssigned')} — {$t('widgets.ghIssues')}</span>
          <button
            class="sb-gh-close"
            onclick={() => (showIssues = false)}
            aria-label={$t('common.close')}>×</button
          >
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
        <!-- #1662 — land on the in-app open-issues view (dashboard GitHub
             widget pre-filtered to assigned + open). -->
        <a
          class="sb-gh-viewall"
          href="{resolve('/')}?activity=github&ghType=issues&ghFilter=assigned&ghState=open"
          onclick={() => (showIssues = false)}>{$t('widgets.ghViewAll')}</a
        >
      </div>
    {/if}

    <!-- Assigned PRs -->
    <button
      class="sb-gh-pill"
      class:active={showPRs}
      bind:this={prsBtn}
      onclick={togglePRs}
      title={$t('widgets.ghAssigned') + ' — PRs'}
      aria-label={$t('widgets.ghAssigned') + ' — PRs'}
      aria-haspopup="dialog"
      aria-expanded={showPRs}
      aria-controls="sb-gh-prs-popover"
    >
      <GitPullRequest size={12} color="var(--success)" />
      <span class="sb-gh-count">{listsLoaded ? openPRs.length : '–'}</span>
      <span class="sb-gh-label">PRs</span>
    </button>
    {#if showPRs}
      <div
        id="sb-gh-prs-popover"
        class="sb-gh-popover"
        role="dialog"
        aria-label="{$t('widgets.ghAssigned')} — PRs"
        transition:slide={{ duration: 150 }}
      >
        <div class="sb-gh-popover-header">
          <span>{$t('widgets.ghAssigned')} — PRs</span>
          <button
            class="sb-gh-close"
            onclick={() => (showPRs = false)}
            aria-label={$t('common.close')}>×</button
          >
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
                  <span class="sb-gh-item-title"
                    >#{pr.number} — {pr.title}{#if pr.draft}
                      (draft){/if}</span
                  >
                </a>
              </li>
            {/each}
          </ul>
        {/if}
        <!-- #1662 — land on the in-app open-PRs view (dashboard GitHub
             widget pre-filtered to assigned + open). -->
        <a
          class="sb-gh-viewall"
          href="{resolve('/')}?activity=github&ghType=prs&ghFilter=assigned&ghState=open"
          onclick={() => (showPRs = false)}>{$t('widgets.ghViewAll')}</a
        >
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
  .sb-gh-viewall {
    display: block;
    padding: 8px 12px;
    border-top: 1px solid var(--border);
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--accent);
    text-decoration: none;
    text-align: center;
    flex-shrink: 0;
    transition: background var(--t-fast, 0.12s);
  }
  .sb-gh-viewall:hover {
    background: var(--surface-hover);
  }
  .sb-gh-viewall:focus-visible {
    outline: 1px solid var(--xp);
    outline-offset: -1px;
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
