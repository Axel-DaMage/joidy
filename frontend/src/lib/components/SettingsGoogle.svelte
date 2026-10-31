<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { ExternalLink } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();

  let googleConnected = $state(false);
  let googleConnecting = $state(false);
  let googleError = $state('');
  let testingGmail = $state(false);
  let showAdvancedGoogle = $state(false);

  let googlePollInterval: ReturnType<typeof setInterval> | null = null;
  let googlePollTimeout: ReturnType<typeof setTimeout> | null = null;
  let destroyed = false;

  onMount(async () => {
    await checkGoogleStatus();
  });

  onDestroy(() => {
    destroyed = true;
    if (googlePollInterval) {
      clearInterval(googlePollInterval);
      googlePollInterval = null;
    }
    if (googlePollTimeout) {
      clearTimeout(googlePollTimeout);
      googlePollTimeout = null;
    }
  });

  async function checkGoogleStatus() {
    try {
      const status = await api.google.status();
      googleConnected = status.connected;
    } catch {
      googleConnected = false;
    }
  }

  function stopPolling() {
    if (googlePollInterval) {
      clearInterval(googlePollInterval);
      googlePollInterval = null;
    }
    if (googlePollTimeout) {
      clearTimeout(googlePollTimeout);
      googlePollTimeout = null;
    }
  }

  async function startGoogleAuth() {
    googleConnecting = true;
    googleError = '';
    try {
      // Persist credentials BEFORE opening the consent popup: the /auth
      // endpoint reads them from settings, and an unsaved form would 400
      // with "Google OAuth is not configured" (#1148).
      const creds: Record<string, string> = {};
      if (systemConfig.google_client_id?.trim()) creds.google_client_id = systemConfig.google_client_id.trim();
      if (systemConfig.google_client_secret?.trim()) creds.google_client_secret = systemConfig.google_client_secret.trim();
      if (systemConfig.google_redirect_uri?.trim()) creds.google_redirect_uri = systemConfig.google_redirect_uri.trim();
      if (Object.keys(creds).length > 0) {
        await api.config.update(creds);
      }

      const data = await api.google.authUrl();
      window.open(data.url, '_blank');
      // The callback persists the tokens server-side; poll until status flips.
      googlePollInterval = setInterval(async () => {
        await checkGoogleStatus();
        if (destroyed || googlePollInterval === null) return;
        if (googleConnected) {
          stopPolling();
          googleConnecting = false;
          showNotification('Google conectado correctamente', 'success');
        }
      }, 3000);
      googlePollTimeout = setTimeout(() => {
        stopPolling();
        googleConnecting = false;
        if (!googleConnected && !destroyed) {
          googleError = 'Se agotó el tiempo de espera (5 min). Intenta de nuevo.';
        }
      }, 300000);
    } catch (e: any) {
      googleError = e.message || 'Error iniciando autenticación con Google';
      googleConnecting = false;
    }
  }

  async function disconnectGoogle() {
    stopPolling();
    googleConnecting = false;
    try {
      await api.google.disconnect();
      googleConnected = false;
      showNotification('Google desconectado', 'info');
    } catch (e: any) {
      googleError = e.message || 'Error al desconectar Google';
    }
  }

  async function testGmail() {
    testingGmail = true;
    try {
      await api.google.gmail(10);
      showNotification('Gmail OK: token válido y leído con éxito', 'success');
    } catch (e: any) {
      showNotification('Gmail falló: ' + (e.message || 'error'), 'error');
    } finally {
      testingGmail = false;
    }
  }
</script>

