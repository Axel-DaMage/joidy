<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/env';
  import { ArrowLeft, CircleCheckBig, Save, TriangleAlert } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import SettingsSection from './SettingsSection.svelte';
  import SettingsAppearance from './SettingsAppearance.svelte';
  import SettingsAdvanced from './SettingsAdvanced.svelte';
  import SettingsEditor from './SettingsEditor.svelte';
  import SettingsVault from './SettingsVault.svelte';
  import SettingsIntegrations from './SettingsIntegrations.svelte';
  import SettingsAI from './SettingsAI.svelte';
  import SettingsApp from './SettingsApp.svelte';
  import SettingsSession from './SettingsSession.svelte';
  import SettingsServices from './SettingsServices.svelte';
  import SettingsDeveloper from './SettingsDeveloper.svelte';
  import { focusTrap } from '$lib/actions/focusTrap';
  import { enter } from '$lib/utils/motion';
  import { api } from '$lib/api';
  import { devMode } from '$lib/stores/settings';
  import { deferredPrompt, isAppInstalled } from '$lib/stores/pwa';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    /** Active section slug; bound so the /settings route can sync it with the URL hash. */
    section?: string;
    /** Escape/back — the route owns navigation (history.back / goto). */
    onClose?: () => void;
  }

  let { section = $bindable('appearance'), onClose }: Props = $props();

  // Section order mirrors the old drawer stack (#1671). `devOnly`/`installOnly`
  // sections only exist when their child would render content (SettingsAI is
  // devMode-gated, SettingsApp only while a PWA install prompt is available).
  const SECTIONS: { id: string; icon: string; devOnly?: boolean; installOnly?: boolean }[] = [
    { id: 'appearance', icon: 'Palette' },
    { id: 'advanced', icon: 'Settings' },
    { id: 'editor', icon: 'PencilLine' },
    { id: 'vault', icon: 'Database' },
    { id: 'integrations', icon: 'GitBranch' },
    { id: 'ai', icon: 'Zap', devOnly: true },
    { id: 'app', icon: 'CloudDownload', installOnly: true },
    { id: 'session', icon: 'UserRound' },
    { id: 'services', icon: 'Power' },
    { id: 'developer', icon: 'Code' },
  ];

  const installable = $derived(!!$deferredPrompt && !$isAppInstalled);
  const visibleSections = $derived(
    SECTIONS.filter(
      (s) => (!s.devOnly || $devMode) && (!s.installOnly || installable)
    )
  );

  // If the active section's gate closes while open (e.g. dev mode toggled off
  // on the Desarrollador tab), fall back to the first section.
  $effect(() => {
    if (!visibleSections.some((s) => s.id === section)) {
      section = visibleSections[0]?.id ?? 'appearance';
    }
  });

  let configLoaded = $state(false);
  let configSaving = $state(false);
  let configSaved = $state(false);
  let configMessage = $state('');
  let configRestartNotice = $state('');
  let savedTimer: ReturnType<typeof setTimeout> | null = null;

  let systemConfig: SystemConfig = $state({
    gemini_api_key: '',
    obsidian_vault_path: '',
    daily_notes_folder: '',
    github_token: '',
    github_username: '',
    github_client_id: '',
    github_client_secret: '',
    google_client_id: '',
    google_client_secret: '',
    google_redirect_uri: '',
    openai_api_key: '',
    openai_base_url: '',
    llm_model: '',
    embedding_model: '',
    telegram_bot_token: '',
    telegram_allowed_user_id: '',
  });

  // $state es OBLIGATORIO aquí: los hijos (SettingsGoogle, SettingsAI, ...)
  // son componentes runes y llaman a isConfigured() dentro de sus propios
  // $derived. Una variable plana no crea señal, así que cuando loadConfig()
  // la rellenaba el hijo nunca se re-renderizaba y el botón «Conectar con
  // Google» no aparecía aunque el backend ya reportara las creds (#1134).
  let configuredKeys: string[] = $state([]);

  function handleKeydown(e: KeyboardEvent) {
    // The guard only requires a finished initial load now: this component is
    // mounted exclusively by the /settings route, so a "closed but mounted"
    // panel (the original #1304 hazard) can no longer receive Ctrl+S — the
    // window listener dies with the page. Keep guarding on configLoaded so a
    // Ctrl+S fired before GET /config resolves can't post secret fields that
    // are always '' client-side.
    if (!configLoaded) return;
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveConfig();
    }
  }

  onMount(async () => {
    await loadConfig();
    if (browser) {
      window.addEventListener('keydown', handleKeydown);
    }
  });

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('keydown', handleKeydown);
      // Broadcast so mounted pages (e.g. notes) can refetch config after edits.
      window.dispatchEvent(new CustomEvent('joidy:settings-closed'));
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
        google_client_id: config.google_client_id || '',
        google_client_secret: '',
        google_redirect_uri: config.google_redirect_uri || '',
        openai_api_key: '',
        openai_base_url: config.openai_base_url || '',
        llm_model: config.llm_model || '',
        embedding_model: config.embedding_model || '',
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
      // Omit empty secrets so we don't overwrite existing configured values
      // with empty strings. GET /config never returns secret values, so these
      // fields are always '' here even when configured on the server (#1304).
      if (!configToSave.gemini_api_key) delete configToSave.gemini_api_key;
      if (!configToSave.github_token) delete configToSave.github_token;
      if (!configToSave.github_client_id) delete configToSave.github_client_id;
      if (!configToSave.github_client_secret) delete configToSave.github_client_secret;
      if (!configToSave.github_username) delete configToSave.github_username;
      if (!configToSave.google_client_id) delete configToSave.google_client_id;
      if (!configToSave.google_client_secret) delete configToSave.google_client_secret;
      if (!configToSave.openai_api_key) delete configToSave.openai_api_key;
      if (!configToSave.telegram_bot_token) delete configToSave.telegram_bot_token;
      if (!configToSave.telegram_allowed_user_id) delete configToSave.telegram_allowed_user_id;

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
    onClose?.();
  }
