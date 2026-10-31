<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import SettingsGithubAdvanced from './SettingsGithubAdvanced.svelte';
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();

  let githubConnected = $state(false);
  let githubUsername = $state('');
  let githubAuthLoading = $state(false);
  let githubAuthError = $state('');
  let githubUserCode = $state('');
  let githubVerificationUri = $state('');
  let githubDeviceCode = '';
  let githubPollInterval = 5;
  let githubExpiresAt = 0;
  let githubPollTimer: ReturnType<typeof setTimeout> | null = null;
  // Set in onDestroy so in-flight async poll callbacks stop rescheduling and
  // stop mutating state after teardown (#1003).
  let destroyed = false;
  let githubUsernameInput = $state('');
  let githubConnectingUsername = $state(false);
  let showAdvancedGithub = $state(false);

  onMount(async () => {
    await checkGithubStatus();
  });

  onDestroy(() => {
    destroyed = true;
    if (githubPollTimer) {
      clearTimeout(githubPollTimer);
      githubPollTimer = null;
    }
  });

  async function checkGithubStatus() {
    try {
      const status = await api.github.status();
      githubConnected = status.connected;
      githubUsername = status.username || '';
      if (githubUsername && !githubUsernameInput) {
        githubUsernameInput = githubUsername;
      }
    } catch (e) {
      githubConnected = false;
      githubUsername = '';
    }
  }

  async function connectGithubByUsername() {
    const trimmed = (githubUsernameInput || '').trim();
    if (!trimmed) {
      githubAuthError = 'Ingresa un nombre de usuario de GitHub';
      return;
    }
    githubConnectingUsername = true;
    githubAuthError = '';
    try {
      await api.config.update({ github_username: trimmed, github_token: '' });
      systemConfig.github_username = trimmed;
      await checkGithubStatus();
      if (githubConnected) {
        showNotification(`GitHub conectado con @${githubUsername || trimmed}`, 'success');
        window.dispatchEvent(new CustomEvent('joidy:github-connected'));
      } else {
        githubAuthError = `No se encontró el usuario @${trimmed} en GitHub`;
      }
    } catch (e: any) {
      githubAuthError = e.message || 'Error al conectar con usuario de GitHub';
    } finally {
      githubConnectingUsername = false;
    }
  }

  function clearGithubAuth() {
    githubAuthLoading = false;
    githubAuthError = '';
    githubUserCode = '';
    githubVerificationUri = '';
    githubDeviceCode = '';
    githubPollInterval = 5;
    githubExpiresAt = 0;
    if (githubPollTimer) {
      clearTimeout(githubPollTimer);
      githubPollTimer = null;
    }
  }

  async function startGithubAuth() {
    githubAuthLoading = true;
    githubAuthError = '';
    try {
      const data = await api.github.startDeviceAuth();
      githubDeviceCode = data.device_code;
      githubUserCode = data.user_code;
      githubVerificationUri = data.verification_uri;
      githubPollInterval = data.interval || 5;
      githubExpiresAt = Date.now() + (data.expires_in || 900) * 1000;
      if (githubVerificationUri) {
        window.open(githubVerificationUri, '_blank');
      }
      await pollGithubDeviceCode();
    } catch (e: any) {
      githubAuthError = e.message || 'Error iniciando autenticación con GitHub';
      githubAuthLoading = false;
    }
  }

  async function pollGithubDeviceCode() {
    if (!githubDeviceCode) {
      clearGithubAuth();
      return;
    }
    if (Date.now() >= githubExpiresAt) {
      githubAuthError = 'El código de verificación expiró. Intenta de nuevo.';
      githubAuthLoading = false;
      return;
    }
    try {
      const result = await api.github.pollDeviceCode(githubDeviceCode);
      if (result.status === 'authorized') {
        await api.config.update({ github_token: result.access_token, github_username: '' });
        await checkGithubStatus();
        clearGithubAuth();
        showNotification('GitHub conectado correctamente', 'success');
        // Notify other components (e.g. the dashboard) to refresh GitHub data
        // without requiring a manual page reload.
        window.dispatchEvent(new CustomEvent('joidy:github-connected'));
        return;
      }
      if (result.status === 'denied') {
        githubAuthError = 'Acceso denegado. No se concedieron permisos.';
        githubAuthLoading = false;
        return;
      }
      if (result.status === 'expired') {
        githubAuthError = 'El código expiró. Intenta de nuevo.';
        githubAuthLoading = false;
        return;
      }
      if (result.status === 'slowdown') {
        githubPollInterval += 5;
      }
      // Don't reschedule if the panel was destroyed mid-poll (#1003).
      if (destroyed || !githubDeviceCode) return;
      githubPollTimer = setTimeout(pollGithubDeviceCode, githubPollInterval * 1000);
    } catch (e: any) {
      if (githubPollTimer) {
        clearTimeout(githubPollTimer);
        githubPollTimer = null;
      }
      githubAuthError = e.message || 'Error verificando autorización de GitHub';
      githubAuthLoading = false;
    }
  }

  async function disconnectGithub() {
    try {
      await api.github.revoke();
    } catch (e) {
      // Ignorar errores de revoke; de todos modos borramos el token
    }
    await api.config.update({ github_token: '', github_username: '' });
    await checkGithubStatus();
    showNotification('GitHub desconectado', 'info');
    window.dispatchEvent(new CustomEvent('joidy:github-disconnected'));
  }
