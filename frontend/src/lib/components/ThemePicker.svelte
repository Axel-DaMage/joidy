<script lang="ts">
  import { PRESET_THEMES, theme } from '$lib/stores/theme';
</script>

<div class="theme-picker">
  <h4 class="picker-title">Tema</h4>
  <div class="theme-grid">
    {#each PRESET_THEMES as t}
      <button
        class="theme-btn"
        class:active={$theme.id === t.id}
        on:click={() => theme.setTheme(t)}
        title={t.name}
      >
        <div class="theme-preview">
          <div class="preview-bg" style="background: {t.colors.background}"></div>
          <div class="preview-elements">
            <div class="preview-surface" style="background: {t.colors.surface}"></div>
            <div class="preview-accent" style="background: {t.colors.accent}"></div>
          </div>
        </div>
        <span class="theme-name">{t.name}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  .theme-picker {
    padding: 12px;
  }

  .picker-title {
    margin: 0 0 12px 0;
    font-size: 13px;
    color: var(--text-secondary);
  }

  .theme-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 12px;
  }

  .theme-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 8px;
    background: transparent;
    border: 1px solid var(--border-light);
    border-radius: 8px;
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .theme-btn:hover {
    border-color: var(--accent);
  }

  .theme-btn.active {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .theme-preview {
    width: 48px;
    height: 32px;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
  }

  .preview-bg {
    position: absolute;
    inset: 0;
  }

  .preview-elements {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    padding: 4px;
    gap: 3px;
  }

  .preview-surface {
    flex: 1;
    border-radius: 2px;
  }

  .preview-accent {
    width: 16px;
    height: 6px;
    border-radius: 2px;
  }

  .theme-name {
    font-size: 10px;
    color: var(--text-muted);
  }

  .theme-btn.active .theme-name {
    color: var(--accent);
  }
</style>