<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { SvelteMap, SvelteSet } from 'svelte/reactivity';
  import {
    api,
    type GmailStatus,
    type GmailMessageSummary,
    type GmailMessage,
    type GmailSendInput,
  } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';
  import {
    isGmailAuthError,
    parseAddress,
  } from '$lib/utils/gmail';
  import GmailMessageList from '$lib/components/gmail/GmailMessageList.svelte';
  import GmailMessageView from '$lib/components/gmail/GmailMessageView.svelte';
  import GmailComposeDialog from '$lib/components/gmail/GmailComposeDialog.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { t } from 'svelte-i18n';
  import Search from 'lucide-svelte/icons/search';
  import Inbox from 'lucide-svelte/icons/inbox';
  import RefreshCw from 'lucide-svelte/icons/refresh-cw';
  import Send from 'lucide-svelte/icons/send';
  import TriangleAlert from 'lucide-svelte/icons/triangle-alert';

  // ── Gmail system labels exposed as filter chips ────────────────────────────
  const LABEL_FILTERS = [
    { id: 'INBOX', key: 'inbox' },
    { id: 'SENT', key: 'sent' },
    { id: 'IMPORTANT', key: 'important' },
    { id: 'UNREAD', key: 'unread' },
    { id: 'STARRED', key: 'starred' },
    { id: 'SPAM', key: 'spam' },
    { id: 'TRASH', key: 'trash' },
  ] as const;

  const PAGE_SIZE = 50;
  // The list endpoint returns stubs only (no subject/sender) — details are
  // hydrated in the background, capped to keep Gmail API quota sane.
  const HYDRATE_LIMIT = 30;
  const HYDRATE_CONCURRENCY = 4;

  // ── Connection status ──────────────────────────────────────────────────────
  let status = $state<GmailStatus | null>(null);
  let statusLoading = $state(true);
  let connecting = $state(false);
  let connectError = $state('');
  let connectPoll: ReturnType<typeof setInterval> | null = null;
  let connectTimeout: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  // ── Message list ───────────────────────────────────────────────────────────
  let messages = $state<GmailMessageSummary[]>([]);
  let nextPageToken = $state<string | null>(null);
  let totalEstimate = $state<number | null>(null);
  let listLoading = $state(false);
  let loadingMore = $state(false);
  let loadError = $state(false);
  let searchQuery = $state('');
  let labelFilter = $state<string>('INBOX');
  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  // ── Detail cache + hydration ───────────────────────────────────────────────
  const details = new SvelteMap<string, GmailMessage>();
  const detailInflight = new SvelteSet<string>();
  const hydrateQueue: string[] = [];
  let activeHydration = 0;
  let selected = $state<GmailMessage | null>(null);
  let detailLoading = $state(false);

  // ── Compose ────────────────────────────────────────────────────────────────
  let composeOpen = $state(false);
  let composePrefill = $state<{ to?: string; cc?: string; subject?: string; body?: string } | null>(null);
  let sending = $state(false);

  // ── Derived ────────────────────────────────────────────────────────────────
  const connected = $derived(status?.connected === true);
  // null capability = legacy token, unknown — attempt the call and let a 403
  // flip the UI into the reconnect state instead of pre-blocking.
  const canModify = $derived(status?.gmail_modify !== false);
  const canSend = $derived(status?.gmail_send !== false);
  const needsReconnect = $derived(
    connected &&
      (status?.gmail_read === false || status?.gmail_modify === false || status?.gmail_send === false)
  );
  const unreadInView = $derived(messages.filter((m) => m.label_ids?.includes('UNREAD')).length);

  // ── Status / OAuth ─────────────────────────────────────────────────────────
  async function loadStatus(): Promise<void> {
    try {
      status = await api.gmail.status();
      statusLoading = false;
      if (status.connected) void refreshList();
    } catch (e) {
      logger.error(e);
      statusLoading = false;
    }
  }

  function stopConnectPolling(): void {
    if (connectPoll) {
      clearInterval(connectPoll);
      connectPoll = null;
    }
    if (connectTimeout) {
      clearTimeout(connectTimeout);
      connectTimeout = null;
    }
  }

  /** Inline Google OAuth connect — same popup+poll pattern as SettingsGoogle. */
  async function connectGoogle(): Promise<void> {
    connecting = true;
    connectError = '';
    stopConnectPolling();
    try {
      const { url } = await api.google.authUrl();
      window.open(url, '_blank', 'noopener,noreferrer');
      connectPoll = setInterval(async () => {
        if (destroyed) return;
        try {
          const s = await api.gmail.status();
          status = s;
          if (s.connected) {
            stopConnectPolling();
            connecting = false;
            showNotification($t('gmail.connectOk'), 'success');
            await refreshList();
          }
        } catch {
          /* transient poll failure — keep waiting */
        }
      }, 3000);
      connectTimeout = setTimeout(() => {
        stopConnectPolling();
        connecting = false;
        if (!connected && !destroyed) connectError = $t('gmail.connectTimeout');
      }, 300000);
    } catch (e) {
      logger.error(e);
      connectError = $t('gmail.connectError');
      connecting = false;
    }
  }

  function openSettings(): void {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
  }

  // ── List ───────────────────────────────────────────────────────────────────
  async function refreshList(append = false): Promise<void> {
    if (!connected) return;
    if (append) loadingMore = true;
    else {
      listLoading = true;
      loadError = false;
    }
    try {
      const page = await api.gmail.list({
        q: searchQuery.trim() || undefined,
        labelIds: labelFilter ? [labelFilter] : undefined,
        maxResults: PAGE_SIZE,
        pageToken: append ? nextPageToken : undefined,
      });
      messages = append ? [...messages, ...page.messages] : page.messages;
      nextPageToken = page.next_page_token;
      if (!append) {
        totalEstimate = page.result_size_estimate ?? null;
        // Drop queued hydration ids for rows that just left the view.
        hydrateQueue.length = 0;
      }
      scheduleHydration();
    } catch (e) {
      logger.error(e);
      if (isGmailAuthError(e)) {
        // Force a status re-check — scopes may have been revoked.
        void loadStatus();
      }
      if (!append && messages.length === 0) loadError = true;
      else showNotification($t('gmail.loadError'), 'error');
    } finally {
      listLoading = false;
      loadingMore = false;
    }
  }

  function onSearchInput(): void {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => void refreshList(), 300);
  }

  function pickLabel(labelId: string): void {
    if (labelFilter === labelId) return;
    labelFilter = labelId;
    selected = null;
    void refreshList();
  }

  // ── Detail hydration (subject/sender are not in list stubs) ────────────────
  function scheduleHydration(): void {
    const pending = messages
      .filter((m) => m.id && !details.has(m.id) && !detailInflight.has(m.id))
      .slice(0, HYDRATE_LIMIT)
      .map((m) => m.id as string);
    hydrateQueue.push(...pending);
    void pumpHydration();
  }

  async function pumpHydration(): Promise<void> {
    while (hydrateQueue.length > 0 && activeHydration < HYDRATE_CONCURRENCY) {
      const id = hydrateQueue.shift();
      if (!id || details.has(id) || detailInflight.has(id)) continue;
      detailInflight.add(id);
      activeHydration++;
      api
        .gmail.get(id)
        .then((msg) => {
          details.set(id, msg);
        })
        .catch(() => {
          /* hydration is best-effort — the row keeps its snippet */
        })
        .finally(() => {
          detailInflight.delete(id);
          activeHydration--;
          void pumpHydration();
        });
    }
  }

  async function openMessage(message: GmailMessageSummary): Promise<void> {
    if (!message.id) return;
    const cached = details.get(message.id);
    if (cached) {
      selected = cached;
      if (canModify && cached.label_ids?.includes('UNREAD')) {
        void markReadSilent(message.id);
      }
      return;
    }
    detailLoading = true;
    try {
      const msg = await api.gmail.get(message.id);
      details.set(message.id, msg);
      selected = msg;
      // Gmail marks opened mail as read — mirror that when we may modify.
      if (canModify && msg.label_ids?.includes('UNREAD')) {
        void markReadSilent(message.id);
      }
    } catch (e) {
      logger.error(e);
      if (isGmailAuthError(e)) void loadStatus();
      else showNotification($t('gmail.loadError'), 'error');
    } finally {
      detailLoading = false;
    }
  }

  function closeMessage(): void {
    selected = null;
  }

  async function markReadSilent(id: string): Promise<void> {
    try {
      const res = await api.gmail.read(id);
      applyLabels(id, res.label_ids ?? []);
      if (selected?.id === id) {
        selected = { ...selected, label_ids: res.label_ids ?? [] };
      }
    } catch {
      /* non-fatal — the message simply stays unread */
    }
  }

  // ── Label actions ──────────────────────────────────────────────────────────
  function applyLabels(id: string, labelIds: string[]): void {
    messages = messages.map((m) => (m.id === id ? { ...m, label_ids: labelIds } : m));
    const cached = details.get(id);
    if (cached) details.set(id, { ...cached, label_ids: labelIds });
  }

  async function runLabelAction(
    message: GmailMessageSummary | GmailMessage,
    action: 'archive' | 'trash' | 'untrash' | 'read' | 'unread'
  ): Promise<void> {
    const id = message.id;
    if (!id || !canModify) return;
    try {
      const res = await api.gmail[action](id);
      applyLabels(id, res.label_ids ?? []);
      if (selected?.id === id) {
        selected = { ...selected, label_ids: res.label_ids ?? [] };
      }
      // archive/trash/untrash change set membership — refresh the list so the
      // row appears/disappears exactly like Gmail would.
      if (action !== 'read' && action !== 'unread') void refreshList();
    } catch (e) {
      logger.error(e);
      if (isGmailAuthError(e)) void loadStatus();
      showNotification($t('gmail.actionError'), 'error');
    }
  }

  function toggleRead(message: GmailMessageSummary | GmailMessage): void {
    const unread = message.label_ids?.includes('UNREAD');
    void runLabelAction(message, unread ? 'read' : 'unread');
  }

  // ── Compose / send ─────────────────────────────────────────────────────────
  function openCompose(prefill: { to?: string; cc?: string; subject?: string; body?: string } | null = null): void {
    composePrefill = prefill;
    composeOpen = true;
  }

  function replyTo(message: GmailMessage): void {
    const from = parseAddress(message.headers?.from);
    const subject = message.headers?.subject || '';
    openCompose({
      to: from.email,
      subject: subject.toLowerCase().startsWith('re:') ? subject : `Re: ${subject}`,
    });
  }

  async function handleSend(payload: GmailSendInput): Promise<void> {
    if (sending) return;
    sending = true;
    try {
      await api.gmail.send(payload);
      showNotification($t('gmail.sendOk'), 'success');
      composeOpen = false;
      composePrefill = null;
      void refreshList();
    } catch (e) {
      logger.error(e);
      if (isGmailAuthError(e)) void loadStatus();
      showNotification($t('gmail.sendError'), 'error');
    } finally {
      sending = false;
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────
  onMount(() => {
    void loadStatus();
  });

  onDestroy(() => {
    destroyed = true;
    stopConnectPolling();
    clearTimeout(debounceTimer);
  });
</script>

<div class="gmail-page">
  <div class="gmail-header">
    <div>
      <h3>{$t('gmail.title')}</h3>
      <span class="caption">{$t('gmail.subtitle')}</span>
    </div>
    <div class="gmail-actions">
      {#if connected && canSend}
        <button class="compose-btn" onclick={() => openCompose()}>
          <Send size={13} /> {$t('gmail.compose')}
        </button>
      {/if}
      <button class="filter-chip refresh" onclick={() => void refreshList()} aria-label="refresh">
        <RefreshCw size={13} />
      </button>
    </div>
  </div>

  {#if statusLoading}
    <div class="loading-state caption">{$t('gmail.loading')}</div>
  {:else if !connected}
    <div class="empty-wrap">
      <EmptyState
        title={$t('gmail.connectTitle')}
        message={connectError || $t('gmail.connectHint')}
        actionLabel={connecting ? $t('gmail.connecting') : $t('gmail.connectCta')}
        onAction={() => void connectGoogle()}
      >
        {#snippet icon()}<Inbox size={44} />{/snippet}
      </EmptyState>
      <div class="connect-secondary">
        <button class="filter-chip" onclick={openSettings}>{$t('gmail.openSettings')}</button>
      </div>
    </div>
  {:else}
    {#if needsReconnect}
      <div class="reconnect-banner" role="alert">
        <TriangleAlert size={15} />
        <span>{$t('gmail.scopeWarning')}</span>
        <button class="filter-chip" onclick={() => void connectGoogle()} disabled={connecting}>
          {connecting ? $t('gmail.connecting') : $t('gmail.reconnect')}
        </button>
      </div>
    {/if}

    <div class="gmail-filters">
      <div class="search-wrap">
        <Search size={15} />
        <input
          class="search-input"
          type="text"
          placeholder={$t('gmail.searchPlaceholder')}
          aria-label={$t('gmail.searchPlaceholder')}
          bind:value={searchQuery}
          oninput={onSearchInput}
        />
      </div>
      <div class="label-chips">
        {#each LABEL_FILTERS as label (label.id)}
          <button
            class="filter-chip"
            class:active={labelFilter === label.id}
            onclick={() => pickLabel(label.id)}
          >
            {$t(`gmail.labels.${label.key}`)}
            {#if label.id === 'UNREAD' && unreadInView > 0}
              <span class="unread-count">{unreadInView}</span>
            {/if}
          </button>
        {/each}
      </div>
    </div>

    {#if selected}
      <GmailMessageView
        message={selected}
        {canModify}
        {canSend}
        loading={detailLoading}
        onBack={closeMessage}
        onArchive={(m) => void runLabelAction(m, 'archive')}
        onTrash={(m) => void runLabelAction(m, 'trash')}
        onUntrash={(m) => void runLabelAction(m, 'untrash')}
        onToggleRead={toggleRead}
        onReply={replyTo}
      />
    {:else if detailLoading}
      <div class="loading-state caption">{$t('gmail.loading')}</div>
    {:else if listLoading && messages.length === 0}
      <div class="loading-state caption">{$t('gmail.loading')}</div>
    {:else if loadError}
      <div class="empty-wrap">
        <EmptyState
          title={$t('gmail.loadError')}
          actionLabel={$t('common.retry')}
          onAction={() => {
            void refreshList();
          }}
        >
          {#snippet icon()}<RefreshCw size={44} />{/snippet}
        </EmptyState>
      </div>
    {:else if messages.length === 0}
      <div class="empty-wrap">
        <EmptyState
          title={searchQuery.trim() ? $t('gmail.noResults') : $t('gmail.empty')}
          message={searchQuery.trim() ? '' : $t('gmail.emptyHint')}
        >
          {#snippet icon()}<Inbox size={44} />{/snippet}
        </EmptyState>
      </div>
    {:else}
      <GmailMessageList
        {messages}
        {details}
        {canModify}
        {labelFilter}
        onOpen={(m) => void openMessage(m)}
        onArchive={(m) => void runLabelAction(m, 'archive')}
        onTrash={(m) => void runLabelAction(m, 'trash')}
        onUntrash={(m) => void runLabelAction(m, 'untrash')}
        onToggleRead={toggleRead}
      />
      {#if nextPageToken}
        <div class="load-more">
          <button class="filter-chip" onclick={() => void refreshList(true)} disabled={loadingMore}>
            {loadingMore ? $t('gmail.loading') : $t('gmail.loadMore')}
          </button>
        </div>
      {/if}
      {#if totalEstimate != null && totalEstimate > messages.length}
        <div class="caption more-hint">
          {$t('gmail.showingCount', { values: { shown: messages.length, total: totalEstimate } })}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<GmailComposeDialog
  open={composeOpen}
  prefill={composePrefill}
  {sending}
  onClose={() => {
    composeOpen = false;
    composePrefill = null;
  }}
  onSend={(payload) => void handleSend(payload)}
/>

<style>
  .gmail-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 8px;
  }

  .gmail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  h3 {
    margin: 0;
    color: var(--text-primary);
  }

  .gmail-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .compose-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 12px;
    border: none;
    border-radius: 999px;
    background: var(--accent);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }

  .compose-btn:hover {
    opacity: 0.9;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .filter-chip:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .filter-chip:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .filter-chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg-primary, #fff);
  }

  .unread-count {
    background: var(--xp, #e8b931);
    color: #1a1a1a;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    padding: 0 6px;
  }

  .gmail-filters {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .search-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-muted);
    background: var(--surface);
  }

  .search-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-size: 13px;
  }
  .search-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
    border-radius: var(--r-sm);
  }

  .label-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .reconnect-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: 1px solid var(--xp, #e8b931);
    border-radius: 10px;
    background: color-mix(in srgb, var(--xp, #e8b931) 10%, transparent);
    color: var(--text-primary);
    font-size: 12px;
  }

  .reconnect-banner span {
    flex: 1;
  }

  .loading-state {
    text-align: center;
    padding: 24px 0;
    color: var(--text-muted);
  }

  .empty-wrap {
    padding: 24px 0;
  }

  .connect-secondary {
    display: flex;
    justify-content: center;
    margin-top: -12px;
  }

  .load-more {
    display: flex;
    justify-content: center;
  }

  .more-hint {
    text-align: center;
    color: var(--text-muted);
  }
</style>
