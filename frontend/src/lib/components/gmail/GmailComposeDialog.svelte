<script lang="ts">
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import type { GmailSendInput } from '$lib/api';
  import { fileToBase64Payload, type OutgoingAttachmentPayload } from '$lib/utils/gmail';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import Paperclip from 'lucide-svelte/icons/paperclip';
  import X from 'lucide-svelte/icons/x';
  import Send from 'lucide-svelte/icons/send';

  /** Backend caps (gmail_service): ≤10 attachments, ≤20 MB decoded total. */
  const MAX_ATTACHMENTS = 10;
  const MAX_ATTACHMENTS_TOTAL_BYTES = 20 * 1024 * 1024;

  interface Props {
    open: boolean;
    /** Reply/forward prefill — applied once when the dialog opens. */
    prefill?: { to?: string; cc?: string; subject?: string; body?: string } | null;
    sending?: boolean;
    onClose: () => void;
    onSend: (payload: GmailSendInput) => void;
  }

  let { open = false, prefill = null, sending = false, onClose, onSend }: Props = $props();

  let to = $state('');
  let cc = $state('');
  let bcc = $state('');
  let subject = $state('');
  let body = $state('');
  let files = $state<File[]>([]);
  let error = $state('');
  let converting = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();

  // Apply prefill each time the dialog opens (reply flow); reset on close is
  // handled by the parent unmount/remount via `open`.
  let wasOpen = false;
  $effect(() => {
    if (open && !wasOpen) {
      to = prefill?.to ?? '';
      cc = prefill?.cc ?? '';
      subject = prefill?.subject ?? '';
      body = prefill?.body ?? '';
      files = [];
      error = '';
    }
    wasOpen = open;
  });

  const totalAttachmentBytes = $derived(files.reduce((sum, f) => sum + (f.size || 0), 0));
  const tooManyFiles = $derived(files.length > MAX_ATTACHMENTS);
  const tooManyBytes = $derived(totalAttachmentBytes > MAX_ATTACHMENTS_TOTAL_BYTES);
  const canSubmit = $derived(
    !sending &&
      !converting &&
      !tooManyFiles &&
      !tooManyBytes &&
      (to.trim() !== '' || cc.trim() !== '' || bcc.trim() !== '') &&
      body.trim() !== ''
  );

  function onFileInput(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const picked = Array.from(input.files ?? []);
    input.value = '';
    if (!picked.length) return;
    const merged = [...files, ...picked];
    if (merged.length > MAX_ATTACHMENTS) {
      showNotification($t('gmail.tooManyAttachments'), 'error');
      files = merged.slice(0, MAX_ATTACHMENTS);
    } else {
      files = merged;
    }
  }

  function removeFile(index: number): void {
    files = files.filter((_, i) => i !== index);
  }

  async function handleSend(): Promise<void> {
    error = '';
    if (!(to.trim() || cc.trim() || bcc.trim())) {
      error = $t('gmail.recipientRequired');
      return;
    }
    if (!body.trim()) {
      error = $t('gmail.bodyRequired');
      return;
    }
    converting = true;
    try {
      const attachments: OutgoingAttachmentPayload[] = [];
      for (const file of files.slice(0, MAX_ATTACHMENTS)) {
        attachments.push(await fileToBase64Payload(file));
      }
      onSend({
        to: to.trim() || null,
        cc: cc.trim() || null,
        bcc: bcc.trim() || null,
        subject: subject.trim() || null,
        body,
        attachments: attachments.length ? attachments : undefined,
      });
    } catch (e) {
      logger.error(e);
      showNotification($t('gmail.sendError'), 'error');
    } finally {
      converting = false;
    }
  }
</script>

