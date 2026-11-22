<script lang="ts">
  // Google Contacts status/connect row for Settings → Integrations (#43).
  // Consumes GET /integrations/contacts/status via the shared contacts store
  // and reuses the Google OAuth flow (the contacts scope ships in the same
  // consent — users granted before the scope bump must re-consent once for
  // write access; reads keep working with contacts.readonly).
  import { onMount, onDestroy } from 'svelte';
  import { contactsStatus, loadContactsStatus } from '$lib/stores/contacts';
  import { startGoogleConnect, type GoogleConnectHandle } from '$lib/utils/googleConnect';
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();

  let connecting = $state(false);
  let connectHandle: GoogleConnectHandle | null = null;

  const isConnected = $derived(!!$contactsStatus?.connected);
  const needsReadScope = $derived(isConnected && $contactsStatus?.contacts_read === false);
  const readOnly = $derived(isConnected && $contactsStatus?.contacts_write === false);
  const fullyReady = $derived(isConnected && $contactsStatus?.contacts_write !== false);

  onMount(async () => {
    try {
      await loadContactsStatus();
    } catch (e) {
      logger.error(e);
    }
  });

  onDestroy(() => {
    connectHandle?.cancel();
  });

  /** Same pre-auth credential persistence as SettingsGoogle (#1148). */
  async function persistGoogleCredentials(): Promise<void> {
    const creds: Record<string, string> = {};
    if (systemConfig.google_client_id?.trim())
      creds.google_client_id = systemConfig.google_client_id.trim();
    if (systemConfig.google_client_secret?.trim())
      creds.google_client_secret = systemConfig.google_client_secret.trim();
    if (systemConfig.google_redirect_uri?.trim())
      creds.google_redirect_uri = systemConfig.google_redirect_uri.trim();
    if (Object.keys(creds).length > 0) {
      await api.config.update(creds);
    }
  }

  async function connect(): Promise<void> {
    if (connecting) return;
    connecting = true;
    connectHandle = startGoogleConnect({
      persistCredentials: persistGoogleCredentials,
      isReady: async () => {
        const s = await loadContactsStatus();
        return !!(s.connected && s.contacts_read !== false);
      },
    });
    const result = await connectHandle.done;
    connectHandle = null;
    connecting = false;
    if (result === 'connected') {
      showNotification($t('contacts.settings.connectedOk'), 'success');
    } else if (result === 'timeout') {
      showNotification($t('contacts.settings.connectTimeout'), 'error');
    } else if (result === 'error') {
      showNotification($t('contacts.settings.connectError'), 'error');
    }
  }
</script>

<div class="row settings-contacts">
  <div class="row-label">
    <span>Google Contacts</span>
    {#if fullyReady}
      <span class="status-badge ok">{$t('contacts.settings.connected')}</span>
    {:else if readOnly}
      <span class="status-badge warn">{$t('contacts.settings.readOnly')}</span>
    {:else if needsReadScope}
      <span class="status-badge warn">{$t('contacts.settings.noScope')}</span>
    {:else if isConnected}
      <span class="status-badge">{$t('contacts.settings.connected')}</span>
    {:else if $contactsStatus === null}
      <span class="status-badge muted">…</span>
    {:else}
      <span class="status-badge muted">{$t('contacts.settings.disconnected')}</span>
    {/if}
  </div>
  <div class="row-actions">
    {#if connecting}
      <span class="connecting-hint">{$t('contacts.settings.connecting')}</span>
    {:else if !isConfigured('google_client_id') && !isConnected}
      <span class="connecting-hint">{$t('contacts.settings.needsGoogleConfig')}</span>
    {:else if !isConnected || needsReadScope || readOnly}
      <button class="link-btn" onclick={connect}>
        {isConnected ? $t('contacts.settings.reconnect') : $t('contacts.settings.connect')}
      </button>
    {:else}
      <a class="link-btn link-btn-ghost" href="/contactos">{$t('contacts.settings.open')}</a>
    {/if}
  </div>
</div>
{#if readOnly}
  <p class="hint">{$t('contacts.settings.readOnlyHint')}</p>
{/if}

<style>
  .settings-contacts {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .row-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .status-badge {
    font-size: 10px;
    font-family: var(--font-mono);
    padding: 2px 7px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--text-muted);
  }

  .status-badge.ok {
    color: var(--success);
    border-color: color-mix(in srgb, var(--success) 40%, transparent);
  }

  .status-badge.warn {
    color: var(--xp, #e8b931);
    border-color: color-mix(in srgb, var(--xp, #e8b931) 40%, transparent);
  }

  .status-badge.muted {
    opacity: 0.7;
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
    text-decoration: none;
    display: inline-block;
  }

  .link-btn:hover {
    opacity: 0.9;
  }

  .link-btn-ghost {
    background: transparent;
    color: var(--accent);
    border: 1px solid var(--border);
  }

  .connecting-hint {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin: 0 0 4px;
  }
</style>
