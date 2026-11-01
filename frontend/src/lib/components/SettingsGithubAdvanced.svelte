<script lang="ts">
  import { ExternalLink } from 'lucide-svelte';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();
</script>

<!-- GitHub Manual / Advanced Config -->
<div
  style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px; border-left: 2px solid var(--border); padding-left: 12px; margin-left: 4px;"
>
  <p class="hint" style="margin-top: 0; font-weight: 500;">Credenciales avanzadas de GitHub:</p>

  <div style="display: flex; flex-direction: column; gap: 4px;">
    <div class="row-label" style="font-size: 11px;">
      <a
        href="https://github.com/settings/tokens/new"
        target="_blank"
        rel="noopener noreferrer"
        class="external-setting-link"
        title="Abrir página para generar un Personal Access Token (PAT) en GitHub"
      >
        <span>Personal Access Token (PAT)</span>
        <ExternalLink size={10} />
      </a>
      {#if isConfigured('github_token')}<span class="configured-badge">✓</span>{/if}
    </div>
    <input
      type="password"
      class="setting-input mono"
      style="font-size: 11px; padding: 4px 8px;"
      placeholder="ghp_..."
      bind:value={systemConfig.github_token}
    />
  </div>

  <div style="display: flex; flex-direction: column; gap: 4px;">
    <div class="row-label" style="font-size: 11px;">
      <a
        href="https://github.com/settings/developers"
        target="_blank"
        rel="noopener noreferrer"
        class="external-setting-link"
        title="Abrir GitHub Developer Settings para gestionar OAuth Apps"
      >
        <span>GitHub OAuth Client ID</span>
        <ExternalLink size={10} />
      </a>
      {#if isConfigured('github_client_id')}<span class="configured-badge">✓</span>{/if}
    </div>
    <input
      type="text"
      class="setting-input mono"
      style="font-size: 11px; padding: 4px 8px;"
      placeholder="Ov23..."
      bind:value={systemConfig.github_client_id}
    />
  </div>

  <div style="display: flex; flex-direction: column; gap: 4px;">
    <div class="row-label" style="font-size: 11px;">
      <a
        href="https://github.com/settings/developers"
        target="_blank"
        rel="noopener noreferrer"
        class="external-setting-link"
        title="Abrir GitHub Developer Settings para gestionar OAuth Apps"
      >
        <span>GitHub OAuth Client Secret</span>
        <ExternalLink size={10} />
      </a>
      {#if isConfigured('github_client_secret')}<span class="configured-badge">✓</span>{/if}
    </div>
    <input
      type="password"
      class="setting-input mono"
      style="font-size: 11px; padding: 4px 8px;"
      placeholder="client_secret_..."
      bind:value={systemConfig.github_client_secret}
    />
  </div>
</div>

<style>
  .external-setting-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--text-secondary);
    text-decoration: none;
    transition: color var(--t-fast);
  }
  .external-setting-link:hover {
    color: var(--accent, var(--xp));
    text-decoration: underline;
  }

  /* Restauradas: se perdieron en el split #1067 (vivían en SettingsPanel). */
  .configured-badge {
    font-size: 10px;
    color: var(--success);
    margin-left: 4px;
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-top: 8px;
  }

  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
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
</style>
