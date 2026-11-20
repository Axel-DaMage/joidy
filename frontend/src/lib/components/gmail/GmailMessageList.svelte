<script lang="ts">
  import type { SvelteMap } from 'svelte/reactivity';
  import type { GmailMessage, GmailMessageSummary } from '$lib/api';
  import { senderLabel, formatEmailDate } from '$lib/utils/gmail';
  import { t } from 'svelte-i18n';
  import MailOpen from 'lucide-svelte/icons/mail-open';
  import Archive from 'lucide-svelte/icons/archive';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import ArchiveRestore from 'lucide-svelte/icons/archive-restore';
  import Star from 'lucide-svelte/icons/star';

  interface Props {
    messages: GmailMessageSummary[];
    /** Hydrated details keyed by message id (background-fetched for subject/sender). */
    details: SvelteMap<string, GmailMessage>;
    canModify: boolean;
    /** Current label filter — drives which row actions make sense. */
    labelFilter: string;
    onOpen: (message: GmailMessageSummary) => void;
    onArchive: (message: GmailMessageSummary) => void;
    onTrash: (message: GmailMessageSummary) => void;
    onUntrash: (message: GmailMessageSummary) => void;
    onToggleRead: (message: GmailMessageSummary) => void;
  }

  let {
    messages,
    details,
    canModify,
    labelFilter,
    onOpen,
    onArchive,
    onTrash,
    onUntrash,
    onToggleRead,
  }: Props = $props();

  const hasLabel = (m: GmailMessageSummary, label: string): boolean =>
    (m.label_ids || []).includes(label);

  const isUnread = (m: GmailMessageSummary): boolean => hasLabel(m, 'UNREAD');
  const inTrash = $derived(labelFilter === 'TRASH');

  /** Row title: hydrated subject wins; until then the Gmail snippet is the
   *  only text the list endpoint provides. */
  function titleFor(m: GmailMessageSummary): string {
    const detail = m.id ? details.get(m.id) : undefined;
    const subject = detail?.headers?.subject;
    if (subject) return subject;
    return m.snippet || $t('gmail.noSubject');
  }

  function senderFor(m: GmailMessageSummary): string {
    const detail = m.id ? details.get(m.id) : undefined;
    return senderLabel(detail?.headers) || '…';
  }
</script>

<div class="gmail-list">
  {#each messages as message (message.id ?? message.thread_id ?? message.snippet)}
    {@const unread = isUnread(message)}
    {@const starred = hasLabel(message, 'STARRED')}
    {@const title = titleFor(message)}
    {@const sender = senderFor(message)}
    <div
      class="gmail-item"
      class:unread
      role="button"
      tabindex="0"
      onclick={() => onOpen(message)}
      onkeydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(message);
        }
      }}
    >
      <div class="gmail-main">
        <div class="gmail-top">
          <span class="sender" class:unread-text={unread}>{sender}</span>
          <span class="when">{formatEmailDate(message.internal_date)}</span>
        </div>
        <div class="subject" class:unread-text={unread}>
          {#if starred}<span class="star"><Star size={11} /></span>{/if}
          {title}
        </div>
        {#if message.snippet && title !== message.snippet}
          <div class="snippet caption">{message.snippet}</div>
        {/if}
      </div>
      <div class="gmail-side">
        {#if unread}<span class="dot unread-dot" title={$t('gmail.labels.unread')}></span>{/if}
        {#if canModify}
          <div class="gmail-ops">
            <button
              onclick={(e) => {
                e.stopPropagation();
                onToggleRead(message);
              }}
              title={unread ? $t('gmail.markRead') : $t('gmail.markUnread')}
              aria-label={unread ? $t('gmail.markRead') : $t('gmail.markUnread')}
            >
              <MailOpen size={13} />
            </button>
            {#if inTrash}
              <button
                onclick={(e) => {
                  e.stopPropagation();
                  onUntrash(message);
                }}
                title={$t('gmail.untrash')}
                aria-label={$t('gmail.untrash')}
              >
                <ArchiveRestore size={13} />
              </button>
            {:else}
              <button
                onclick={(e) => {
                  e.stopPropagation();
                  onArchive(message);
                }}
                title={$t('gmail.archive')}
                aria-label={$t('gmail.archive')}
              >
                <Archive size={13} />
              </button>
              <button
                onclick={(e) => {
                  e.stopPropagation();
                  onTrash(message);
                }}
                title={$t('gmail.trash')}
                aria-label={$t('gmail.trash')}
              >
                <Trash2 size={13} />
              </button>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .gmail-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    background: var(--surface);
  }

  .gmail-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
  }

  .gmail-item:last-child {
    border-bottom: none;
  }

  .gmail-item.unread {
    background: color-mix(in srgb, var(--accent) 6%, transparent);
  }

  .gmail-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .gmail-top {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }

  .sender {
    font-size: 12px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .when {
    flex-shrink: 0;
    font-size: 11px;
    color: var(--text-muted);
  }

  .subject {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .star {
    color: var(--xp, #e8b931);
    flex-shrink: 0;
  }

  .unread-text {
    font-weight: 700;
    color: var(--text-primary);
  }

  .snippet {
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .gmail-side {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  .unread-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
  }

  .gmail-ops {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.15s ease;
  }

  .gmail-item:hover .gmail-ops,
  .gmail-item:focus-within .gmail-ops {
    opacity: 1;
  }

  /* Touch devices have no hover: keep the row actions reachable. */
  @media (hover: none) {
    .gmail-ops {
      opacity: 1;
    }
  }

  .gmail-ops button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    padding: 4px 6px;
    cursor: pointer;
  }

  .gmail-ops button:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }
</style>
