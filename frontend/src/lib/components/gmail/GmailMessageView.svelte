<script lang="ts">
  import { SvelteSet } from 'svelte/reactivity';
  import type { GmailAttachmentMeta, GmailMessage } from '$lib/api';
  import {
    sanitizeEmailHtml,
    senderLabel,
    formatEmailDate,
    formatBytes,
    downloadGmailAttachment,
  } from '$lib/utils/gmail';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import ArrowLeft from 'lucide-svelte/icons/arrow-left';
  import Archive from 'lucide-svelte/icons/archive';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import ArchiveRestore from 'lucide-svelte/icons/archive-restore';
  import MailOpen from 'lucide-svelte/icons/mail-open';
  import Reply from 'lucide-svelte/icons/reply';
  import Paperclip from 'lucide-svelte/icons/paperclip';
  import Download from 'lucide-svelte/icons/download';

  interface Props {
    message: GmailMessage;
    canModify: boolean;
    canSend: boolean;
    loading?: boolean;
    onBack: () => void;
    onArchive: (message: GmailMessage) => void;
    onTrash: (message: GmailMessage) => void;
    onUntrash: (message: GmailMessage) => void;
    onToggleRead: (message: GmailMessage) => void;
    onReply: (message: GmailMessage) => void;
  }

  let {
    message,
    canModify,
    canSend,
    loading = false,
    onBack,
    onArchive,
    onTrash,
    onUntrash,
    onToggleRead,
    onReply,
  }: Props = $props();

  const inTrash = $derived((message.label_ids || []).includes('TRASH'));
  const isUnread = $derived((message.label_ids || []).includes('UNREAD'));

  /**
   * body_html is RAW sender-controlled HTML — sanitize before {@html}.
   * sanitizeEmailHtml returns '' without a DOM (SSR safety) and strips
   * scripts, handlers, javascript: URLs, style/class and active embeds.
   */
  const sanitizedHtml = $derived(sanitizeEmailHtml(message.body_html));
  const hasHtml = $derived(!!sanitizedHtml);
  const hasText = $derived(!!message.body_text?.trim());

  const subject = $derived(message.headers?.subject || $t('gmail.noSubject'));
  const fromLabel = $derived(senderLabel(message.headers));
  const toLabel = $derived(message.headers?.to || '');
  const ccLabel = $derived(message.headers?.cc || '');
  const dateLabel = $derived(formatEmailDate(message.internal_date || message.headers?.date));

  const downloading = new SvelteSet<string>();

  async function download(att: GmailAttachmentMeta): Promise<void> {
    const key = att.attachment_id || att.filename || '';
    if (!key || downloading.has(key)) return;
    downloading.add(key);
    try {
      await downloadGmailAttachment(message, att);
    } catch (e) {
      logger.error(e);
      showNotification($t('gmail.downloadError'), 'error');
    } finally {
      downloading.delete(key);
    }
  }
</script>

