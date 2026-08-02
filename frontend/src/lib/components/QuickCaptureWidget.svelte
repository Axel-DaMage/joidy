<script lang="ts">
  import { _ } from 'svelte-i18n';
  import { createNote } from '$lib/stores/notes';
  import { showNotification } from '$lib/stores/notifications';
  import { showXPGain } from '$lib/stores/gamification';
  import { Send } from 'lucide-svelte';

  let text = $state('');
  let submitting = $state(false);

  async function handleCapture(e: MouseEvent) {
    const trimmed = text.trim();
    if (!trimmed || submitting) return;
    submitting = true;
    const title = trimmed.split('\n')[0].slice(0, 60) || $_('quickCapture.defaultTitle');
    const note = await createNote(title, trimmed, ['inbox'], null);
    submitting = false;
    if (note) {
      text = '';
      showNotification($_('quickCapture.created'), 'success');
      showXPGain(10, e.clientX, e.clientY);
    } else {
      showNotification($_('quickCapture.error'), 'error');
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleCapture(e as unknown as MouseEvent);
    }
  }
</script>

<div class="quick-capture">
  <textarea
    bind:value={text}
    placeholder={$_('quickCapture.placeholder')}
    onkeydown={handleKeydown}
    rows="2"
    aria-label={$_('quickCapture.placeholder')}
  ></textarea>
  <button
    class="qc-btn"
    onclick={handleCapture}
    disabled={submitting || !text.trim()}
    aria-label={$_('common.save')}
  >
    {#if submitting}
      <span class="qc-spinner"></span>
    {:else}
      <Send size={14} />
    {/if}
    <span>{submitting ? $_('common.saving') : $_('common.save')}</span>
  </button>
</div>

<style>
  .quick-capture {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px;
  }

  textarea {
    width: 100%;
    min-height: 44px;
    max-height: 120px;
    resize: vertical;
    background: var(--surface, rgba(255, 255, 255, 0.05));
    border: 1px solid var(--border, rgba(255, 255, 255, 0.1));
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
    font-family: inherit;
    color: var(--text, inherit);
    line-height: 1.4;
  }

  textarea:focus {
    outline: none;
    border-color: var(--accent, #4f9cf9);
  }

  textarea::placeholder {
    color: var(--text-muted, rgba(255, 255, 255, 0.4));
  }

  .qc-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 6px 14px;
    border: none;
    border-radius: 8px;
    background: var(--accent, #4f9cf9);
    color: white;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
    align-self: flex-end;
  }

  .qc-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .qc-btn:not(:disabled):hover {
    opacity: 0.85;
  }

  .qc-spinner {
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: qc-spin 0.6s linear infinite;
  }

  @keyframes qc-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
