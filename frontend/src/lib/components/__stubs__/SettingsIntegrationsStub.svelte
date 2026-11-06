<script lang="ts">
  // Stub runes que replica cómo SettingsGoogle real consume isConfigured()
  // dentro de un $derived (vía SettingsIntegrations).
  let { isConfigured }: { isConfigured: (key: string) => boolean } = $props();

  const googleConfigured = $derived(isConfigured('google_client_id'));
</script>

<div>
  <span>Google (Calendar · Tasks · Gmail · Contacts)</span>
  {#if googleConfigured}
    <button data-testid="google-connect">Conectar con Google</button>
  {:else}
    <button data-testid="google-setup">Configurar</button>
  {/if}
</div>
