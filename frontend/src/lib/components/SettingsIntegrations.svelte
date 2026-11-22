<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import SettingsGithub from './SettingsGithub.svelte';
  import SettingsGoogle from './SettingsGoogle.svelte';
  import SettingsStrava from './SettingsStrava.svelte';
  // Google Contacts is a real integration now (#43) — real status/connect row,
  // no longer gated behind dev mode like the Strava/Spotify placeholders.
  import SettingsContacts from './SettingsContacts.svelte';
  import SettingsSpotify from './SettingsSpotify.svelte';
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
    <DynamicIcon name="GitBranch" size={12} /> Integraciones
  </div>
  <SettingsGithub bind:systemConfig {isConfigured} />
  <SettingsGoogle bind:systemConfig {isConfigured} />
  <!-- Strava (#44): estado real de conexión — OAuth popup + poll, igual que Google. -->
  <SettingsStrava />
  <!-- Google Contacts: real status/connect row (#43) -->
  <SettingsContacts bind:systemConfig {isConfigured} />
  <SettingsSpotify />
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