<ModalDialog open={open} title={$t('gmail.compose')} size="lg" onClose={onClose}>
  <form
    class="compose-form"
    onsubmit={(e) => {
      e.preventDefault();
      void handleSend();
    }}
  >
    <label class="field">
      <span class="field-label">{$t('gmail.to')}</span>
      <input class="field-input" type="text" bind:value={to} placeholder="destinatario@example.com" autocomplete="off" />
    </label>
    <div class="field-row">
      <label class="field">
        <span class="field-label">{$t('gmail.cc')}</span>
        <input class="field-input" type="text" bind:value={cc} autocomplete="off" />
      </label>
      <label class="field">
        <span class="field-label">{$t('gmail.bcc')}</span>
        <input class="field-input" type="text" bind:value={bcc} autocomplete="off" />
      </label>
    </div>
    <label class="field">
      <span class="field-label">{$t('gmail.subject')}</span>
      <input class="field-input" type="text" bind:value={subject} />
    </label>
    <label class="field field-grow">
      <span class="field-label">{$t('gmail.bodyLabel')}</span>
      <textarea class="field-input field-textarea" bind:value={body} placeholder={$t('gmail.bodyPlaceholder')}></textarea>
    </label>

    <div class="attachments-block">
      <input
        bind:this={fileInput}
        type="file"
        multiple
        class="file-input-hidden"
        onchange={onFileInput}
        aria-hidden="true"
        tabindex="-1"
      />
      <button type="button" class="attach-btn" onclick={() => fileInput?.click()}>
        <Paperclip size={14} /> {$t('gmail.attach')}
      </button>
      {#if files.length}
        <ul class="picked-files">
          {#each files as file, i (file.name + file.size + i)}
            <li class="picked-file">
              <span class="picked-name" title={file.name}>{file.name}</span>
              <span class="picked-size caption">{(file.size / 1024).toFixed(0)} KB</span>
              <button type="button" class="picked-remove" onclick={() => removeFile(i)} aria-label={$t('gmail.removeAttachment')}>
                <X size={12} />
              </button>
            </li>
          {/each}
        </ul>
        {#if tooManyFiles || tooManyBytes}
          <p class="field-error">{$t('gmail.attachmentsTooLarge')}</p>
        {/if}
      {/if}
    </div>

    {#if error}
      <p class="field-error" role="alert">{error}</p>
    {/if}
  </form>

  {#snippet footer()}
    <button type="button" class="btn-ghost" onclick={onClose} disabled={sending}>{$t('gmail.cancel')}</button>
    <button type="button" class="btn-send" onclick={() => void handleSend()} disabled={!canSubmit}>
      <Send size={14} /> {sending || converting ? $t('gmail.sending') : $t('gmail.send')}
    </button>
  {/snippet}
</ModalDialog>

<style>
  .compose-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .field-input {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 7px 10px;
    font-size: 13px;
    color: var(--text-primary);
    outline: none;
    width: 100%;
    font-family: inherit;
  }

  .field-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 1px;
    border-color: var(--accent);
  }

  .field-textarea {
    min-height: 180px;
    resize: vertical;
    line-height: 1.5;
  }

  .attachments-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .file-input-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  .attach-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    align-self: flex-start;
    background: transparent;
    border: 1px dashed var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 6px 12px;
    cursor: pointer;
  }

  .attach-btn:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .picked-files {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .picked-file {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 12px;
  }

  .picked-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-primary);
  }

  .picked-size {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .picked-remove {
    display: inline-flex;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px;
    flex-shrink: 0;
  }

  .picked-remove:hover {
    color: var(--danger, #e5534b);
  }

  .field-error {
    margin: 0;
    font-size: 12px;
    color: var(--danger, #e5534b);
  }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-secondary);
    font-size: 12px;
    padding: 7px 14px;
    cursor: pointer;
  }

  .btn-ghost:hover:not(:disabled) {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .btn-send {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--accent);
    border: none;
    border-radius: var(--r);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    padding: 7px 16px;
    cursor: pointer;
  }

  .btn-send:hover:not(:disabled) {
    opacity: 0.9;
  }

  .btn-send:disabled,
  .btn-ghost:disabled {
    opacity: 0.5;
    cursor: default;
  }

  @media (max-width: 560px) {
    .field-row {
      grid-template-columns: 1fr;
    }
  }
</style>