<div class="gmail-view">
  <div class="gmail-view-toolbar">
    <button class="back-btn" onclick={onBack}>
      <ArrowLeft size={15} /> {$t('gmail.back')}
    </button>
    {#if canModify}
      <div class="gmail-view-actions">
        <button onclick={() => onToggleRead(message)} title={isUnread ? $t('gmail.markRead') : $t('gmail.markUnread')}>
          <MailOpen size={14} /> {isUnread ? $t('gmail.markRead') : $t('gmail.markUnread')}
        </button>
        {#if inTrash}
          <button onclick={() => onUntrash(message)}>
            <ArchiveRestore size={14} /> {$t('gmail.untrash')}
          </button>
        {:else}
          <button onclick={() => onArchive(message)}>
            <Archive size={14} /> {$t('gmail.archive')}
          </button>
          <button onclick={() => onTrash(message)}>
            <Trash2 size={14} /> {$t('gmail.trash')}
          </button>
        {/if}
        {#if canSend}
          <button onclick={() => onReply(message)}>
            <Reply size={14} /> {$t('gmail.reply')}
          </button>
        {/if}
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="loading-state caption">{$t('gmail.loading')}</div>
  {:else}
    <article class="gmail-card">
      <header class="gmail-head">
        <h2 class="gmail-subject">{subject}</h2>
        <dl class="gmail-meta">
          <div class="meta-row">
            <dt>{$t('gmail.from')}</dt>
            <dd>{fromLabel || '—'}</dd>
          </div>
          {#if toLabel}
            <div class="meta-row">
              <dt>{$t('gmail.to')}</dt>
              <dd>{toLabel}</dd>
            </div>
          {/if}
          {#if ccLabel}
            <div class="meta-row">
              <dt>CC</dt>
              <dd>{ccLabel}</dd>
            </div>
          {/if}
          {#if dateLabel}
            <div class="meta-row">
              <dt>{$t('gmail.dateLabel')}</dt>
              <dd>{dateLabel}</dd>
            </div>
          {/if}
        </dl>
      </header>

      <div class="gmail-body">
        {#if hasHtml}
          <!-- body_html is raw sender HTML — rendered only after DOMPurify
               sanitization in sanitizeEmailHtml; never render it raw. -->
          {@html sanitizedHtml}
        {:else if hasText}
          <pre class="gmail-text">{message.body_text}</pre>
        {:else}
          <p class="gmail-empty-body">{$t('gmail.noBody')}</p>
        {/if}
        {#if message.body_truncated}
          <p class="gmail-truncated caption">{$t('gmail.bodyTruncated')}</p>
        {/if}
      </div>

      {#if message.attachments?.length}
        <footer class="gmail-attachments">
          <div class="attachments-title">
            <Paperclip size={13} /> {$t('gmail.attachments')}
            <span class="caption">({message.attachments.length})</span>
          </div>
          <ul>
            {#each message.attachments as att (att.attachment_id ?? att.filename ?? att.part_id)}
              {@const key = att.attachment_id || att.filename || ''}
              <li class="attachment-item">
                <span class="attachment-name" title={att.filename || ''}>
                  {att.filename || $t('gmail.noSubject')}
                </span>
                <span class="attachment-size caption">{formatBytes(att.size)}</span>
                <button
                  class="attachment-dl"
                  onclick={() => download(att)}
                  disabled={downloading.has(key)}
                  title={$t('gmail.download')}
                  aria-label={$t('gmail.download')}
                >
                  <Download size={13} />
                </button>
              </li>
            {/each}
          </ul>
        </footer>
      {/if}
    </article>
  {/if}
</div>

<style>
  .gmail-view {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .gmail-view-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 5px 10px;
    cursor: pointer;
  }

  .back-btn:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .gmail-view-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .gmail-view-actions button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 12px;
    padding: 5px 10px;
    cursor: pointer;
  }

  .gmail-view-actions button:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .loading-state {
    text-align: center;
    padding: 24px 0;
    color: var(--text-muted);
  }

  .gmail-card {
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    overflow: hidden;
  }

  .gmail-head {
    padding: 16px 18px 12px;
    border-bottom: 1px solid var(--border);
  }

  .gmail-subject {
    margin: 0 0 10px;
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary);
    word-break: break-word;
  }

  .gmail-meta {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .meta-row {
    display: flex;
    gap: 10px;
    font-size: 12px;
    min-width: 0;
  }

  .meta-row dt {
    flex-shrink: 0;
    width: 44px;
    color: var(--text-muted);
    font-weight: 600;
  }

  .meta-row dd {
    margin: 0;
    color: var(--text-secondary);
    word-break: break-word;
  }

  .gmail-body {
    padding: 16px 18px;
    color: var(--text-primary);
    font-size: 14px;
    line-height: 1.55;
    overflow-x: auto;
  }

  /* {@html} content is NOT scoped by Svelte — style it via :global. */
  .gmail-body :global(p) {
    margin: 0 0 0.8em;
  }
  .gmail-body :global(a) {
    color: var(--accent);
  }
  .gmail-body :global(img) {
    max-width: 100%;
    height: auto;
  }
  .gmail-body :global(table) {
    border-collapse: collapse;
    max-width: 100%;
  }
  .gmail-body :global(blockquote) {
    margin: 0.5em 0;
    padding-left: 12px;
    border-left: 3px solid var(--border);
    color: var(--text-secondary);
  }
  .gmail-body :global(pre),
  .gmail-body :global(code) {
    font-family: var(--font-mono, monospace);
    font-size: 0.9em;
  }

  .gmail-text {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: inherit;
    line-height: inherit;
  }

  .gmail-empty-body {
    margin: 0;
    color: var(--text-muted);
    font-style: italic;
  }

  .gmail-truncated {
    margin: 12px 0 0;
    color: var(--text-muted);
    border-top: 1px dashed var(--border);
    padding-top: 8px;
  }

  .gmail-attachments {
    border-top: 1px solid var(--border);
    padding: 12px 18px;
  }

  .attachments-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .gmail-attachments ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .attachment-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--elevated, transparent);
  }

  .attachment-name {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .attachment-size {
    flex-shrink: 0;
    color: var(--text-muted);
  }

  .attachment-dl {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-secondary);
    padding: 4px 6px;
    cursor: pointer;
    flex-shrink: 0;
  }

  .attachment-dl:hover:not(:disabled) {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .attachment-dl:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
