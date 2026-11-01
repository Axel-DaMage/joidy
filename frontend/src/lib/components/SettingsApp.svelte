<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { deferredPrompt, isAppInstalled, showInstallBanner } from '$lib/stores/pwa';
</script>

<!-- Aplicación (PWA) -->
{#if $deferredPrompt && !$isAppInstalled}
  <section class="section">
    <div class="section-title" style="color: var(--xp, var(--accent));">
      <DynamicIcon name="CloudDownload" size={12} /> Aplicación
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

<style>
  /* Restaurada: se perdió en el split #1067; el markup usaba la clase
     inválida ":global(hint)" que nunca matcheaba. */
  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin-top: 8px;
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

  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
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
</style>
