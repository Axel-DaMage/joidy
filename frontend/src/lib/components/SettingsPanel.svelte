<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { browser } from '$app/env';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import SettingsAppearance from './SettingsAppearance.svelte';
  import SettingsAdvanced from './SettingsAdvanced.svelte';
  import SettingsVault from './SettingsVault.svelte';
  import SettingsIntegrations from './SettingsIntegrations.svelte';
  import SettingsAI from './SettingsAI.svelte';
  import SettingsApp from './SettingsApp.svelte';
  import SettingsSession from './SettingsSession.svelte';
  import SettingsServices from './SettingsServices.svelte';
  import SettingsDeveloper from './SettingsDeveloper.svelte';
  import { api } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  export let open = false;

  const dispatch = createEventDispatcher<{ close: void }>();

  let configLoaded = false;
  let configSaving = false;
  let configSaved = false;
  let configMessage = '';
  let configRestartNotice = '';
  let savedTimer: ReturnType<typeof setTimeout> | null = null;

  let systemConfig: SystemConfig = {
    gemini_api_key: '',
    obsidian_vault_path: '',
    daily_notes_folder: '',
    github_token: '',
    github_username: '',
    github_client_id: '',
    github_client_secret: '',
    telegram_bot_token: '',
    telegram_allowed_user_id: '',
  };

  let configuredKeys: string[] = [];

  onMount(async () => {
    if (open) {
      await loadConfig();
    }
  });

  $: if (open && !configLoaded) {
    loadConfig();
  }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveConfig();
    }
  }

  onMount(() => {
    if (browser) {
      window.addEventListener('keydown', handleKeydown);
    }
  });

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('keydown', handleKeydown);
    }
    if (savedTimer) {
      clearTimeout(savedTimer);
      savedTimer = null;
    }
  });

  async function loadConfig() {
    try {
      const config = await api.config.get();
      configuredKeys = config.configured_keys;
      systemConfig = {
        gemini_api_key: config.gemini_api_key || '',
        obsidian_vault_path: config.obsidian_vault_path || '',
        daily_notes_folder: config.daily_notes_folder || '',
        github_token: '',
        github_username: config.github_username || '',
        github_client_id: config.github_client_id || '',
        github_client_secret: config.github_client_secret || '',
        telegram_bot_token: '',
        telegram_allowed_user_id: '',
      };
      configLoaded = true;
    } catch (e) {
      logger.error('Failed to load config:', e);
      configLoaded = true;
    }
  }

  async function saveConfig() {
    configSaving = true;
    configMessage = '';
    configRestartNotice = '';
    if (savedTimer) {
      clearTimeout(savedTimer);
      savedTimer = null;
    }
    try {
      const configToSave: Record<string, any> = { ...systemConfig };
      // Omit empty secrets so we don't overwrite existing configured values with empty strings
      if (!configToSave.github_token) delete configToSave.github_token;
      if (!configToSave.github_client_id) delete configToSave.github_client_id;
      if (!configToSave.github_client_secret) delete configToSave.github_client_secret;
      if (!configToSave.github_username) delete configToSave.github_username;

      const result = await api.config.update(configToSave);
      configuredKeys = Object.entries(systemConfig)
        .filter(
          ([k, v]) =>
            (v || isConfigured(k)) && k !== 'telegram_bot_token' && k !== 'telegram_allowed_user_id'
        )
        .map(([k, v]) => k);
      if (result.requires_restart && result.restart_reason) {
        configRestartNotice = result.restart_reason;
      }
      configSaved = true;
      savedTimer = setTimeout(() => {
        configSaved = false;
        savedTimer = null;
      }, 2500);
    } catch (e: any) {
      configMessage = 'Error: ' + (e.message || 'Failed to save');
    } finally {
      configSaving = false;
    }
  }

  function isConfigured(key: string): boolean {
    return configuredKeys.includes(key);
  }

  function close() {
    dispatch('close');
  }

  function onBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) close();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdropClick}>
    <div class="panel">
      <div class="panel-header">
        <span class="mono" style="font-size:12px; letter-spacing:0.08em;"
          >{$t('settings.title')}</span
        >
        <button class="close-btn" onclick={close} aria-label={$t('common.close')}
          ><DynamicIcon name="X" size={14} /></button
        >
      </div>

      <div class="panel-body">
        <!-- Apariencia -->
        <SettingsAppearance />

        <!-- Avanzado -->
        <SettingsAdvanced />

        <!-- Vault -->
        <SettingsVault bind:systemConfig {isConfigured} />

        <!-- Integraciones -->
        <SettingsIntegrations bind:systemConfig {isConfigured} />

        <!-- IA -->
        <SettingsAI bind:systemConfig {isConfigured} />

        <!-- Aplicación (PWA) -->
        <SettingsApp />

        <!-- Sesión -->
        <SettingsSession />

        <!-- Servicios (Power Management) -->
        <SettingsServices />
        <!-- Repositorio + Desarrollador -->
        <SettingsDeveloper />
      </div>

      <div class="panel-footer">
        <button
          class="save-config-btn fixed-save"
          class:saved={configSaved}
          onclick={saveConfig}
          disabled={configSaving}
        >
          {#if configSaving}
            {$t('common.saving')}
          {:else if configSaved}
            <DynamicIcon name="CircleCheckBig" size={12} /> {$t('common.saved')}
          {:else}
            <DynamicIcon name="Save" size={12} /> {$t('common.save')}
          {/if}
        </button>
        {#if configMessage}
          <span class="config-message-footer error">{configMessage}</span>
        {/if}
      </div>
      {#if configRestartNotice}
        <div class="restart-notice">
          <DynamicIcon name="TriangleAlert" size={14} />
          <span>{configRestartNotice}</span>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .panel {
    width: 480px;
    max-width: 100%;
    height: 100%;
    background: var(--surface);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    animation: slideIn 150ms ease-out;
    position: relative;
  }

  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    border-radius: var(--r);
    transition: color var(--t-fast);
  }
  .close-btn:hover {
    color: var(--text-primary);
  }

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
    padding-bottom: 60px;
  }

  .panel-footer {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 12px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .save-config-btn.fixed-save {
    width: 100%;
    padding: 10px 16px;
  }

  .config-message-footer {
    font-size: 11px;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .config-message-footer.error {
    color: var(--error, #ef4444);
  }

  .restart-notice {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 20px;
    background: color-mix(in srgb, var(--warning, #f59e0b) 12%, var(--elevated, #1a1a1a));
    border-top: 1px solid color-mix(in srgb, var(--warning, #f59e0b) 30%, transparent);
    color: var(--text-secondary);
    font-size: 12px;
    line-height: 1.5;
  }
  .restart-notice :global(svg) {
    color: var(--warning, #f59e0b);
    flex-shrink: 0;
    margin-top: 1px;
  }

  .save-config-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    padding: 10px 16px;
    background: var(--accent, var(--xp));
    border: none;
    border-radius: var(--r);
    color: var(--bg);
    font-size: 12px;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: opacity var(--t-fast);
  }
  .save-config-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  .save-config-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .save-config-btn.saved {
    background: var(--success, #22c55e);
  }

  @media (max-width: 520px) {
    .panel {
      width: 100%;
    }
    .panel-header,
    .panel-footer {
      padding-left: var(--s3);
      padding-right: var(--s3);
    }
    .config-message-footer {
      white-space: normal;
    }
  }
</style>
