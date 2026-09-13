<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import { goto } from '$app/navigation';
  import type { Note } from '$lib/api';
  import { t } from 'svelte-i18n';

  export let accentColor = '#6366F1';
  export let githubConnected = false;
  export let githubLoading = false;
  export let githubIssues: { id: number; number: number; title: string; repo: string; url: string; state?: string }[] = [];
  export let githubPRs: { id: number; number: number; title: string; repo: string; url: string; state?: string; merged_at?: string | null }[] = [];
  export let repoColors: Record<string, string> = {};
  export let issueStats: { open: number; total: number } = { open: 0, total: 0 };
  export let prStats: { open: number; total: number } = { open: 0, total: 0 };
  export let ghFilter = 'created';
  export let ghType = 'all';
  export let itemLimit = 8;
  export let onSetFilter: (filter: string) => void;
  export let onSetType: (type: string) => void;

  export let activeTab: 'github' | 'recent-notes' = 'github';
  export let onTabChange: ((tab: 'github' | 'recent-notes') => void) | undefined = undefined;
  export let recentNotes: Note[] = [];

  function handleTabClick(tab: 'github' | 'recent-notes') {
    if (onTabChange) {
      onTabChange(tab);
    } else {
      activeTab = tab;
    }
  }

  function getPrBadgeInfo(pr: any): { icon: string; color: string } {
    if (pr.merged_at) return { icon: 'GitMerge', color: '#8250DF' };
    if (pr.state === 'open') return { icon: 'GitPullRequest', color: '#238636' };
    return { icon: 'XCircle', color: '#F85149' };
  }

  function getIssueInfo(issue: any): { icon: string; color: string } {
    if (issue.state === 'open') return { icon: 'CircleDot', color: '#238636' };
    return { icon: 'Circle', color: '#8250DF' };
  }
</script>

