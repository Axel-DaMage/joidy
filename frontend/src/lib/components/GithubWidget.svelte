<script lang="ts">
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import Search from 'lucide-svelte/icons/search';
  import SlidersHorizontal from 'lucide-svelte/icons/sliders-horizontal';
  import { goto } from '$app/navigation';
  import type { Note } from '$lib/api';
  import { folderMetaStore } from '$lib/stores/settings';
  import { extractFrontmatter, getFileIcon } from '$lib/utils/fileTree';
  import { getLocale } from '$lib/stores/locale';
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
  // #1164 — estado y búsqueda son props bindeables para que el dashboard
  // los persista en UserSettings y sobrevivan a salir/entrar del dashboard.
  export let ghState = 'all';
  export let ghSearch = '';
  // #1095 — el cuerpo ya no se dimensiona con un tope de filas (height fija), es dinámico
  const recentNotesLimit = 8;
  const skeletonRows = 10;
  export let onSetFilter: (filter: string) => void;
  export let onSetType: (type: string) => void;

  // #1670 — secondary filters (type/scope/state) live in an overflow popover;
  // the header keeps only the segmented tabs, search and one toggle button.
  let filtersOpen = false;

  $: hasActiveFilters = ghType !== 'all' || ghFilter !== 'created' || ghState !== 'all';

  $: visiblePRs = githubPRs.filter((pr) => ghMatchesState(pr, ghState) && ghMatchesSearch(pr, ghSearch));
  $: visibleIssues = githubIssues.filter((issue) => ghMatchesState(issue, ghState) && ghMatchesSearch(issue, ghSearch));

  function ghMatchesState(item: { state?: string; merged_at?: string | null }, state: string): boolean {
    if (state === 'open') return item.state === 'open';
    if (state === 'merged') return !!item.merged_at;
    if (state === 'closed') return item.state === 'closed' && !item.merged_at;
    return true;
  }

  function ghMatchesSearch(item: { title: string; repo: string; number: number }, query: string): boolean {
    const q = query.trim().toLowerCase().replace(/^#+/, '');
    if (!q) return true;
    return item.title.toLowerCase().includes(q) || item.repo.toLowerCase().includes(q) || String(item.number).includes(q);
  }

  export let activeTab: 'github' | 'recent-notes' = 'github';
  export let onTabChange: ((tab: 'github' | 'recent-notes') => void) | undefined = undefined;
  export let recentNotes: Note[] = [];

  function handleTabClick(tab: 'github' | 'recent-notes') {
    if (tab !== 'github') filtersOpen = false;
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

  // #1670 — lean recent-notes rows share the gh-item treatment; the icon
  // resolution mirrors NoteCard (folder meta → frontmatter → filename guess).
  function noteMeta(note: Note) {
    const key = note.source_path || `note-${note.id}`;
    const meta = $folderMetaStore[key] || {};
    const fm = extractFrontmatter(note.content || '');
    return {
      icon: meta.icon || fm.icon || getFileIcon(note.title, note.content || ''),
      color: meta.color || fm.color || undefined,
      pack: fm.pack || undefined,
    };
  }

  function formatNoteDate(note: Note): string {
    const iso = note.updated_at || note.created_at;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const sameDay =
      d.getFullYear() === new Date().getFullYear() &&
      d.getMonth() === new Date().getMonth() &&
      d.getDate() === new Date().getDate();
    if (sameDay) {
      return d.toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString(getLocale(), { day: 'numeric', month: 'short' });
  }
</script>

<!-- #1670 — boxed panel per the Panel Border Standard (same chrome as the
     analytics .ac-card): one bordered surface, tabs up top, restrained
     actions, single-column lists below. -->
<svelte:window onkeydown={(e) => filtersOpen && e.key === 'Escape' && (filtersOpen = false)} />

<div class="gh-panel">
  <div class="gh-panel-head">
    {#if githubConnected}
      <div class="gh-seg" role="group" aria-label={$t('widgets.tabGithub')}>
        <button
          type="button"
          class="gh-seg-btn"
          class:active={activeTab === 'github'}
          aria-pressed={activeTab === 'github'}
          onclick={() => handleTabClick('github')}
        >
          <span>{$t('widgets.tabGithub')}</span>
          {#if activeTab === 'github' && githubLoading}
            <span class="gh-updating" title={$t('widgets.ghUpdating')}></span>
          {/if}
        </button>
        <button
          type="button"
          class="gh-seg-btn"
          class:active={activeTab === 'recent-notes'}
          aria-pressed={activeTab === 'recent-notes'}
          onclick={() => handleTabClick('recent-notes')}
        >
          <span>{$t('widgets.tabRecentNotes')}</span>
        </button>
      </div>
    {:else}
      <span class="gh-panel-title">{$t('widgets.tabRecentNotes')}</span>
    {/if}

    <div class="gh-head-actions">
      {#if githubConnected && activeTab === 'github'}
        <div class="gh-search-wrap">
          <Search size={11} />
          <input
            class="gh-search"
            type="search"
            placeholder={$t('widgets.ghSearch')}
            aria-label={$t('widgets.ghSearch')}
            bind:value={ghSearch}
          />
        </div>
        <div
          class="gh-filter-wrap"
          style="z-index: {filtersOpen ? 'var(--z-overlay)' : 'auto'};"
        >
          <button
            type="button"
            class="gh-icon-btn gh-filter-toggle"
            class:active={filtersOpen}
            style="z-index: {filtersOpen ? 'var(--z-overlay)' : 'auto'};"
            onclick={() => (filtersOpen = !filtersOpen)}
            title={$t('widgets.ghFilters')}
            aria-label={$t('widgets.ghFilters')}
            aria-haspopup="dialog"
            aria-expanded={filtersOpen}
            aria-controls="gh-filter-menu"
          >
            <SlidersHorizontal size={13} />
            {#if hasActiveFilters}
              <span class="gh-filter-dot" aria-hidden="true"></span>
            {/if}
          </button>

          {#if filtersOpen}
            <!-- Backdrop to close dropdown on outside click -->
            <div
              class="gh-filter-backdrop"
              onclick={() => (filtersOpen = false)}
              role="presentation"
              tabindex="-1"
            ></div>
            <div
              id="gh-filter-menu"
              class="gh-filter-menu"
              role="dialog"
              aria-label={$t('widgets.ghFilters')}
            >
              <div class="gh-filters-stack">
                <div class="gh-filter-group">
                  <span class="gh-filter-label">{$t('widgets.ghGroupType')}</span>
                  <div class="gh-filters">
                    <button type="button" class="filter-btn" class:active={ghType === 'all'} aria-pressed={ghType === 'all'} onclick={() => onSetType('all')}>{$t('widgets.ghAll')}</button>
                    <button type="button" class="filter-btn" class:active={ghType === 'issues'} aria-pressed={ghType === 'issues'} onclick={() => onSetType('issues')}>{$t('widgets.ghIssues')}</button>
                    <button type="button" class="filter-btn" class:active={ghType === 'prs'} aria-pressed={ghType === 'prs'} onclick={() => onSetType('prs')}>PRs</button>
                  </div>
                </div>
                <div class="gh-filter-group">
                  <span class="gh-filter-label">{$t('widgets.ghGroupScope')}</span>
                  <div class="gh-filters">
                    <button type="button" class="filter-btn" class:active={ghFilter === 'created'} aria-pressed={ghFilter === 'created'} onclick={() => onSetFilter('created')}>{$t('widgets.ghCreated')}</button>
                    <button type="button" class="filter-btn" class:active={ghFilter === 'assigned'} aria-pressed={ghFilter === 'assigned'} onclick={() => onSetFilter('assigned')}>{$t('widgets.ghAssigned')}</button>
                  </div>
                </div>
                <div class="gh-filter-group">
                  <span class="gh-filter-label">{$t('widgets.ghGroupState')}</span>
                  <div class="gh-filters">
                    <button type="button" class="filter-btn" class:active={ghState === 'all'} aria-pressed={ghState === 'all'} onclick={() => (ghState = 'all')}>{$t('widgets.ghStateAll')}</button>
                    <button type="button" class="filter-btn" class:active={ghState === 'open'} aria-pressed={ghState === 'open'} onclick={() => (ghState = 'open')}>{$t('widgets.ghStateOpen')}</button>
                    <button type="button" class="filter-btn" class:active={ghState === 'closed'} aria-pressed={ghState === 'closed'} onclick={() => (ghState = 'closed')}>{$t('widgets.ghStateClosed')}</button>
                    <button type="button" class="filter-btn" class:active={ghState === 'merged'} aria-pressed={ghState === 'merged'} onclick={() => (ghState = 'merged')}>{$t('widgets.ghStateMerged')}</button>
                  </div>
                </div>
              </div>
            </div>
          {/if}
        </div>
      {:else}
        <a href="/notes" class="view-all-link">{$t('widgets.viewAllNotes')}</a>
      {/if}
    </div>
  </div>

  <div class="github-body">
    {#if githubConnected && activeTab === 'github'}
      {#if githubLoading && githubIssues.length === 0 && githubPRs.length === 0}
        <div class="github-skeleton">
          {#each Array(skeletonRows) as _, idx}
            <!-- Shared `m-skeleton` shimmer (motion system, #1657). -->
            <div class="skeleton-row" style="animation-delay: {idx * 80}ms">
              <span class="skeleton-icon m-skeleton"></span>
              <span class="skeleton-line long m-skeleton"></span>
            </div>
          {/each}
        </div>
      {:else if githubIssues.length > 0 || githubPRs.length > 0}
        <div class="github-list">
          {#if ghType === 'all' || ghType === 'prs'}
            {#each visiblePRs as pr (pr.id)}
              {@const prInfo = getPrBadgeInfo(pr)}
              <a href={pr.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[pr.repo] || accentColor}" title="{pr.repo} #{pr.number} — {pr.title}">
                <span class="gh-identity">
                  <span class="gh-title truncate">{pr.title}</span>
                  <span class="gh-meta mono">{pr.repo} #{pr.number}</span>
                </span>
                <span class="gh-badge-icon"><DynamicIcon name={prInfo.icon} size={14} color={prInfo.color} /></span>
              </a>
            {/each}
          {/if}
          {#if ghType === 'all' || ghType === 'issues'}
            {#each visibleIssues as issue (issue.id)}
              {@const issueInfo = getIssueInfo(issue)}
              <a href={issue.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[issue.repo] || accentColor}" title="{issue.repo} #{issue.number} — {issue.title}">
                <span class="gh-identity">
                  <span class="gh-title truncate">{issue.title}</span>
                  <span class="gh-meta mono">{issue.repo} #{issue.number}</span>
                </span>
                <span class="gh-badge-icon"><DynamicIcon name={issueInfo.icon} size={14} color={issueInfo.color} /></span>
              </a>
            {/each}
          {/if}
          {#if visiblePRs.length === 0 && visibleIssues.length === 0}
            <div class="empty-state">{$t('widgets.ghNoResults')}</div>
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
          {#each recentNotes.slice(0, recentNotesLimit) as note (note.id)}
            {@const meta = noteMeta(note)}
            <button
              type="button"
              class="rn-item"
              title={note.title}
              onclick={() => goto(`/notes?id=${note.id}`)}
            >
              <span class="rn-icon"><DynamicIcon name={meta.icon} size={12} color={meta.color} pack={meta.pack} /></span>
              <span class="rn-title truncate">{note.title}</span>
              <span class="rn-date mono">{formatNoteDate(note)}</span>
            </button>
          {/each}
        </div>
      {:else}
        <div class="empty-state">
          <span class="caption">{$t('widgets.recentNotesEmpty')}</span>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  /* ── Panel chrome — boxed per the Panel Border Standard (.ac-card) ── */
  .gh-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    transition: border-color var(--t-fast);
  }
  .gh-panel:hover {
    border-color: var(--border-light);
  }
  /* While the filter popover is open it must escape the panel's rounded-corner
     clip, otherwise short panels cut the menu off. */
  .gh-panel:has(.gh-filter-menu) {
    overflow: visible;
  }

  .gh-panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s2);
    padding: var(--s2) var(--s3);
    flex-shrink: 0;
  }

  .gh-panel-title {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    padding: var(--s1) var(--s1);
  }

  .gh-head-actions {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-shrink: 0;
    min-width: 0;
  }

  /* ── Tab switcher — same segmented treatment as the app-header control ── */
  .gh-seg {
    display: flex;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
    flex-shrink: 0;
  }
  .gh-seg-btn {
    min-height: 24px;
    padding: 0 10px;
    border: none;
    border-left: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-mono);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: color var(--t-fast), background var(--t-fast);
  }
  .gh-seg-btn:first-child {
    border-left: none;
  }
  .gh-seg-btn:hover {
    color: var(--text-secondary);
  }
  .gh-seg-btn.active {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }

  .gh-updating {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.5);
    animation: ghPulse 1.4s ease-in-out infinite;
  }

  /* ── Header actions — one search field, one overflow toggle ── */
  .gh-search-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 24px;
    padding: 0 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    transition: border-color var(--t-fast);
  }
  .gh-search-wrap:focus-within {
    border-color: var(--xp);
    color: var(--text-secondary);
  }
  .gh-search {
    border: none;
    background: transparent;
    color: var(--text-primary);
    font-size: 11px;
    width: 110px;
    padding: 0;
    font-family: inherit;
  }
  .gh-search::placeholder { color: var(--text-muted); }
  .gh-search:focus { outline: none; }
  .gh-search-wrap:focus-within:has(.gh-search:focus-visible) {
    outline: 2px solid var(--xp);
    outline-offset: 1px;
  }

  .gh-icon-btn {
    position: relative;
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: color var(--t-fast), background var(--t-fast), border-color var(--t-fast);
  }
  .gh-icon-btn:hover {
    color: var(--text-primary);
    background: var(--hover);
  }
  .gh-icon-btn.active {
    color: var(--xp);
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }
  .gh-filter-wrap {
    position: relative;
    display: inline-flex;
  }
  .gh-filter-dot {
    position: absolute;
    top: -3px;
    right: -3px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--xp);
    border: 1.5px solid var(--surface);
  }
  .gh-filter-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-dropdown);
    cursor: default;
  }
  .gh-filter-menu {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    width: 220px;
    max-height: calc(100vh - 120px);
    overflow-y: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s2);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    z-index: var(--z-modal);
  }
  .gh-filters-stack {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }
  .gh-filter-group {
    display: flex;
    flex-direction: column;
    gap: var(--s1);
  }
  .gh-filter-label {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    padding: 0 2px;
  }
  .gh-filters {
    display: flex;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }
  .filter-btn {
    flex: 1 1 0;
    min-width: 0;
    min-height: 24px;
    padding: 0 6px;
    border: none;
    border-left: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 10px;
    font-weight: 600;
    font-family: var(--font-mono);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color var(--t-fast), background var(--t-fast);
  }
  .filter-btn:first-child {
    border-left: none;
  }
  .filter-btn:hover {
    color: var(--text-secondary);
  }
  .filter-btn.active {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }

  .view-all-link {
    font-size: 11px;
    color: var(--text-muted);
    text-decoration: none;
    padding: 4px 8px;
    border-radius: var(--r);
    font-family: var(--font-mono);
    transition: color var(--t-fast), background var(--t-fast);
  }
  .view-all-link:hover {
    color: var(--xp);
    background: var(--hover);
  }

  /* ── Body — dynamic, scrolls inside the boxed panel ── */
  .github-body {
    --gh-item-h: 32px;
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
  }
  .github-body:has(.empty-state),
  .github-body:has(.github-summary) {
    flex: 0 0 auto;
  }

  .github-list { display: flex; flex-direction: column; width: 100%; }
  .gh-item {
    display: flex; align-items: center; gap: 8px;
    min-height: var(--gh-item-h);
    padding: 4px 12px; border-bottom: 1px solid var(--border-light);
    text-decoration: none; color: var(--text-primary);
    transition: background var(--t-fast);
  }
  .gh-item:last-child { border-bottom: none; }
  .gh-item:hover { background: var(--elevated); }
  .gh-identity {
    flex: 1 1 auto; min-width: 0;
    display: flex; align-items: baseline; gap: 6px;
  }
  .gh-title { flex: 1 1 auto; min-width: 0; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gh-meta { flex-shrink: 0; font-size: 11px; color: var(--text-muted); white-space: nowrap; }
  .gh-badge-icon { display: flex; align-items: center; justify-content: center; flex-shrink: 0; }

  /* ── Recent notes — lean rows sharing the gh-item hierarchy ── */
  .recent-notes-list {
    display: flex;
    flex-direction: column;
  }
  .rn-item {
    display: flex;
    align-items: center;
    gap: var(--s2);
    width: 100%;
    min-height: var(--gh-item-h, 32px);
    padding: 4px 12px;
    border: none;
    border-bottom: 1px solid var(--border-light);
    background: transparent;
    color: var(--text-primary);
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: background var(--t-fast);
  }
  .rn-item:last-child { border-bottom: none; }
  .rn-item:hover { background: var(--elevated); }
  .rn-item:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: -2px;
  }
  .rn-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    color: var(--text-muted);
  }
  .rn-title {
    flex: 1 1 auto;
    min-width: 0;
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rn-date {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .github-summary { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 16px; }
  .stat { display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .stat-value { font-size: 18px; font-weight: 600; }
  .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; }
  .stat-divider { width: 1px; height: 30px; background: var(--border-light); }
  .empty-state { padding: var(--s6) var(--s5); color: var(--text-muted); text-align: center; }
  .empty-state.success { color: #238636; text-align: center; padding: 12px; }

  .github-skeleton {
    display: flex; flex-direction: column; gap: 10px;
    padding: 12px; width: 100%;
  }

  .skeleton-row {
    display: flex; gap: 10px; align-items: center;
    animation: skeletonFade 1.2s ease-in-out infinite;
  }

  /* Gradient sweep + border-radius come from the shared `m-skeleton`
     utility (app.css); these classes only keep the geometry. */
  .skeleton-icon {
    width: 18px; height: 18px; flex-shrink: 0;
  }

  .skeleton-line {
    height: 10px; flex: 1 1 auto;
  }

  .skeleton-line.long { max-width: 75%; }

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

  @media (prefers-reduced-motion: reduce) {
    .gh-updating {
      animation: none;
    }
    .skeleton-row,
    .skeleton-icon,
    .skeleton-line {
      animation: none;
    }
  }

  @media (max-width: 768px) {
    .gh-panel-head {
      flex-wrap: wrap;
      padding: var(--s2);
    }
    .gh-search {
      width: 80px;
    }
    .github-body {
      max-height: 280px;
    }
    .github-summary {
      gap: var(--s3);
      padding: var(--s3);
    }
  }

  @media (max-width: 480px) {
    .gh-panel-head {
      flex-direction: column;
      align-items: stretch;
      gap: var(--s2);
    }
    .gh-head-actions {
      justify-content: flex-end;
    }
    .gh-search-wrap {
      flex: 1 1 auto;
    }
    .gh-search {
      width: 100%;
      flex: 1 1 auto;
    }
    .gh-filter-menu {
      width: min(220px, 80vw);
    }
  }
</style>
