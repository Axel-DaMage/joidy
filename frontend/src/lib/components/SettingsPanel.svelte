<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import {
    accentColors,
    activeIconPack,
    showFrontmatter,
    showTrash,
    showHiddenFiles,
    writeInObsidian,
    use24HourClock,
    hideTagsLine,
    devMode,
    themeMode,
    type IconPack,
    type ThemeMode,
    MAX_COLORS,
  } from '$lib/stores/settings';
  import { api } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { deferredPrompt, isAppInstalled, showInstallBanner } from '$lib/stores/pwa';
  import { showNotification } from '$lib/stores/notifications';
  import { locale as localeStore, setLocale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';
  import { mapToSupportedLocale, SUPPORTED_LOCALES, type SupportedLocale } from '$lib/i18n';

  export let open = false;

  const dispatch = createEventDispatcher<{ close: void }>();

  let configLoaded = false;
  let configSaving = false;
  let configMessage = '';

  let githubConnected = false;
  let githubUsername = '';
  let githubAuthLoading = false;
  let githubAuthError = '';
  let githubUserCode = '';
  let githubVerificationUri = '';
  let githubDeviceCode = '';
  let githubPollInterval = 5;
  let githubExpiresAt = 0;
  let githubPollTimer: ReturnType<typeof setTimeout> | null = null;

  let googleConnected = false;
  let googleConnecting = false;
  let googleError = '';
  let stravaConnected = false;
  let stravaName = '';
  let gmailConnected = false;
  let gmailEmail = '';

  let systemConfig = {
    gemini_api_key: '',
    obsidian_vault_path: '',
    daily_notes_folder: '',
    github_token: '',
    github_username: '',
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
        telegram_bot_token: '',
        telegram_allowed_user_id: '',
      };
      configLoaded = true;
      await checkGithubStatus();
      await checkGoogleStatus();
    } catch (e) {
      logger.error('Failed to load config:', e);
      configLoaded = true;
    }
  }

  async function checkGithubStatus() {
    try {
      const status = await api.github.status();
      githubConnected = status.connected;
      githubUsername = status.username || '';
    } catch (e) {
      githubConnected = false;
      githubUsername = '';
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
      const pollInterval = setInterval(async () => {
        await checkGoogleStatus();
        if (googleConnected) {
          clearInterval(pollInterval);
          googleConnecting = false;
          showNotification('Google conectado correctamente', 'success');
        }
      }, 3000);
      // Stop polling after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
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

  async function saveConfig() {
    configSaving = true;
    configMessage = '';
    try {
      // No enviamos github_token ni github_username desde el formulario general;
      // esos se manejan con el flujo OAuth dedicado.
      const { github_token, github_username, ...configToSave } = systemConfig;
      const result = await api.config.update(configToSave);
      configMessage = result.message;
      configuredKeys = Object.entries(configToSave)
        .filter(([k, v]) => v && k !== 'telegram_bot_token' && k !== 'telegram_allowed_user_id')
        .map(([k, v]) => k);
      setTimeout(() => (configMessage = ''), 3000);
    } catch (e: any) {
      configMessage = 'Error: ' + (e.message || 'Failed to save');
    } finally {
      configSaving = false;
    }
  }

  function isConfigured(key: string): boolean {
    return configuredKeys.includes(key);
  }

  const ICON_PACKS: { value: IconPack; label: string }[] = [
    { value: 'lucide', label: 'Lucide (Por Defecto)' },
    { value: 'phosphor', label: 'Phosphor' },
    { value: 'material', label: 'Material' },
  ];

  // Language selector options (#370). The store holds the full BCP-47 tag
  // (e.g. "es-CL"); we map it to a supported base locale for the dropdown.
  const LANGUAGE_OPTIONS: { value: SupportedLocale; label: string }[] = [
    { value: 'es', label: 'Español' },
    { value: 'en', label: 'English' },
  ];

  $: currentLocale = mapToSupportedLocale($localeStore);

  function onLocaleChange(e: Event) {
    const value = (e.target as HTMLSelectElement).value as SupportedLocale;
    setLocale(value);
  }

  function onColorPicker(i: number, e: Event) {
    accentColors.setColor(i, (e.target as HTMLInputElement).value);
  }

  function onHex(i: number, e: Event) {
    const raw = (e.target as HTMLInputElement).value.trim();
    const full = raw.startsWith('#') ? raw : '#' + raw;
    if (/^#[0-9a-fA-F]{6}$/.test(full)) accentColors.setColor(i, full);
  }

  $: gradientPreview =
    $accentColors.length === 1
      ? $accentColors[0]
      : `linear-gradient(to right, ${$accentColors.join(', ')})`;

  let offsetPx = 0;
  let isDragging = false;
  let startX = 0;
  let baseColors: string[] = [];

  function getFloatedColors(): string[] {
    if (baseColors.length < 2) return $accentColors;
    const n = baseColors.length;
    const pxPerColor = 120;
    const fullShift = offsetPx / pxPerColor;
    const result: string[] = [];
    for (let i = 0; i < n; i++) {
      const targetIdx = i + fullShift;
      const lo = Math.floor(targetIdx);
      const hi = lo + 1;
      const t = targetIdx - lo;
      const loIdx = ((lo % n) + n) % n;
      const hiIdx = ((hi % n) + n) % n;
      result.push(lerp(baseColors[loIdx], baseColors[hiIdx], t));
    }
    return result;
  }

  function lerp(c1: string, c2: string, t: number): string {
    const r1 = parseInt(c1.slice(1, 3), 16);
    const g1 = parseInt(c1.slice(3, 5), 16);
    const b1 = parseInt(c1.slice(5, 7), 16);
    const r2 = parseInt(c2.slice(1, 3), 16);
    const g2 = parseInt(c2.slice(3, 5), 16);
    const b2 = parseInt(c2.slice(5, 7), 16);
    const r = Math.round(r1 + (r2 - r1) * t);
    const g = Math.round(g1 + (g2 - g1) * t);
    const b = Math.round(b1 + (b2 - b1) * t);
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }

  function onGradientMouseDown(e: MouseEvent) {
    isDragging = true;
    startX = e.clientX;
    baseColors = [...$accentColors];
    window.addEventListener('mousemove', onGradientMouseMove);
    window.addEventListener('mouseup', onGradientMouseUp);
  }

  function onGradientMouseMove(e: MouseEvent) {
    if (!isDragging) return;
    offsetPx = e.clientX - startX;
  }

  function onGradientMouseUp() {
    isDragging = false;
    const pxPerColor = 120;
    const steps = Math.round(offsetPx / pxPerColor);
    if (steps !== 0 && baseColors.length > 0) {
      const n = baseColors.length;
      const rotated: string[] = [];
      for (let i = 0; i < n; i++) {
        rotated.push(baseColors[(i + steps) % n]);
      }
      rotated.forEach((c, i) => accentColors.setColor(i, c));
    }
    offsetPx = 0;
    baseColors = [];
    window.removeEventListener('mousemove', onGradientMouseMove);
    window.removeEventListener('mouseup', onGradientMouseUp);
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
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            {$t('settings.appearance')}
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label">
              <DynamicIcon name="Sparkles" size={13} />
              <span>{$t('settings.theme')}</span>
            </div>
            <div class="theme-mode-options">
              <label class="theme-mode-option" class:active={$themeMode === 'light'}>
                <input
                  type="radio"
                  name="theme-mode"
                  value="light"
                  checked={$themeMode === 'light'}
                  onchange={() => themeMode.set('light')}
                />
                <DynamicIcon name="Sun" size={14} />
                <span>{$t('settings.themeLight')}</span>
              </label>
              <label class="theme-mode-option" class:active={$themeMode === 'dark'}>
                <input
                  type="radio"
                  name="theme-mode"
                  value="dark"
                  checked={$themeMode === 'dark'}
                  onchange={() => themeMode.set('dark')}
                />
                <DynamicIcon name="Moon" size={14} />
                <span>{$t('settings.themeDark')}</span>
              </label>
            </div>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Clock3" size={13} />
              <span>{$t('settings.timeFormat')}</span>
            </div>
            <button class="toggle" onclick={() => use24HourClock.toggle()}>
              <span class:active={$use24HourClock}>24h</span>
              <span class="sep">/</span>
              <span class:active={!$use24HourClock}>12h</span>
            </button>
          </div>

          <!-- Language selector (#370) -->
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label">
              <DynamicIcon name="Languages" size={13} />
              <span>{$t('settings.language')}</span>
            </div>
            <select class="setting-input mono" value={currentLocale} onchange={onLocaleChange}>
              {#each LANGUAGE_OPTIONS as lang}
                <option value={lang.value}>{lang.label}</option>
              {/each}
            </select>
            <p class="hint" style="margin-top: 2px;">{$t('settings.languageHint')}</p>
          </div>

          <!-- Gradient preview bar -->
          <div
            class="gradient-preview"
            role="slider"
            aria-label="Color gradient preview"
            style="background: {gradientPreview}; cursor: grab;"
            onmousedown={onGradientMouseDown}
            class:dragging={isDragging}
          ></div>
          <p class="color-limit-note mono">Máximo {MAX_COLORS} colores</p>

          <!-- Per-color rows -->
          <div class="color-list">
            {#each $accentColors as color, i}
              <div class="color-entry">
                <span class="color-idx mono">{i + 1}</span>
                <input
                  type="color"
                  class="color-swatch"
                  value={color}
                  oninput={(e) => onColorPicker(i, e)}
                />
                <input
                  type="text"
                  class="hex-input mono"
                  maxlength="7"
                  value={color}
                  oninput={(e) => onHex(i, e)}
                  placeholder="#c8a96e"
                />
                {#if $accentColors.length > 1}
                  <button
                    class="color-rm"
                    onclick={() => accentColors.removeColor(i)}
                    title="Quitar"
                    aria-label="Quitar"
                  >
                    <DynamicIcon name="Minus" size={10} />
                  </button>
                {/if}
              </div>
            {/each}
          </div>

          {#if $accentColors.length < MAX_COLORS}
            <button class="add-color-btn mono" onclick={() => accentColors.addColor()}>
              <DynamicIcon name="Plus" size={10} /> agregar color
            </button>
          {/if}

          <!-- Icon Packs Selector -->
          <div
            class="row"
            style="margin-top: 16px; flex-direction: column; align-items: stretch; gap: 8px;"
          >
            <div class="row-label"><span>Set de Iconos (Alternativa Emojis)</span></div>
            <select class="setting-input mono" bind:value={$activeIconPack}>
              {#each ICON_PACKS as pack}
                <option value={pack.value}>{pack.label}</option>
              {/each}
            </select>
            <p class="hint" style="margin-top: 2px;">
              Los iconos cambiarán en los conectores y notas.
            </p>
          </div>
        </section>

        <!-- Avanzado -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="Settings" size={12} /> Avanzado
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Code" size={13} />
              <span>Metadatos (YAML)</span>
            </div>
            <button class="toggle" onclick={() => showFrontmatter.toggle()}>
              <span class:active={!$showFrontmatter}>oculto</span>
              <span class="sep">/</span>
              <span class:active={$showFrontmatter}>visible</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="EyeOff" size={13} />
              <span>Carpetas Ocultas</span>
            </div>
            <button class="toggle" onclick={() => showHiddenFiles.toggle()}>
              <span class:active={!$showHiddenFiles}>oculto</span>
              <span class="sep">/</span>
              <span class:active={$showHiddenFiles}>visible</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Trash2" size={13} />
              <span>Mostrar Papelera</span>
            </div>
            <button class="toggle" onclick={() => showTrash.toggle()}>
              <span class:active={!$showTrash}>oculto</span>
              <span class="sep">/</span>
              <span class:active={$showTrash}>visible</span>
            </button>
          </div>

          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Tag" size={13} />
              <span>Línea de Etiquetas</span>
            </div>
            <button class="toggle" onclick={() => hideTagsLine.toggle()}>
              <span class:active={$hideTagsLine}>oculta</span>
              <span class="sep">/</span>
              <span class:active={!$hideTagsLine}>visible</span>
            </button>
          </div>
        </section>

        <!-- Vault -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="Database" size={12} /> Obsidian Vault
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label">
              <span>Directorio del Vault</span>
              {#if isConfigured('obsidian_vault_path')}<span class="configured-badge">✓</span>{/if}
            </div>
            <div
              style="display: flex; align-items: center; gap: 2px; padding: 0 10px; background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r);"
              class="input-wrapper"
            >
              <span class="mono" style="color: var(--text-disabled); font-size: 11px;">~</span>
              <input
                type="text"
                class="setting-input mono"
                style="border: none; background: transparent; flex: 1; padding-left: 2px;"
                placeholder="/Documentos/ObsidianVault"
                bind:value={systemConfig.obsidian_vault_path}
              />
            </div>
          </div>
          <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
            <div class="row-label">
              <span>Carpeta de notas diarias</span>
              {#if isConfigured('daily_notes_folder')}<span class="configured-badge">✓</span>{/if}
            </div>
            <div
              style="display: flex; align-items: center; gap: 2px; padding: 0 10px; background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r);"
              class="input-wrapper"
            >
              <span class="mono" style="color: var(--text-disabled); font-size: 11px;">~</span>
              <input
                type="text"
                class="setting-input mono"
                style="border: none; background: transparent; flex: 1; padding-left: 2px;"
                placeholder="Ejemplo/Daily"
                bind:value={systemConfig.daily_notes_folder}
              />
            </div>
          </div>
          <div class="row">
            <div class="row-label">
              <DynamicIcon name="FolderRoot" size={13} />
              <span>Escribir en Vault nativo</span>
            </div>
            <button class="toggle" onclick={() => writeInObsidian.toggle()}>
              <span class:active={!$writeInObsidian}>aislado</span>
              <span class="sep">/</span>
              <span class:active={$writeInObsidian}>nativo</span>
            </button>
          </div>
          <p class="hint">
            {#if !$writeInObsidian}
              Joidy escribe en <code>_joidy/</code>. No modifica notas nativas.
            {:else}
              Joidy creará las notas directamente en la raíz de tu Vault.
            {/if}
          </p>
        </section>

        <!-- Integraciones -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="GitBranch" size={12} /> Integraciones
          </div>
          <div class="row">
            <div class="row-label">
              <span>GitHub</span>
              {#if githubConnected}<span class="configured-badge">✓</span>{/if}
            </div>
            {#if githubAuthLoading}
              <span class="mono" style="font-size:12px; color: var(--text-muted);">
                {#if githubUserCode}
                  Código: <code style="margin-left:4px; color: var(--accent); font-weight:600; letter-spacing:0.05em;">{githubUserCode}</code>
                {:else}
                  Conectando…
                {/if}
              </span>
            {:else if githubConnected}
              <div style="display:flex; align-items:center; gap:8px;">
                <span class="mono" style="font-size:12px; color: var(--xp);">{githubUsername}</span>
                <button
                  class="link-btn"
                  onclick={disconnectGithub}
                  style="background:var(--border); color:var(--text-secondary);">Desconectar</button
                >
              </div>
            {:else}
              <button class="link-btn" onclick={startGithubAuth} disabled={githubAuthLoading}
                >Enlazar</button
              >
            {/if}
          </div>
          {#if githubAuthError && !githubAuthLoading}
            <p class="hint" style="color:var(--danger)">{githubAuthError}</p>
          {/if}
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
          {/if}
          <div class="row">
            <div class="row-label">
              <span>Google Calendar & Tasks</span>
              {#if googleConnected}<span class="badge badge-on" style="margin-left:4px"
                  >Conectado</span
                >{/if}
            </div>
            {#if googleConnecting}
              <span class="mono" style="font-size:12px; color: var(--text-muted);">Conectando…</span
              >
            {:else if googleConnected}
              <button
                class="link-btn"
                onclick={disconnectGoogle}
                style="background:var(--border); color:var(--text-secondary);">Desconectar</button
              >
            {:else}
              <button class="link-btn" onclick={startGoogleAuth}>Enlazar</button>
            {/if}
          </div>
          {#if googleError}
            <p class="hint" style="color:var(--danger)">{googleError}</p>
          {/if}
        </section>

        {#if $devMode}
          <!-- IA -->
          <section class="section">
            <div class="section-title" style="color: var(--xp, var(--accent));">
              <DynamicIcon name="Zap" size={12} /> IA
            </div>
            <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
              <div class="row-label">
                <span>Gemini API Key</span>
                {#if isConfigured('gemini_api_key')}<span class="configured-badge">✓</span>{/if}
              </div>
              <input
                type="password"
                class="setting-input mono"
                placeholder="AIzaSy..."
                bind:value={systemConfig.gemini_api_key}
              />
            </div>
            <p class="hint">Habilita auto-tagging y búsqueda semántica.</p>
          </section>
        {/if}

        <!-- Aplicación (PWA) -->
        {#if $deferredPrompt && !$isAppInstalled}
          <section class="section">
            <div class="section-title" style="color: var(--xp, var(--accent));">
              <DynamicIcon name="DownloadCloud" size={12} /> Aplicación
            </div>
            <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
              <p class="hint" style="margin-top: 0;">
                Instala Joidy en tu dispositivo para acceso rápido y sin conexión.
              </p>
              <button
                class="save-config-btn"
                style="background: var(--xp);"
                onclick={async () => {
                  $deferredPrompt.prompt();
                  const { outcome } = await $deferredPrompt.userChoice;
                  if (outcome === 'accepted') {
                    showInstallBanner.set(false);
                  }
                  deferredPrompt.set(null);
                }}
              >
                <DynamicIcon name="Download" size={12} /> Instalar Joidy
              </button>
            </div>
          </section>
        {/if}

        <!-- Repositorio -->
        <section class="section">
          <div class="row">
            <div class="row-label"><span>Repositorio</span></div>
            <a
              href="https://github.com/Axel-DaMage/joidy"
              target="_blank"
              rel="noopener"
              class="mono"
              style="font-size:11px; color: var(--text-secondary);">github.com/Axel-DaMage/joidy</a
            >
          </div>
        </section>

        <!-- Desarrollador -->
        <section class="section">
          <div class="section-title" style="color: var(--xp, var(--accent));">
            <DynamicIcon name="Code" size={12} /> Desarrollador
          </div>
          <div class="row">
            <div class="row-label">
              <DynamicIcon name="Wrench" size={13} />
              <span>Modo Desarrollo</span>
            </div>
            <button class="toggle" onclick={() => devMode.toggle()}>
              <span class:active={!$devMode}>off</span>
              <span class="sep">/</span>
              <span class:active={$devMode}>on</span>
            </button>
          </div>
          <p class="hint">Activa para mostrar contenido avanzado e integraciones experimentales.</p>
        </section>
      </div>

      <div class="panel-footer">
        <button class="save-config-btn fixed-save" onclick={saveConfig} disabled={configSaving}>
          {#if configSaving}
            {$t('common.saving')}
          {:else}
            <DynamicIcon name="Save" size={12} /> {$t('common.save')}
          {/if}
        </button>
        {#if configMessage}
          <span class="config-message-footer">{configMessage}</span>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: var(--z-dropdown);
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
  }

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

  .section-subtitle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
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

  .toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    transition: border-color var(--t-fast);
  }
  .toggle:hover {
    border-color: var(--text-muted);
  }
  .toggle .active {
    color: var(--text-primary);
  }
  .toggle .sep,
  .toggle .divider {
    color: var(--border);
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

  .link-btn.disabled {
    background: var(--border);
    color: var(--text-muted);
    cursor: not-allowed;
  }
  .link-btn.disabled:hover {
    opacity: 0.6;
  }

  .row-label.disabled {
    color: var(--text-muted);
  }

  .badge {
    font-size: 10px;
    font-family: var(--font-mono);
    padding: 2px 7px;
    border-radius: 2px;
    letter-spacing: 0.05em;
  }
  .badge-off {
    background: var(--elevated);
    color: var(--text-muted);
    border: 1px solid var(--border);
  }

  .path-value {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    background: var(--elevated);
    padding: 2px 6px;
    border-radius: 2px;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-top: 8px;
  }
  .hint code {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-secondary);
    background: var(--elevated);
    padding: 1px 4px;
    border-radius: 2px;
  }

  /* ── Accent gradient builder ── */
  .gradient-preview {
    height: 24px;
    border-radius: 4px;
    margin: 8px 0 10px;
    transition: background 300ms ease;
    overflow-x: auto;
    overflow-y: hidden;
    white-space: nowrap;
    scrollbar-width: thin;
    scrollbar-color: var(--text-disabled) transparent;
  }

  .gradient-preview::-webkit-scrollbar {
    height: 4px;
  }

  .gradient-preview::-webkit-scrollbar-track {
    background: transparent;
  }

  .gradient-preview::-webkit-scrollbar-thumb {
    background: var(--text-disabled);
    border-radius: 2px;
  }

  .gradient-preview.dragging {
    cursor: grabbing;
  }

  .color-limit-note {
    margin: -4px 0 10px;
    font-size: 10px;
    color: var(--text-disabled);
    letter-spacing: 0.04em;
  }

  .color-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .color-entry {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .color-idx {
    font-size: 9px;
    color: var(--text-disabled);
    width: 10px;
    text-align: right;
  }

  .color-swatch {
    width: 26px;
    height: 26px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: none;
    cursor: pointer;
    padding: 2px;
    flex-shrink: 0;
  }

  .hex-input {
    flex: 1;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 7px;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color var(--t-fast);
  }
  .hex-input:focus {
    border-color: var(--text-muted);
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

  .input-wrapper:focus-within {
    border-color: var(--text-muted);
  }

  .color-rm {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .color-rm:hover {
    color: var(--error);
    border-color: var(--error);
  }

  .add-color-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 8px;
    background: none;
    border: 1px dashed var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    font-size: 10px;
    padding: 4px 10px;
    cursor: pointer;
    width: 100%;
    justify-content: center;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .add-color-btn:hover {
    color: var(--text-secondary);
    border-color: var(--text-muted);
  }
  .add-color-btn:focus-visible {
    outline: none;
    border-color: var(--xp);
    color: var(--xp);
  }

  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
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
    color: #fff;
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

  .config-message {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 8px;
    text-align: center;
  }

  /* Theme mode selector */
  .theme-mode-options {
    display: flex;
    gap: 6px;
  }

  .theme-mode-option {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    cursor: pointer;
    transition:
      border-color var(--t-fast),
      color var(--t-fast);
  }
  .theme-mode-option:hover {
    border-color: var(--text-muted);
  }
  .theme-mode-option.active {
    border-color: var(--xp);
    color: var(--text-primary);
  }
  .theme-mode-option input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
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
    .section {
      padding: var(--s3);
    }
    .config-message-footer {
      white-space: normal;
    }
  }

  @media (max-width: 380px) {
    .panel-header {
      padding: 10px var(--s2);
    }
    .section {
      padding: var(--s2) var(--s3);
    }
    .toggle {
      white-space: normal;
    }
  }
</style>
