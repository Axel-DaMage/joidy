<script lang="ts">
  import SettingsGithub from './SettingsGithub.svelte';
  import SettingsGoogle from './SettingsGoogle.svelte';
  import SettingsStrava from './SettingsStrava.svelte';
  import SettingsContacts from './SettingsContacts.svelte';
  import SettingsSpotify from './SettingsSpotify.svelte';
  import { devMode } from '$lib/stores/settings';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();


</script>

<!-- Integraciones — el marco (título/descripción/borde) lo aporta SettingsSection (#1671). -->
<div class="section-content">
  <SettingsGithub bind:systemConfig {isConfigured} />
  <SettingsGoogle bind:systemConfig {isConfigured} />
  {#if $devMode}
    <!-- Strava/Contacts/Spotify UIs are gated behind dev mode (#1492): their
         backends are partial/OAuth-dependent, so the rows stay hidden until
         the integrations are production-ready. -->
    <SettingsStrava />
    <SettingsContacts bind:systemConfig {isConfigured} />
    <SettingsSpotify />
  {/if}
</div>