<div class="section-header github-header">
  <div class="gh-heading">
    {#if githubConnected}
      <div class="header-tabs">
        <button
          type="button"
          class="header-tab-btn"
          class:active={activeTab === 'github'}
          onclick={() => handleTabClick('github')}
        >
          <span style={activeTab === 'github' ? `color: ${accentColor}` : ''}>{$t('widgets.tabGithub')}</span>
          {#if activeTab === 'github' && githubLoading}
            <span class="gh-updating" title={$t('widgets.ghUpdating')}></span>
          {/if}
        </button>
        <button
          type="button"
          class="header-tab-btn"
          class:active={activeTab === 'recent-notes'}
          onclick={() => handleTabClick('recent-notes')}
        >
          <span style={activeTab === 'recent-notes' ? `color: ${accentColor}` : ''}>{$t('widgets.tabRecentNotes')}</span>
        </button>
      </div>
    {:else}
      <h4 style="color: {accentColor}">{$t('widgets.tabRecentNotes')}</h4>
    {/if}
  </div>

  {#if githubConnected && activeTab === 'github'}
    <div class="gh-filters">
      <div class="gh-filter">
        <button class="filter-btn" class:active={ghType === 'all'} onclick={() => onSetType('all')}>{$t('widgets.ghAll')}</button>
        <button class="filter-btn" class:active={ghType === 'issues'} onclick={() => onSetType('issues')}>{$t('widgets.ghIssues')}</button>
        <button class="filter-btn" class:active={ghType === 'prs'} onclick={() => onSetType('prs')}>PRs</button>
      </div>
      <span class="gh-filter-divider">|</span>
      <div class="gh-filter">
        <button class="filter-btn" class:active={ghFilter === 'created'} onclick={() => onSetFilter('created')}>{$t('widgets.ghCreated')}</button>
        <button class="filter-btn" class:active={ghFilter === 'assigned'} onclick={() => onSetFilter('assigned')}>{$t('widgets.ghAssigned')}</button>
      </div>
    </div>
  {:else}
    <div class="recent-notes-actions">
      <a href="/notes" class="view-all-link">{$t('widgets.viewAllNotes')}</a>
    </div>
  {/if}
</div>

<div class="github-body" style="--gh-items-max: {itemLimit}">
  {#if githubConnected && activeTab === 'github'}
    {#if githubLoading && githubIssues.length === 0 && githubPRs.length === 0}
      <div class="github-skeleton">
        {#each Array(itemLimit) as _, idx}
          <div class="skeleton-row" style="animation-delay: {idx * 80}ms">
            <span class="skeleton-icon"></span>
            <div class="skeleton-lines">
              <span class="skeleton-line long"></span>
              <span class="skeleton-line short"></span>
            </div>
          </div>
        {/each}
      </div>
    {:else if githubIssues.length > 0 || githubPRs.length > 0}
      <div class="github-list">
        {#if ghType === 'all' || ghType === 'prs'}
          {#each githubPRs as pr (pr.id)}
            {@const prInfo = getPrBadgeInfo(pr)}
            <a href={pr.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[pr.repo] || accentColor}">
              <span class="gh-badge-icon"><DynamicIcon name={prInfo.icon} size={14} color={prInfo.color} /></span>
              <div class="gh-info">
                <span class="gh-title truncate">{pr.title}</span>
                <span class="gh-meta mono">{pr.repo} #{pr.number}</span>
              </div>
            </a>
          {/each}
        {/if}
        {#if ghType === 'all' || ghType === 'issues'}
          {#each githubIssues as issue (issue.id)}
            {@const issueInfo = getIssueInfo(issue)}
            <a href={issue.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[issue.repo] || accentColor}">
              <span class="gh-badge-icon"><DynamicIcon name={issueInfo.icon} size={14} color={issueInfo.color} /></span>
              <div class="gh-info">
                <span class="gh-title truncate">{issue.title}</span>
                <span class="gh-meta mono">{issue.repo} #{issue.number}</span>
              </div>
            </a>
          {/each}
        {/if}
      </div>
    {:else}
      <div class="github-summary">
        <div class="stat"><span class="stat-value mono">{issueStats.open + prStats.open}</span><span class="stat-label label">open</span></div>
        <div class="stat-divider"></div>
        <div class="stat"><span class="stat-value mono">{issueStats.total}</span><span class="stat-label label">issues</span></div>
        <div class="stat-divider"></div>
        <div class="stat"><span class="stat-value mono">{prStats.total}</span><span class="stat-label label">prs</span></div>
      </div>
      <div class="empty-state success">{$t('widgets.ghNoPending')}</div>
    {/if}
  {:else}
    {#if recentNotes.length > 0}
      <div class="recent-notes-list">
        {#each recentNotes.slice(0, itemLimit) as note (note.id)}
          <NoteCard
            {note}
            showTags={true}
            on:select={() => goto(`/notes?id=${note.id}`)}
          />
        {/each}
      </div>
    {:else}
      <div class="empty-state">
        <span class="caption">{$t('widgets.recentNotesEmpty')}</span>
      </div>
    {/if}
  {/if}
</div>

<style>
  .github-header {
    border-top: 1px solid var(--border-light);
    min-height: 52px;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .gh-heading {
    display: flex; align-items: center; gap: 8px;
    flex-shrink: 0;
  }

  .header-tabs {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-tab-btn {
    background: transparent;
    border: none;
    padding: 2px 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--text-base, 14px);
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 2px solid transparent;
    transition: all var(--t-fast);
  }

  .header-tab-btn:hover {
    color: var(--text-secondary);
  }

  .header-tab-btn.active {
    border-bottom-color: var(--accent);
  }

  .recent-notes-actions {
    display: flex;
    align-items: center;
  }

  .view-all-link {
    font-size: 11px;
    color: var(--text-muted);
    text-decoration: none;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all var(--t-fast);
  }

  .view-all-link:hover {
    color: var(--accent);
    background: var(--elevated);
  }

  .recent-notes-list {
    display: flex;
    flex-direction: column;
  }

  .gh-updating {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.5);
    animation: ghPulse 1.4s ease-in-out infinite;
  }

  .gh-filter {
    display: flex; gap: 6px;
  }
  .gh-filters {
    display: flex; flex-direction: row; gap: 8px; align-items: center; flex-wrap: nowrap;
  }
  .gh-filter-divider {
    color: var(--border); font-size: 12px;
  }
  .filter-btn {
    font-size: 10px; padding: 4px 10px; border-radius: 4px;
    background: transparent; border: 1px solid var(--border-light);
    color: var(--text-muted); cursor: pointer; transition: all var(--t-fast);
    min-width: 60px; height: 24px; display: flex; align-items: center; justify-content: center;
  }
  .filter-btn:hover { border-color: var(--border); color: var(--text-secondary); }
  .filter-btn.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast-text, white);
  }

  .github-list { display: flex; flex-direction: column; }
  .github-body {
    --gh-item-h: 48px;
    height: calc(var(--gh-item-h) * var(--gh-items-max));
    overflow-y: auto;
  }
  .github-body:has(.empty-state) {
    height: auto;
  }
  .gh-item {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; border-bottom: 1px solid var(--border-light);
    text-decoration: none; color: var(--text-primary);
  }
  .gh-item:hover { background: var(--elevated); }
  .gh-badge-icon { display: flex; align-items: center; justify-content: center; min-width: 24px; }
  .gh-info { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .gh-title { flex: 1; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gh-meta { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
  .github-summary { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 16px; }
  .stat { display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .stat-value { font-size: 18px; font-weight: 600; }
  .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; }
  .stat-divider { width: 1px; height: 30px; background: var(--border-light); }
  .empty-state { padding: var(--s6) var(--s5); color: var(--text-muted); text-align: center; }
  .empty-state.success { color: #238636; text-align: center; padding: 12px; }

  .github-skeleton {
    display: flex; flex-direction: column; gap: 10px;
    padding: 12px; height: 100%;
  }

  .skeleton-row {
    display: grid; grid-template-columns: 24px 1fr; gap: 10px; align-items: center;
    animation: skeletonFade 1.2s ease-in-out infinite;
  }

  .skeleton-icon {
    width: 18px; height: 18px; border-radius: 6px;
    background: linear-gradient(90deg, rgba(125, 125, 125, 0.2) 0%, rgba(125, 125, 125, 0.35) 50%, rgba(125, 125, 125, 0.2) 100%);
    background-size: 200% 100%;
    animation: skeletonShimmer 1.4s ease-in-out infinite;
  }

  .skeleton-lines { display: flex; flex-direction: column; gap: 6px; }

  .skeleton-line {
    height: 10px; border-radius: 8px;
    background: linear-gradient(90deg, rgba(125, 125, 125, 0.18) 0%, rgba(125, 125, 125, 0.32) 50%, rgba(125, 125, 125, 0.18) 100%);
    background-size: 200% 100%;
    animation: skeletonShimmer 1.4s ease-in-out infinite;
  }

  .skeleton-line.long { width: 80%; }
  .skeleton-line.short { width: 45%; }

  @keyframes skeletonShimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @keyframes skeletonFade {
    0% { opacity: 0.65; }
    50% { opacity: 1; }
    100% { opacity: 0.65; }
  }

  @keyframes ghPulse {
    0% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.45); opacity: 1; }
    70% { box-shadow: 0 0 0 6px rgba(99, 102, 241, 0); opacity: 0.6; }
    100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); opacity: 1; }
  }

  @media (max-width: 768px) {
    .github-header {
      flex-direction: column;
      align-items: stretch;
      gap: var(--s2);
      min-height: auto;
      padding: var(--s2) var(--s3);
    }
    .gh-filters {
      flex-wrap: wrap;
      justify-content: center;
    }
    .filter-btn {
      min-width: 48px;
    }
    .github-body {
      --gh-item-h: 40px;
      max-height: 280px;
    }
    .github-summary {
      gap: var(--s3);
      padding: var(--s3);
    }
  }

  @media (max-width: 480px) {
    .gh-filters {
      flex-direction: column;
      gap: var(--s1);
    }
    .filter-btn {
      width: 100%;
      min-width: unset;
    }
    .gh-filter-divider {
      display: none;
    }
  }
</style>
