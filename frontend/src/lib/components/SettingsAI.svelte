<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { devMode } from '$lib/stores/settings';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();
</script>

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
  .hint code {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--text-secondary);
    background: var(--elevated);
    padding: 1px 4px;
    border-radius: 2px;
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

  .input-wrapper:focus-within {
    border-color: var(--text-muted);
  }

  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
  }
</style>
