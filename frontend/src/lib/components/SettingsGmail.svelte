<script lang="ts">
  import { api, type EmailAccount, type GmailStatus, type GmailWatchState } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { locale } from '$lib/stores/locale';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';

  interface Props {
    /** Parent's live Google-connection flag — refetches status on change. */
    googleConnected: boolean;
    /** Re-runs the Google OAuth flow (owned by SettingsGoogle). */
    onReconnect?: () => void;
  }

  let { googleConnected, onReconnect }: Props = $props();

  let status = $state<GmailStatus | null>(null);
  let loading = $state(true);
  let watchBusy = $state(false);

  // ── Per-account mailboxes (#1659) ─────────────────────────────────────────
  let accounts = $state<EmailAccount[]>([]);
  let connectBusy = $state(false);
  let busyAccountId = $state<number | null>(null);
  let connectPoll: ReturnType<typeof setInterval> | null = null;
  let connectTimeout: ReturnType<typeof setTimeout> | null = null;

  // Refetch on mount and whenever the parent Google connection flips — a fresh
  // connect may upgrade the granted Gmail scopes (#42).
  $effect(() => {
    void googleConnected;
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    try {
      const [s, list] = await Promise.all([api.gmail.status(), api.gmail.accounts.list()]);
      status = s;
      accounts = list;
    } catch (e) {
      logger.error(e);
      status = null;
    } finally {
      loading = false;
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

  /** Popup OAuth to connect an additional mailbox — polls the accounts list
   * for a new/changed row (same popup+poll pattern as the page). */
  async function connectAccount(): Promise<void> {
    if (connectBusy) return;
    connectBusy = true;
    stopConnectPolling();
    try {
      const before = new Map(accounts.map((a) => [a.id, a.updated_at]));
      const { url } = await api.gmail.accounts.authUrl();
      window.open(url, '_blank', 'noopener,noreferrer');
      connectPoll = setInterval(async () => {
        try {
          const list = await api.gmail.accounts.list();
          const changed = list.some((a) => !before.has(a.id) || a.updated_at !== before.get(a.id));
          if (changed) {
            stopConnectPolling();
            connectBusy = false;
            accounts = list;
            showNotification($t('gmail.connectOk'), 'success');
          }
        } catch {
          /* transient poll failure — keep waiting */
        }
      }, 3000);
      connectTimeout = setTimeout(() => {
        stopConnectPolling();
        connectBusy = false;
      }, 300000);
    } catch (e) {
      logger.error(e);
      showNotification($t('gmail.connectError'), 'error');
      connectBusy = false;
    }
  }

  async function disconnectAccount(account: EmailAccount): Promise<void> {
    if (busyAccountId !== null) return;
    busyAccountId = account.id;
    try {
      await api.gmail.accounts.disconnect(account.id);
      accounts = accounts.filter((a) => a.id !== account.id);
      showNotification($t('gmail.accounts.disconnected'), 'info');
    } catch (e) {
      logger.error(e);
      showNotification($t('gmail.accounts.disconnectError'), 'error');
    } finally {
      busyAccountId = null;
    }
  }

  function accountLabel(account: EmailAccount): string {
    const address = account.email_address === '__pending__' ? '' : account.email_address;
    return account.display_name || address || $t('gmail.accounts.pending');
  }

  const connected = $derived(status?.connected === true);
  const missingCaps = $derived(
    connected &&
      (status?.gmail_read === false || status?.gmail_modify === false || status?.gmail_send === false)
  );
  const watchState = $derived<GmailWatchState | null>(status?.watch.state ?? null);

  function capLabel(value: boolean | null | undefined): string {
    return value === true ? $t('gmail.settings.capOk') : value === false ? $t('gmail.settings.capMissing') : '—';
  }

  async function registerWatch(): Promise<void> {
    watchBusy = true;
    try {
      await api.gmail.watchRegister();
      showNotification($t('gmail.settings.watchOk'), 'success');
      await load();
    } catch (e) {
      logger.error(e);
      showNotification($t('gmail.settings.watchError'), 'error');
    } finally {
      watchBusy = false;
    }
  }

  async function stopWatch(): Promise<void> {
    watchBusy = true;
    try {
      await api.gmail.watchStop();
      showNotification($t('gmail.settings.watchStopped'), 'info');
      await load();
    } catch (e) {
      logger.error(e);
      showNotification($t('gmail.settings.watchError'), 'error');
    } finally {
      watchBusy = false;
    }
  }
</script>

<div class="gmail-settings">
  <div class="row-label">
    <span>{$t('gmail.settings.title')}</span>
    {#if connected}
      <span class="configured-badge">✓</span>
    {/if}
  </div>

  {#if loading}
    <p class="hint">{$t('gmail.loading')}</p>
  {:else if !connected && accounts.length === 0}
    <p class="hint">{$t('gmail.settings.notConnectedHint')}</p>
  {:else}
    {#if connected}
      <div class="cap-row">
      <span class="cap" class:cap-ok={status?.gmail_read === true} class:cap-miss={status?.gmail_read === false}>
        {$t('gmail.settings.capRead')} · {capLabel(status?.gmail_read)}
      </span>
      <span class="cap" class:cap-ok={status?.gmail_modify === true} class:cap-miss={status?.gmail_modify === false}>
        {$t('gmail.settings.capModify')} · {capLabel(status?.gmail_modify)}
      </span>
      <span class="cap" class:cap-ok={status?.gmail_send === true} class:cap-miss={status?.gmail_send === false}>
        {$t('gmail.settings.capSend')} · {capLabel(status?.gmail_send)}
      </span>
      </div>
    {/if}

    {#if missingCaps}
      <p class="hint warn">{$t('gmail.settings.missingCaps')}</p>
      {#if onReconnect}
        <button class="link-btn" onclick={onReconnect}>{$t('gmail.reconnect')}</button>
      {/if}
    {/if}

    <!-- Connected mailboxes (#1659) — each account holds its own OAuth grant,
         sync cursor and watch registration. -->
    <div class="accounts-block">
      <span class="watch-title">{$t('gmail.accounts.title')}</span>
      {#if accounts.length === 0}
        <span class="hint">{$t('gmail.accounts.none')}</span>
      {:else}
        {#each accounts as account (account.id)}
          <div class="account-row">
            <span class="account-name" class:inactive={!account.is_active}>{accountLabel(account)}</span>
            <span class="account-actions">
              <button class="link-btn ghost" onclick={() => void disconnectAccount(account)} disabled={busyAccountId !== null}>
                {busyAccountId === account.id ? $t('gmail.accounts.disconnecting') : $t('gmail.accounts.disconnect')}
              </button>
            </span>
          </div>
        {/each}
      {/if}
      <button class="link-btn ghost" onclick={() => void connectAccount()} disabled={connectBusy}>
        {connectBusy ? $t('gmail.connecting') : $t('gmail.accounts.connect')}
      </button>
    </div>

    {#if connected}
      <div class="watch-block">
      <span class="watch-title">{$t('gmail.settings.watchTitle')}</span>
      {#if status?.watch.configured}
        {#if watchState?.expiration}
          <span class="hint">
            {$t('gmail.settings.watchActive', {
              values: { date: new Date(watchState.expiration).toLocaleString($locale) },
            })}
          </span>
        {:else}
          <span class="hint">{$t('gmail.settings.watchNone')}</span>
        {/if}
        <span class="watch-actions">
          {#if watchState}
            <button class="link-btn ghost" onclick={stopWatch} disabled={watchBusy}>
              {$t('gmail.settings.watchStop')}
            </button>
          {:else}
            <button class="link-btn ghost" onclick={registerWatch} disabled={watchBusy}>
              {$t('gmail.settings.watchRegister')}
            </button>
          {/if}
        </span>
      {:else}
        <span class="hint">{$t('gmail.settings.watchNotConfigured')}</span>
      {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .gmail-settings {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 6px 0 10px;
    border-top: 1px dashed var(--border-light, var(--border));
    margin-top: 4px;
  }

  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.5;
    margin: 0;
  }

  .hint.warn {
    color: var(--xp, #e8b931);
  }

  .configured-badge {
    font-size: 10px;
    color: var(--success);
  }

  .cap-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .cap {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--text-muted);
  }

  .cap-ok {
    color: var(--success);
    border-color: color-mix(in srgb, var(--success) 40%, transparent);
  }

  .cap-miss {
    color: var(--xp, #e8b931);
    border-color: color-mix(in srgb, var(--xp, #e8b931) 40%, transparent);
  }

  .link-btn {
    background: var(--accent);
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: var(--r);
    font-size: 11px;
    cursor: pointer;
    font-family: var(--font-mono);
    align-self: flex-start;
  }

  .link-btn:hover {
    opacity: 0.9;
  }

  .link-btn.ghost {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
  }

  .link-btn.ghost:hover {
    background: var(--hover);
    color: var(--text-primary);
  }

  .link-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .accounts-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 4px;
  }

  .account-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 4px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
  }

  .account-name {
    font-size: 11px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .account-name.inactive {
    opacity: 0.5;
  }

  .account-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  .accounts-block > .link-btn {
    align-self: flex-start;
  }

  .watch-block {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding-top: 4px;
  }

  .watch-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .watch-actions {
    margin-left: auto;
  }
</style>
