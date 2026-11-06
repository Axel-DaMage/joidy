<script lang="ts">
  // Stub runes que replica cómo SettingsAI real consume isConfigured().
  let { isConfigured }: { isConfigured: (key: string) => boolean } = $props();

  const openaiConfigured = $derived(isConfigured('openai_api_key'));
</script>

<div>
  <span>IA</span>
  {#if openaiConfigured}
    <span data-testid="ai-configured">configurada</span>
  {:else}
    <span data-testid="ai-not-configured">sin configurar</span>
  {/if}
</div>
