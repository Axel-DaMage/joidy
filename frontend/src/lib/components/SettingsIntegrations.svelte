<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import SettingsGithub from './SettingsGithub.svelte';
  import { devMode } from '$lib/stores/settings';
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
  let stravaConnected = $state(false);
  let stravaName = $state('');
  let gmailConnected = $state(false);
  let gmailEmail = $state('');

  async function openGoogleCalendarLink() {
    window.open('https://calendar.google.com', '_blank');
  }
  async function openGoogleTasksLink() {
    window.open('https://tasksboard.com', '_blank');
  }
  async function openGoogleContactsLink() {
    window.open('https://contacts.google.com', '_blank');
  }
  async function openStravaLink() {
    window.open('https://strava.com', '_blank');
  }
  async function openGmailLink() {
    window.open('https://mail.google.com', '_blank');
  }

  onMount(async () => {
    await checkGoogleStatus();
  });

  let googlePollInterval: ReturnType<typeof setInterval> | null = null;
  let googlePollTimeout: ReturnType<typeof setTimeout> | null = null;
  // Set in onDestroy so in-flight async poll callbacks stop rescheduling and
  // stop mutating state after teardown (#1003).
  let destroyed = false;

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

  async function startGoogleAuth() {
    googleConnecting = true;
    googleError = '';
    try {
      const data = await api.google.authUrl();
      window.open(data.url, '_blank');
      // Listen for the OAuth callback via URL params (popup or redirect)
      // The user will be redirected back with ?code=xxx
      // We poll for connection status
      googlePollInterval = setInterval(async () => {
        await checkGoogleStatus();
        // Stop mutating state once the panel is gone (#1003).
        if (destroyed || googlePollInterval === null) return;
        if (googleConnected) {
          clearInterval(googlePollInterval);
          googlePollInterval = null;
          googleConnecting = false;
          showNotification('Google conectado correctamente', 'success');
        }
      }, 3000);
      // Stop polling after 5 minutes
      googlePollTimeout = setTimeout(() => {
        if (googlePollInterval) {
          clearInterval(googlePollInterval);
          googlePollInterval = null;
        }
        googleConnecting = false;
      }, 300000);
    } catch (e: any) {
      googleError = e.message || 'Error iniciando autenticación con Google';
      googleConnecting = false;
    }
  }

  async function disconnectGoogle() {
    try {
      await api.google.disconnect();
      googleConnected = false;
      showNotification('Google desconectado', 'info');
    } catch (e: any) {
      googleError = e.message || 'Error al desconectar Google';
    }
  }
</script>

<!-- Integraciones -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="GitBranch" size={12} /> Integraciones
  </div>
  <SettingsGithub bind:systemConfig {isConfigured} />
  {#if $devMode}
    <div class="row">
      <div class="row-label">
        <span>Google Contacts</span>
      </div>
      <button class="link-btn" onclick={openGoogleContactsLink}>Enlazar</button>
    </div>
    <div class="row">
      <div class="row-label">
        <span>Strava</span>
      </div>
      <button class="link-btn" onclick={openStravaLink}>Enlazar</button>
    </div>
    <div class="row">
      <div class="row-label">
        <span>Gmail</span>
      </div>
      <button class="link-btn" onclick={openGmailLink}>Enlazar</button>
    </div>
    <div class="row">
      <div class="row-label">
        <span>Spotify</span>
      </div>
      <button class="link-btn">Enlazar</button>
    </div>
    <div class="row">
      <div class="row-label">
        <span>Google Calendar & Tasks</span>
        {#if googleConnected}<span class="badge badge-on" style="margin-left:4px">Conectado</span
          >{/if}
      </div>
      {#if googleConnecting}
        <span class="mono" style="font-size:12px; color: var(--text-muted);">Conectando…</span>
      {:else if googleConnected}
        <button class="link-btn disconnect-btn" onclick={disconnectGoogle}>Desconectar</button>
      {:else}
        <button class="link-btn" onclick={startGoogleAuth}>Enlazar</button>
      {/if}
    </div>
    {#if googleError}
      <p class="hint" style="color:var(--danger)">{googleError}</p>
    {/if}
  {/if}
</section>

<style>
  .section {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-light);
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }

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
</style>
