<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { devMode } from '$lib/stores/settings';

  export let icon: string;
  export let title: string;
  export let caption: string;
  export let color: string = 'var(--accent)';
</script>

<div class="integration-page">
  <div class="page-header">
    <div class="header-icon" style="color: {color}">
      <DynamicIcon name={icon} size={28} />
    </div>
    <div class="header-text">
      <h2>{title}</h2>
      <span class="caption">{caption}</span>
    </div>
  </div>

  <div class="content">
    {#if $devMode}
      <div class="dev-box">
        <DynamicIcon name="Wrench" size={48} />
        <h3>En Desarrollo</h3>
        <p>Esta integración está siendo implementada. Trabaja en este modulo usando la rama de desarrollo.</p>
      </div>
    {:else}
      <div class="construction-box">
        <DynamicIcon name="Construction" size={48} />
        <h3>En Construcción</h3>
        <p>Esta integración está en desarrollo. Activa el Modo Desarrollo en Ajustes para acceder.</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .integration-page {
    padding: 24px;
    max-width: 800px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 32px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }

  .header-icon {
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }

  .header-text h2 {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
  }

  .header-text .caption {
    font-size: 13px;
    color: var(--text-muted);
  }

  .construction-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 48px 24px;
    background: var(--elevated);
    border: 2px dashed var(--border);
    border-radius: var(--r-lg);
    color: var(--text-muted);
  }

  .construction-box :global(svg) {
    margin-bottom: 16px;
    opacity: 0.6;
  }

  .construction-box h3 {
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 8px 0;
    color: var(--text-secondary);
  }

  .construction-box p {
    font-size: 14px;
    max-width: 400px;
    margin: 0;
    line-height: 1.5;
  }

  .dev-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 48px 24px;
    background: color-mix(in srgb, var(--xp) 5%, var(--elevated));
    border: 2px solid var(--xp);
    border-radius: var(--r-lg);
    color: var(--text-secondary);
  }

  .dev-box :global(svg) {
    margin-bottom: 16px;
    color: var(--xp);
  }

  .dev-box h3 {
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 8px 0;
    color: var(--xp);
  }

  .dev-box p {
    font-size: 14px;
    max-width: 400px;
    margin: 0;
    line-height: 1.5;
  }
</style>
