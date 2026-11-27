<script lang="ts">
  import { PencilLine, Terminal } from 'lucide-svelte';
  import { vimModeEnabled, isTouchDevice } from '$lib/stores/vim';
  import { t } from 'svelte-i18n';

  // Coarse-pointer-only devices can't use modal editing — show the toggle
  // disabled with the hint instead of hiding the row, so the setting's
  // behavior stays discoverable (#1666).
  let touchOnly = $derived(isTouchDevice());
</script>

<!-- Editor -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <PencilLine size={12} />
    {$t('settings.editor.title')}
  </div>

  <div class="row">
    <div class="row-label">
      <Terminal size={13} />
      <span>{$t('settings.editor.vimMode')}</span>
    </div>
    <button
      class="toggle"
      disabled={touchOnly}
      onclick={() => vimModeEnabled.toggle()}
      title={touchOnly ? $t('settings.editor.vimModeTouchHint') : $t('settings.editor.vimModeHint')}
    >
      <span class:active={!$vimModeEnabled}>{$t('settings.editor.off')}</span>
      <span class="sep">/</span>
      <span class:active={$vimModeEnabled}>{$t('settings.editor.on')}</span>
    </button>
  </div>
  <div class="row-hint">
    {touchOnly ? $t('settings.editor.vimModeTouchHint') : $t('settings.editor.vimModeHint')}
  </div>
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

  .row-hint {
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1.4;
    padding: 0 0 4px;
  }

  .toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    transition: border-color var(--t-fast);
  }
  .toggle:hover:not(:disabled) {
    border-color: var(--text-muted);
  }
  .toggle:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .toggle .active {
    color: var(--text-primary);
  }
</style>
