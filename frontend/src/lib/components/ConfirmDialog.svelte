<script lang="ts">
  import ModalDialog from './ModalDialog.svelte';
  import { t } from 'svelte-i18n';

  // ModalDialog-based replacement for window.confirm(): a titled dialog with a
  // message plus Cancel/Confirm actions (#1308).
  let {
    open = false,
    title = '',
    message = '',
    confirmLabel = '',
    danger = false,
    onConfirm,
    onClose,
  }: {
    open?: boolean;
    title?: string;
    message?: string;
    confirmLabel?: string;
    danger?: boolean;
    onConfirm?: () => void;
    onClose?: () => void;
  } = $props();

  function close() {
    onClose?.();
  }

  function confirm() {
    onConfirm?.();
    close();
  }
</script>

<ModalDialog {open} {title} size="sm" onClose={close}>
  <p class="confirm-message">{message}</p>
  {#snippet footer()}
    <button class="btn ghost" type="button" onclick={close}>{$t('common.cancel')}</button>
    <button class="btn" class:danger type="button" onclick={confirm}>
      {confirmLabel || $t('common.delete')}
    </button>
  {/snippet}
</ModalDialog>

<style>
  .confirm-message {
    margin: 0;
    font-size: 13px;
    color: var(--text-primary);
    line-height: 1.5;
    word-break: break-word;
  }

  .btn {
    padding: 8px 14px;
    border-radius: var(--r);
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-secondary);
  }

  .btn.ghost:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .btn.danger {
    background: var(--error);
    border-color: var(--error);
    color: #fff;
  }

  .btn.danger:hover {
    opacity: 0.85;
  }
</style>
