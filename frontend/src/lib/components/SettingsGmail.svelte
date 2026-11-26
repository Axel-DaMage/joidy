<script lang="ts">
  import { api, type GmailStatus, type GmailWatchState } from '$lib/api';
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

  // Refetch on mount and whenever the parent Google connection flips — a fresh
  // connect may upgrade the granted Gmail scopes (#42).
  $effect(() => {
    void googleConnected;
    void load();
  });

  async function load(): Promise<void> {
    loading = true;
    try {
      status = await api.gmail.status();
    } catch (e) {
      logger.error(e);
      status = null;
    } finally {
      loading = false;
    }
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
  {:else if !connected}
    <p class="hint">{$t('gmail.settings.notConnectedHint')}</p>
  {:else}
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

    {#if missingCaps}
      <p class="hint warn">{$t('gmail.settings.missingCaps')}</p>
      {#if onReconnect}
        <button class="link-btn" onclick={onReconnect}>{$t('gmail.reconnect')}</button>
      {/if}
    {/if}

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
