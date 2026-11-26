<script lang="ts">
  import { GitBranch } from 'lucide-svelte';
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

<!-- Integraciones -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <GitBranch size={12} /> Integraciones
  </div>
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
</style>
