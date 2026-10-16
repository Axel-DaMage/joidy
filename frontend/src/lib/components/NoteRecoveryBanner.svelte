<script lang="ts">
  import { RotateCcw } from 'lucide-svelte';
  import { t } from 'svelte-i18n';

  interface Props {
    show: boolean;
    onApply: () => void;
    onDismiss: () => void;
  }

  let { show = $bindable(), onApply, onDismiss }: Props = $props();
</script>

{#if show}
  <div class="recovery-banner">
    <RotateCcw size={12} />
    <span>¿Recuperar borrador no guardado?</span>
    <button class="recovery-btn" onclick={onApply}>{$t('noteEditor.recover')}</button>
    <button class="recovery-btn secondary" onclick={onDismiss}>{$t('noteEditor.discard')}</button>
  </div>
{/if}

<style>
  /* ── Recovery Banner ── */
  .recovery-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    background: color-mix(in srgb, #fbbf24 12%, var(--surface));
    border-bottom: 1px solid color-mix(in srgb, #fbbf24 30%, var(--border));
    font-size: 12px;
    color: var(--text-primary);
  }

  .recovery-btn {
    padding: 3px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-sm, 4px);
    background: var(--elevated);
    color: var(--text-primary);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.1s;
  }

  .recovery-btn:hover {
    background: var(--bg-card);
    border-color: var(--text-muted);
  }

  .recovery-btn.secondary {
    background: transparent;
    color: var(--text-muted);
  }

  .recovery-btn.secondary:hover {
    color: var(--error);
    border-color: var(--error);
  }
</style>