</script>

<div class="settings-view" in:enter use:focusTrap={{ onEscape: close }}>
  <!-- Section rail -->
  <nav class="settings-nav" aria-label={$t('settings.title')}>
    <button class="settings-back" onclick={close}>
      <ArrowLeft size={13} />
      <span>{$t('common.back')}</span>
    </button>
    <div class="settings-nav-title mono">{$t('settings.title')}</div>
    {#each visibleSections as s (s.id)}
      <button
        class="settings-nav-item"
        class:active={section === s.id}
        aria-current={section === s.id ? 'true' : undefined}
        onclick={() => (section = s.id)}
      >
        <DynamicIcon name={s.icon} size={14} />
        <span>{$t(`settings.nav.${s.id}`)}</span>
      </button>
    {/each}
  </nav>

  <!-- Content pane -->
  <div class="settings-main">
    <div class="settings-content">
      {#if section === 'appearance'}
        <SettingsSection
          id="appearance"
          title={$t('settings.nav.appearance')}
          description={$t('settings.descriptions.appearance')}
          icon="Palette"
        >
          <SettingsAppearance />
        </SettingsSection>
      {:else if section === 'advanced'}
        <SettingsSection
          id="advanced"
          title={$t('settings.nav.advanced')}
          description={$t('settings.descriptions.advanced')}
          icon="Settings"
        >
          <SettingsAdvanced />
        </SettingsSection>
      {:else if section === 'editor'}
        <SettingsSection
          id="editor"
          title={$t('settings.nav.editor')}
          description={$t('settings.descriptions.editor')}
          icon="PencilLine"
        >
          <SettingsEditor />
        </SettingsSection>
      {:else if section === 'vault'}
        <SettingsSection
          id="vault"
          title={$t('settings.nav.vault')}
          description={$t('settings.descriptions.vault')}
          icon="Database"
        >
          <SettingsVault bind:systemConfig {isConfigured} />
        </SettingsSection>
      {:else if section === 'integrations'}
        <SettingsSection
          id="integrations"
          title={$t('settings.nav.integrations')}
          description={$t('settings.descriptions.integrations')}
          icon="GitBranch"
        >
          <SettingsIntegrations bind:systemConfig {isConfigured} />
        </SettingsSection>
      {:else if section === 'ai'}
        <SettingsSection
          id="ai"
          title={$t('settings.nav.ai')}
          description={$t('settings.descriptions.ai')}
          icon="Zap"
        >
          <SettingsAI bind:systemConfig {isConfigured} />
        </SettingsSection>
      {:else if section === 'app'}
        <SettingsSection
          id="app"
          title={$t('settings.nav.app')}
          description={$t('settings.descriptions.app')}
          icon="CloudDownload"
        >
          <SettingsApp />
        </SettingsSection>
      {:else if section === 'session'}
        <SettingsSection
          id="session"
          title={$t('settings.nav.session')}
          description={$t('settings.descriptions.session')}
          icon="UserRound"
        >
          <SettingsSession />
        </SettingsSection>
      {:else if section === 'services'}
        <SettingsSection
          id="services"
          title={$t('settings.nav.services')}
          description={$t('settings.descriptions.services')}
          icon="Power"
        >
          <SettingsServices />
        </SettingsSection>
      {:else if section === 'developer'}
        <SettingsSection
          id="developer"
          title={$t('settings.nav.developer')}
          description={$t('settings.descriptions.developer')}
          icon="Code"
        >
          <SettingsDeveloper />
        </SettingsSection>
      {/if}
    </div>

    {#if configRestartNotice}
      <div class="restart-notice">
        <TriangleAlert size={14} />
        <span>{configRestartNotice}</span>
      </div>
    {/if}

    <div class="settings-footer">
      <p class="settings-save-hint">{$t('settings.saveHint')}</p>
      {#if configMessage}
        <span class="config-message-footer error">{configMessage}</span>
      {/if}
      <button
        class="save-config-btn"
        class:saved={configSaved}
        onclick={saveConfig}
        disabled={configSaving}
      >
        {#if configSaving}
          {$t('common.saving')}
        {:else if configSaved}
          <CircleCheckBig size={12} /> {$t('common.saved')}
        {:else}
          <Save size={12} /> {$t('common.save')}
        {/if}
      </button>
    </div>
  </div>
</div>

<style>
  /* Full-window settings view (#1671): left section rail + content pane.
     View body spacing standard: padding: var(--s3) and nothing else. */
  .settings-view {
    display: flex;
    gap: var(--s3);
    height: 100%;
    min-height: 0;
    padding: var(--s3);
    box-sizing: border-box;
    outline: none;
  }

  /* ── Section rail ── */
  .settings-nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    width: 200px;
    flex-shrink: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    overflow-y: auto;
    min-height: 0;
  }

  .settings-back {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    margin-bottom: var(--s2);
    background: none;
    border: none;
    border-radius: var(--r);
    color: var(--text-muted);
    font-size: 11px;
    font-family: var(--font-mono);
    cursor: pointer;
    transition:
      color var(--t-fast),
      background var(--t-fast);
  }
  .settings-back:hover {
    color: var(--text-primary);
    background: var(--elevated);
  }

  .settings-nav-title {
    padding: 0 8px var(--s2);
    font-size: 10px;
    letter-spacing: 0.1em;
    color: var(--text-muted);
  }

  .settings-nav-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 8px;
    background: none;
    border: none;
    border-radius: var(--r);
    color: var(--text-secondary);
    font-size: 12px;
    font-family: var(--font-sans);
    text-align: left;
    cursor: pointer;
    transition:
      color var(--t-fast),
      background var(--t-fast);
  }
  .settings-nav-item:hover {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .settings-nav-item.active {
    background: var(--elevated);
    color: var(--text-primary);
    box-shadow: inset 2px 0 0 var(--xp, var(--accent));
  }

  /* ── Content pane ── */
  .settings-main {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    flex: 1;
    min-width: 0;
    min-height: 0;
  }

  .settings-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .restart-notice {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px var(--s4);
    background: color-mix(in srgb, var(--warning, #f59e0b) 12%, var(--elevated, #1a1a1a));
    border: 1px solid color-mix(in srgb, var(--warning, #f59e0b) 30%, transparent);
    border-radius: var(--r);
    color: var(--text-secondary);
    font-size: 12px;
    line-height: 1.5;
    flex-shrink: 0;
  }
  .restart-notice :global(svg) {
    color: var(--warning, #f59e0b);
    flex-shrink: 0;
    margin-top: 1px;
  }

  /* Global save semantics (#1671): one save posts the whole system config —
     sections share the same SystemConfig store, so there is no per-section
     save. Empty secrets are dropped before POST so they never wipe configured
     values (#1304). */
  .settings-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--s3);
    padding: var(--s3) var(--s4);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    flex-shrink: 0;
  }

  .settings-save-hint {
    margin: 0;
    margin-right: auto;
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .config-message-footer {
    font-size: 11px;
    color: var(--text-secondary);
  }
  .config-message-footer.error {
    color: var(--error, #ef4444);
  }

  .save-config-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 20px;
    background: var(--accent, var(--xp));
    border: none;
    border-radius: var(--r);
    color: var(--bg);
    font-size: 12px;
    font-family: var(--font-mono);
    cursor: pointer;
    white-space: nowrap;
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

  /* Narrow viewports: the rail collapses to a horizontal strip on top. */
  @media (max-width: 700px) {
    .settings-view {
      flex-direction: column;
    }
    .settings-nav {
      width: 100%;
      flex-direction: row;
      align-items: center;
      gap: 4px;
      overflow-x: auto;
      overflow-y: hidden;
      flex-shrink: 0;
    }
    .settings-back {
      margin-bottom: 0;
      flex-shrink: 0;
    }
    .settings-nav-title {
      display: none;
    }
    .settings-nav-item {
      flex-shrink: 0;
      white-space: nowrap;
    }
    .settings-nav-item.active {
      box-shadow: inset 0 -2px 0 var(--xp, var(--accent));
    }
    .settings-footer {
      flex-wrap: wrap;
    }
    .settings-save-hint {
      flex-basis: 100%;
    }
  }
</style>
