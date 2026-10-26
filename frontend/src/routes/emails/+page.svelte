<script lang="ts">
  import { onMount } from 'svelte';
  import { api, type EmailSummary, type EmailAccountStats } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { Search, Inbox, Star, RefreshCw } from 'lucide-svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { t } from 'svelte-i18n';

  let emails: EmailSummary[] = $state([]);
  let total = $state(0);
  let accounts: EmailAccountStats[] = $state([]);
  let loading = $state(true);

  let searchQuery = $state('');
  let accountFilter = $state<string | null>(null);
  let onlyUnread = $state(true);
  let onlyImportant = $state(false);

  let debounceTimer: ReturnType<typeof setTimeout> | undefined;

  const dtFormatter = new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

  function senderName(email: EmailSummary): string {
    if (!email.sender) return '(sin remitente)';
    const match = email.sender.match(/^(.*?)\s*<.*>$/);
    return (match?.[1] || email.sender).trim();
  }

  function senderAddress(email: EmailSummary): string {
    const match = email.sender?.match(/<(.*?[^>])>/);
    return (match?.[1] || email.sender || '').trim();
  }

  function formatWhen(email: EmailSummary): string {
    if (!email.received_at) return '';
    const date = new Date(email.received_at);
    if (Number.isNaN(date.getTime())) return '';
    const today = new Date();
    return date.toDateString() === today.toDateString()
      ? dtFormatter.format(date)
      : `${dtFormatter.format(date)} · ${date.toLocaleDateString(undefined, { day: '2-digit', month: 'short' })}`;
  }

  async function refresh(): Promise<void> {
    try {
      const inbox = await api.emails.list({
        unread: onlyUnread ? true : undefined,
        important: onlyImportant ? true : undefined,
        account: accountFilter ?? undefined,
        q: searchQuery.trim() || undefined,
        limit: 200,
      });
      emails = inbox.items;
      total = inbox.total;
    } catch (e) {
      logger.error(e);
    } finally {
      loading = false;
    }
  }

  function onSearchInput(): void {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(refresh, 300);
  }

  async function toggleRead(email: EmailSummary): Promise<void> {
    try {
      const updated = await api.emails.patch(email.id, { unread: !email.unread });
      emails = emails.map((e) => (e.id === email.id ? updated : e));
    } catch (e) {
      logger.error(e);
    }
  }

  async function toggleImportant(email: EmailSummary): Promise<void> {
    try {
      const updated = await api.emails.patch(email.id, { important: !email.important });
      emails = emails.map((e) => (e.id === email.id ? updated : e));
    } catch (e) {
      logger.error(e);
    }
  }

  async function removeEmail(email: EmailSummary): Promise<void> {
    try {
      await api.emails.remove(email.id);
      emails = emails.filter((e) => e.id !== email.id);
      accounts = accounts.map((a) =>
        a.account === email.account
          ? { ...a, total: a.total - 1, unread: a.unread - (email.unread ? 1 : 0) }
          : a
      );
      total = Math.max(total - 1, 0);
    } catch (e) {
      logger.error(e);
    }
  }

  function pickAccount(account: string | null): void {
    accountFilter = accountFilter === account ? null : account;
    refresh();
  }

  function toggleUnreadFilter(): void {
    onlyUnread = !onlyUnread;
    refresh();
  }

  function toggleImportantFilter(): void {
    onlyImportant = !onlyImportant;
    refresh();
  }

  onMount(async () => {
    try {
      [accounts] = await Promise.all([api.emails.accounts()]);
    } catch (e) {
      logger.error(e);
    }
    await refresh();
  });
</script>

