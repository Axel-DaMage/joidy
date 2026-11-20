<script lang="ts">
  import ModalDialog from './ModalDialog.svelte';
  import { t } from 'svelte-i18n';

  // ModalDialog-based replacement for window.prompt(): a titled dialog with a
  // single labeled text input plus Cancel/Confirm actions (#1308).
  let {
    open = false,
    title = '',
    label = '',
    value = $bindable(''),
    placeholder = '',
    confirmLabel = '',
    onSubmit,
    onClose,
  }: {
    open?: boolean;
    title?: string;
    label?: string;
    value?: string;
    placeholder?: string;
    confirmLabel?: string;
    onSubmit?: (value: string) => void;
    onClose?: () => void;
  } = $props();

  const inputId = 'prompt-dialog-input';

  function close() {
    onClose?.();
  }

  function submit() {
    const v = value.trim();
    if (!v) return;
    onSubmit?.(v);
    close();
  }
</script>

<ModalDialog {open} {title} size="sm" onClose={close}>
  <form
    onsubmit={(e) => {
      e.preventDefault();
      submit();
    }}
  >
    <div class="prompt-field">
      <label class="prompt-label" for={inputId}>{label}</label>
      <input
        id={inputId}
        type="text"
        class="prompt-input mono"
        bind:value
        {placeholder}
        autocomplete="off"
      />
    </div>
  </form>
  {#snippet footer()}
    <button class="btn ghost" type="button" onclick={close}>{$t('common.cancel')}</button>
    <button class="btn primary" type="button" disabled={!value.trim()} onclick={submit}>
      {confirmLabel || $t('common.save')}
    </button>
  {/snippet}
</ModalDialog>

<style>
  .prompt-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .prompt-label {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .prompt-input {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 8px 10px;
    font-size: 13px;
    color: var(--text-primary);
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }

  .prompt-input:focus {
    border-color: var(--xp);
  }

  .prompt-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }

  .btn {
    padding: 8px 14px;
    border-radius: var(--r);
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
  }

  .btn.ghost {
    background: var(--bg);
    color: var(--text-secondary);
  }

  .btn.ghost:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .btn.primary {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
  }

  .btn.primary:hover:not(:disabled) {
    opacity: 0.85;
  }

  .btn.primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
