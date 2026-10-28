<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import SettingsGithub from './SettingsGithub.svelte';
  import SettingsGoogle from './SettingsGoogle.svelte';
  import { devMode } from '$lib/stores/settings';
  import type { SystemConfig } from '$lib/utils/settingsTypes';

  interface Props {
    systemConfig: SystemConfig;
    isConfigured: (key: string) => boolean;
  }

  let { systemConfig = $bindable(), isConfigured }: Props = $props();

  async function openGoogleContactsLink() {
    window.open('https://contacts.google.com', '_blank');
  }
  async function openStravaLink() {
    window.open('https://strava.com', '_blank');
  }
</script>

<!-- Integraciones -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="GitBranch" size={12} /> Integraciones
  </div>
  <SettingsGithub bind:systemConfig {isConfigured} />
  <SettingsGoogle bind:systemConfig {isConfigured} />
  {#if $devMode}
    <div class="row">
      <div class="row-label">
        <span>Google Contacts</span>
      </div>
      <button class="link-btn" onclick={openGoogleContactsLink}>Enlazar</button>
    </div>
    <div class="row">
      <div class="row-label">
        <span>Strava</span>
      </div>
      <button class="link-btn" onclick={openStravaLink}>Enlazar</button>
    </div>
    <div class="row">
      <div class="row-label">
        <span>Spotify</span>
      </div>
      <button class="link-btn">Enlazar</button>
    </div>
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
</style>
