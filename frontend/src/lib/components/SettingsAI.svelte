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

    <div
      class="row"
      style="flex-direction: column; align-items: stretch; gap: 8px; margin-top: 12px; border-top: 1px solid var(--border-light); padding-top: 10px;"
    >
      <div class="row-label">
        <span>API OpenAI-compatible</span>
        {#if isConfigured('openai_api_key')}<span class="configured-badge">✓</span>{/if}
      </div>
      <input
        type="password"
        class="setting-input mono"
        placeholder="sk_live_..."
        bind:value={systemConfig.openai_api_key}
      />
      <div class="row-label">
        <span>Base URL</span>
        {#if isConfigured('openai_base_url')}<span class="configured-badge">✓</span>{/if}
      </div>
      <input
        type="text"
        class="setting-input mono"
        placeholder="https://api.stdcmpt.com/v1"
        bind:value={systemConfig.openai_base_url}
      />
      <div class="row-label">
        <span>Modelo LLM</span>
      </div>
      <input
        type="text"
        class="setting-input mono"
        placeholder="openai:standardcompute"
        bind:value={systemConfig.llm_model}
      />
      <div class="row-label">
        <span>Modelo Embeddings</span>
      </div>
      <input
        type="text"
        class="setting-input mono"
        placeholder="ollama:nomic-embed-text"
        bind:value={systemConfig.embedding_model}
      />
      <p class="hint" style="margin-bottom: 0;">
        Endpoint OpenAI-compatible (StandardCompute, LiteLLM...). Los embeddings solo se
        sirven vía Ollama u otro proveedor con <span class="mono">/embeddings</span>. Reinicia
        ai-service después de guardar.
      </p>
    </div>
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
</style>