</script>

<!-- GitHub Integration -->
<div class="row">
  <div class="row-label">
    <DynamicIcon name="Github" size={13} />
    <span>GitHub</span>
    {#if githubConnected}<span class="configured-badge">✓</span>{/if}
  </div>
  {#if githubAuthLoading}
    <span class="mono" style="font-size:12px; color: var(--text-muted);">
      {#if githubUserCode}
        Código: <code
          style="margin-left:4px; color: var(--accent); font-weight:600; letter-spacing:0.05em;"
          >{githubUserCode}</code
        >
      {:else}
        Conectando…
      {/if}
    </span>
  {:else if githubConnected}
    <div style="display:flex; align-items:center; gap:8px;">
      <span class="mono" style="font-size:12px; color: var(--xp);">@{githubUsername}</span>
      <button class="link-btn disconnect-btn" onclick={disconnectGithub}>Desconectar</button>
    </div>
  {:else}
    <button class="link-btn" onclick={startGithubAuth} disabled={githubAuthLoading}
      >Conectar OAuth</button
    >
  {/if}
</div>

{#if !githubConnected}
  <!-- Conexión rápida por usuario -->
  <div style="margin-top: 8px; display: flex; gap: 8px; align-items: center;">
    <input
      type="text"
      class="setting-input mono"
      style="font-size: 12px; padding: 6px 10px; flex: 1;"
      placeholder="Tu usuario de GitHub (ej: torvalds)"
      bind:value={githubUsernameInput}
      onkeydown={(e) => {
        if (e.key === 'Enter') connectGithubByUsername();
      }}
    />
    <button
      class="link-btn"
      style="white-space: nowrap; padding: 6px 14px;"
      onclick={connectGithubByUsername}
      disabled={githubConnectingUsername || !githubUsernameInput.trim()}
    >
      {githubConnectingUsername ? 'Verificando…' : 'Conectar usuario'}
    </button>
  </div>
  <p class="hint" style="margin-top: 4px;">
    Conecta sólo con tu nombre de usuario para ver repositorios, issues y pulls públicos sin
    requerir tokens ni OAuth.
  </p>
{/if}

{#if githubAuthError && !githubAuthLoading}
  <p class="hint" style="color:var(--danger); margin-top: 6px;">{githubAuthError}</p>
{/if}

<!-- Botón para alternar configuración manual/avanzada -->
<div style="margin-top: 10px;">
  <button
    type="button"
    class="toggle"
    style="font-size: 10px; padding: 3px 8px;"
    onclick={() => (showAdvancedGithub = !showAdvancedGithub)}
  >
    <DynamicIcon name="SlidersHorizontal" size={11} />
    <span
      >{showAdvancedGithub
        ? 'Ocultar configuración avanzada'
        : 'Configuración avanzada (Tokens / OAuth App)'}</span
    >
  </button>
</div>

{#if showAdvancedGithub}
  <SettingsGithubAdvanced bind:systemConfig {isConfigured} />
{/if}

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
</style>
