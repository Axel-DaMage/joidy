<script lang="ts">
  // Passthrough stub para tests: SettingsSection solo aporta el marco
  // (título/descripción/borde), irrelevante para lo que se prueba.
  let { children }: { children?: import('svelte').Snippet } = $props();
</script>

{@render children?.()}
