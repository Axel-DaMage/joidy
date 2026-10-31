<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import SettingsAccentColors from './SettingsAccentColors.svelte';
  import {
    activeIconPack,
    use24HourClock,
    themeMode,
    clockStyle,
    type IconPack,
  } from '$lib/stores/settings';
  import { CLOCK_STYLES } from '$lib/utils/clock';
  import { locale as localeStore, setLocale } from '$lib/stores/locale';
  import { t } from 'svelte-i18n';
  import { mapToSupportedLocale, type SupportedLocale } from '$lib/i18n';

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
</script>

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

  <!-- Clock style selector (#707) -->
  <div class="row" style="flex-direction: column; align-items: stretch; gap: 8px;">
    <div class="row-label">
      <DynamicIcon name="Clock" size={13} />
      <span>{$t('settings.clockStyle')}</span>
    </div>
    <select class="setting-input mono" bind:value={$clockStyle}>
      {#each CLOCK_STYLES as style}
        <option value={style}>{$t(`settings.clockStyles.${style}`)}</option>
      {/each}
    </select>
    <p class="hint" style="margin-top: 2px;">{$t('settings.clockStyleHint')}</p>
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

  <SettingsAccentColors />

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
    <p class="hint" style="margin-top: 2px;">Los iconos cambiarán en los conectores y notas.</p>
  </div>
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
</style>