<div class="emails-page">
  <div class="emails-header">
    <div>
      <h3>{$t('emails.title')}</h3>
      <span class="caption">{$t('emails.subtitle')}</span>
    </div>
    <div class="emails-actions">
      <button class="filter-chip" class:active={onlyUnread} onclick={toggleUnreadFilter}>
        {$t('emails.unreadOnly')}
      </button>
      <button class="filter-chip" class:active={onlyImportant} onclick={toggleImportantFilter}>
        <Star size={13} /> {$t('emails.importantOnly')}
      </button>
      <button class="filter-chip refresh" onclick={refresh} aria-label="refresh">
        <RefreshCw size={13} />
      </button>
    </div>
  </div>

  {#if accounts.length > 0}
    <div class="account-chips">
      <button class="filter-chip" class:active={accountFilter === null} onclick={() => pickAccount(null)}>
        {$t('emails.allAccounts')}
      </button>
      {#each accounts as account (account.account)}
        <button class="filter-chip" class:active={accountFilter === account.account} onclick={() => pickAccount(account.account)}>
          {account.account}
          {#if account.unread > 0}<span class="unread-count">{account.unread}</span>{/if}
        </button>
      {/each}
    </div>
  {/if}

  <div class="emails-search">
    <div class="search-wrap">
      <Search size={15} />
      <input
        class="search-input"
        type="text"
        placeholder={$t('emails.searchPlaceholder')}
        bind:value={searchQuery}
        oninput={onSearchInput}
      />
    </div>
  </div>

  {#if loading}
    <div class="loading-state caption">...</div>
  {:else if total === 0}
    <div class="empty-wrap">
      <EmptyState
        title={onlyImportant ? $t('emails.emptyImportant') : onlyUnread ? $t('emails.emptyUnread') : $t('emails.emptyAll')}
        message={$t('emails.syncHint')}
      >
        {#snippet icon()}<Inbox size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else if emails.length === 0}
    <div class="loading-state caption">{$t('emails.noResults')}</div>
  {:else}
    <div class="emails-list">
      {#each emails as email (email.id)}
        <div class="email-item" class:unread={email.unread}>
          <div class="email-main">
            <div class="email-top">
              <span class="sender" class:unread-text={email.unread}>{senderName(email)}</span>
              <span class="when">{formatWhen(email)}</span>
            </div>
            <div class="subject" class:unread-text={email.unread}>
              {#if email.important}<span class="star-wrap"><Star size={11} /></span>{/if}
              {email.subject || '(sin asunto)'}
            </div>
            <div class="snippet caption">
              {email.snippet || senderAddress(email)}
            </div>
          </div>
          <div class="email-side">
            {#if email.unread}<span class="dot unread-dot" title={$t('emails.unreadOnly')}></span>{/if}
            <div class="email-ops">
              <button onclick={() => toggleRead(email)} title={email.unread ? $t('emails.markRead') : $t('emails.markUnread')}>
                {email.unread ? $t('emails.markRead') : $t('emails.markUnread')}
              </button>
              <button onclick={() => toggleImportant(email)} title={$t('emails.toggleImportant')}>
                <span class="star-wrap" class:idle={!email.important}><Star size={14} /></span>
              </button>
              <button onclick={() => removeEmail(email)} title={$t('emails.deleted')}>×</button>
            </div>
          </div>
        </div>
      {/each}
    </div>
    {#if total > emails.length}
      <div class="caption more-hint">+{total - emails.length} · limit 200</div>
    {/if}
  {/if}
</div>

<style>
  .emails-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 720px;
    margin: 0 auto;
    padding: 16px 8px;
  }

  .emails-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  h3 {
    margin: 0;
    color: var(--text-primary);
  }

  .emails-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
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

  .filter-chip:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .filter-chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg-primary, #fff);
  }

  .account-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .unread-count {
    background: var(--xp, #e8b931);
    color: #1a1a1a;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    padding: 0 6px;
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

  .emails-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    background: var(--surface);
  }

  .email-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }

  .email-item:last-child {
    border-bottom: none;
  }

  .email-item.unread {
    background: color-mix(in srgb, var(--accent) 6%, transparent);
  }

  .email-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .email-top {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }

  .sender {
    font-size: 12px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .when {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-muted);
  }

  .subject {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .unread-text {
    font-weight: 700;
    color: var(--text-primary);
  }

  .snippet {
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .star-wrap {
    display: inline-flex;
    color: var(--xp, #e8b931);
    flex-shrink: 0;
  }

  .star-wrap.idle {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .email-side {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .unread-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
  }

  .email-ops {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .email-item:hover .email-ops {
    opacity: 1;
  }

  .email-ops button {
    display: inline-flex;
    align-items: center;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 11px;
    padding: 3px 8px;
    cursor: pointer;
  }

  .email-ops button:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .loading-state {
    text-align: center;
    padding: 24px 0;
    color: var(--text-muted);
  }

  .empty-wrap {
    padding: 24px 0;
  }

  .more-hint {
    text-align: center;
    color: var(--text-muted);
  }
</style>