<!-- Google OAuth (GitHub-style one-click flow) -->
<div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
  <div class="row-label">
    <span>Google (Calendar · Tasks · Gmail · Contacts)</span>
    {#if googleConnected}
      <span class="configured-badge">✓</span>
    {:else if isConfigured('google_client_id')}
      <span class="configured-badge" style="color:var(--text-muted)">+ configurado</span>
    {/if}
  </div>

  <div style="display: flex; gap: 8px; flex-wrap: wrap;">
    {#if googleConnecting}
      <span class="mono" style="font-size: 12px; color: var(--text-muted);">
        Abre la ventana de Google y da permiso… (esperando hasta 5 min)
      </span>
    {:else if googleConnected}
      <button class="link-btn" onclick={testGmail} disabled={testingGmail}>
        {testingGmail ? 'Probando...' : 'Probar Gmail'}
      </button>
      <button class="link-btn disconnect-btn" onclick={disconnectGoogle}>Desconectar</button>
    {:else if isConfigured('google_client_id')}
      <button class="link-btn" onclick={startGoogleAuth}>Conectar con Google</button>
    {:else}
      <button
        class="link-btn"
        onclick={() => {
          showAdvancedGoogle = true;
          showNotification('Pega tu Client ID y Secret de Google y guarda', 'info');
        }}
      >
        Configurar
      </button>
    {/if}
  </div>

  {#if googleError}
    <p class="hint" style="color: var(--danger); margin: 0;">{googleError}</p>
  {/if}

    {#if showAdvancedGoogle}
    <div
      style="display: flex; flex-direction: column; gap: 8px; border-left: 2px solid var(--border); padding-left: 12px; margin-left: 4px;"
    >
      <p class="hint" style="margin: 0; font-weight: 500;">
        Credenciales avanzadas de Google (se guardan automáticamente al Conectar, o con Ctrl+S):
      </p>
      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div class="row-label" style="font-size: 11px;">
          <a
            href="https://console.cloud.google.com/apis/credentials"
            target="_blank"
            rel="noopener noreferrer"
            class="external-setting-link"
            title="Abrir Google Cloud Console — credenciales OAuth"
          >
            <span>Google OAuth Client ID</span>
            <ExternalLink size={10} />
          </a>
          {#if isConfigured('google_client_id') || systemConfig.google_client_id}<span
              class="configured-badge">✓</span
            >{/if}
        </div>
        <input
          type="text"
          class="setting-input mono"
          style="font-size: 11px; padding: 4px 8px;"
          placeholder={isConfigured('google_client_id')
            ? '•••••••••••••••••••••••• (configurado)'
            : '1234567890-abc.apps.googleusercontent.com'}
          bind:value={systemConfig.google_client_id}
        />
      </div>

      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div class="row-label" style="font-size: 11px;">
          <a
            href="https://console.cloud.google.com/apis/credentials"
            target="_blank"
            rel="noopener noreferrer"
            class="external-setting-link"
          >
            <span>Google OAuth Client Secret</span>
            <ExternalLink size={10} />
          </a>
          {#if isConfigured('google_client_secret') || systemConfig.google_client_secret}<span
              class="configured-badge">✓</span
            >{/if}
        </div>
        <input
          type="password"
          class="setting-input mono"
          style="font-size: 11px; padding: 4px 8px;"
          placeholder={isConfigured('google_client_secret') && !systemConfig.google_client_secret
            ? '•••••••••••••••• (configurado)'
            : 'GOCSPX-...'}
          bind:value={systemConfig.google_client_secret}
        />
      </div>

      <div style="display: flex; flex-direction: column; gap: 4px;">
        <div class="row-label" style="font-size: 11px;">
          <span>Redirect URI</span>
        </div>
        <input
          type="text"
          class="setting-input mono"
          style="font-size: 11px; padding: 4px 8px;"
          placeholder="http://localhost:8000/integrations/google/callback"
          bind:value={systemConfig.google_redirect_uri}
        />
        <p class="hint" style="margin: 0;">
          Registra este URI exacto en tu OAuth client de Google Cloud (Authorized redirect
          URIs). Scopes: Calendar, Tasks, Gmail y Contacts (solo lectura).
        </p>
      </div>
    </div>
  {/if}
</div>

<style>
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
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
    line-height: 1.6;
    margin-top: 8px;
  }
  .setting-input {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 10px;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
    width: 100%;
  }
  .setting-input:focus {
    outline: none;
  }
  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
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
  }
  .link-btn:hover {
    opacity: 0.9;
  }
  .disconnect-btn {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
  }
  .disconnect-btn:hover {
    background: var(--hover);
    border-color: var(--text-muted);
    color: var(--text-primary);
  }
  .external-setting-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--accent);
    text-decoration: none;
    font-size: 11px;
  }
  .external-setting-link:hover {
    text-decoration: underline;
  }
</style>
