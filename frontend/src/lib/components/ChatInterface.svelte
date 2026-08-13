<script lang="ts">
  import { tick } from 'svelte';
  import { Send, Sparkles, Trash2, Loader2 } from 'lucide-svelte';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';
  import { messages, isLoading, suggestions, sendMessage, clearChat } from '$lib/stores/chat';
  import { t } from 'svelte-i18n';

  marked.use({ gfm: true, breaks: true });

  let input = $state('');
  let scrollContainer: HTMLDivElement | null = $state(null);

  const defaultSuggestions = [
    '¿Qué debería aprender esta semana?',
    'Ayúdame a definir una nueva meta',
    '¿Cómo organizo mejor mis notas?',
    'Dame un resumen de mi progreso',
  ];

  let isEmpty = $derived($messages.length === 0);
  let activeSuggestions = $derived(isEmpty ? defaultSuggestions : $suggestions);

  async function scrollToBottom() {
    await tick();
    if (scrollContainer) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
  }

  $effect(() => {
    $messages.length;
    $isLoading;
    scrollToBottom();
  });

  function renderMarkdown(md: string): string {
    if (!md.trim()) return '';
    return DOMPurify.sanitize(String(marked.parse(md)));
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || $isLoading) return;
    input = '';
    await sendMessage(text);
  }

  async function handleSuggestion(text: string) {
    if ($isLoading) return;
    input = '';
    await sendMessage(text);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }
</script>

<div class="chat">
  <div class="chat-header">
    <div class="chat-title">
      <Sparkles size={18} />
      <span>{$t('chat.assistantName')}</span>
    </div>
    {#if !isEmpty}
      <button class="clear-btn" onclick={clearChat} title={$t('chat.clearConversation')}>
        <Trash2 size={15} />
      </button>
    {/if}
  </div>

  <div class="chat-messages" bind:this={scrollContainer}>
    {#if isEmpty}
      <div class="empty-state">
        <div class="empty-icon"><Sparkles size={28} /></div>
        <h3>{$t('chat.welcomeTitle')}</h3>
        <p class="empty-hint">
          Pregunta sobre tus notas, metas y progreso. Joidy usa tu contexto personal para responder.
        </p>
        <div class="suggestions">
          {#each defaultSuggestions as s}
            <button class="suggestion-chip" onclick={() => handleSuggestion(s)} disabled={$isLoading}>
              {s}
            </button>
          {/each}
        </div>
      </div>
    {:else}
      {#each $messages as msg (msg.timestamp)}
        <div class="msg {msg.role}">
          <div class="bubble">
            {#if msg.role === 'assistant'}
              <div class="markdown">{@html renderMarkdown(msg.content)}</div>
            {:else}
              <p>{msg.content}</p>
            {/if}
          </div>
        </div>
      {/each}

      {#if $isLoading}
        <div class="msg assistant">
          <div class="bubble loading-bubble">
            <Loader2 size={16} class="spin" />
            <span>{$t('chat.thinking')}</span>
          </div>
        </div>
      {/if}

      {#if activeSuggestions.length && !$isLoading}
        <div class="followup-suggestions">
          {#each activeSuggestions as s}
            <button class="suggestion-chip small" onclick={() => handleSuggestion(s)}>
              {s}
            </button>
          {/each}
        </div>
      {/if}
    {/if}
  </div>

  <div class="chat-input">
    <textarea
      bind:value={input}
      onkeydown={handleKeydown}
      placeholder={$t('chat.inputPlaceholder')}
      rows="1"
      disabled={$isLoading}
    ></textarea>
    <button class="send-btn" onclick={handleSend} disabled={$isLoading || !input.trim()} title={$t('chat.send')}>
      <Send size={17} />
    </button>
  </div>
</div>

<style>
  .chat {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: var(--surface, #000);
    border: 1px solid var(--border, #1a1a1a);
    border-radius: var(--r-lg, 8px);
    overflow: hidden;
  }
  .chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s3, 12px) var(--s4, 16px);
    border-bottom: 1px solid var(--border, #1a1a1a);
    flex-shrink: 0;
  }
  .chat-title {
    display: flex;
    align-items: center;
    gap: var(--s2, 8px);
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-primary, #fff);
  }
  .clear-btn {
    background: none;
    border: none;
    color: var(--text-muted, #888);
    cursor: pointer;
    padding: var(--s1, 4px);
    border-radius: var(--r, 4px);
    display: flex;
    transition: color var(--t-fast, 50ms), background var(--t-fast, 50ms);
  }
  .clear-btn:hover {
    color: var(--error, #ef4444);
    background: var(--hover, #0c0c0c);
  }
  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: var(--s4, 16px);
    display: flex;
    flex-direction: column;
    gap: var(--s3, 12px);
    min-height: 0;
  }
  .empty-state {
    margin: auto;
    text-align: center;
    max-width: 460px;
    padding: var(--s5, 24px);
  }
  .empty-icon {
    color: var(--xp, #c8a96e);
    margin-bottom: var(--s3, 12px);
    display: flex;
    justify-content: center;
  }
  .empty-state h3 {
    margin: 0 0 var(--s2, 8px);
    font-size: 1.05rem;
    color: var(--text-primary, #fff);
  }
  .empty-hint {
    color: var(--text-muted, #888);
    font-size: 0.85rem;
    margin: 0 0 var(--s5, 24px);
    line-height: 1.5;
  }
  .suggestions {
    display: flex;
    flex-direction: column;
    gap: var(--s2, 8px);
  }
  .suggestion-chip {
    text-align: left;
    background: var(--elevated, #000);
    border: 1px solid var(--border, #1a1a1a);
    color: var(--text-secondary, #d0d0d0);
    padding: var(--s3, 12px) var(--s4, 16px);
    border-radius: var(--r-lg, 8px);
    cursor: pointer;
    font-size: 0.85rem;
    transition: border-color var(--t-fast, 50ms), background var(--t-fast, 50ms);
  }
  .suggestion-chip:hover:not(:disabled) {
    border-color: var(--xp, #c8a96e);
    background: var(--hover, #0c0c0c);
  }
  .suggestion-chip:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .suggestion-chip.small {
    padding: var(--s2, 8px) var(--s3, 12px);
    font-size: 0.8rem;
  }
  .followup-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2, 8px);
    padding-top: var(--s2, 8px);
  }
  .msg {
    display: flex;
    max-width: 100%;
  }
  .msg.user {
    justify-content: flex-end;
  }
  .msg.assistant {
    justify-content: flex-start;
  }
  .bubble {
    max-width: 80%;
    padding: var(--s3, 12px) var(--s4, 16px);
    border-radius: var(--r-lg, 8px);
    font-size: 0.875rem;
    line-height: 1.55;
    word-wrap: break-word;
    overflow-wrap: anywhere;
  }
  .msg.user .bubble {
    background: var(--xp, #c8a96e);
    color: #1a1a1a;
    border-bottom-right-radius: var(--r, 4px);
  }
  .msg.user .bubble p {
    margin: 0;
    white-space: pre-wrap;
  }
  .msg.assistant .bubble {
    background: var(--elevated, #000);
    border: 1px solid var(--border, #1a1a1a);
    color: var(--text-primary, #fff);
    border-bottom-left-radius: var(--r, 4px);
  }
  .loading-bubble {
    display: flex;
    align-items: center;
    gap: var(--s2, 8px);
    color: var(--text-muted, #888);
    font-style: italic;
  }
  .spin {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .markdown :global(p) { margin: 0 0 var(--s2, 8px); }
  .markdown :global(p:last-child) { margin-bottom: 0; }
  .markdown :global(ul),
  .markdown :global(ol) { margin: 0 0 var(--s2, 8px); padding-left: var(--s5, 24px); }
  .markdown :global(li) { margin: var(--s1, 4px) 0; }
  .markdown :global(h1),
  .markdown :global(h2),
  .markdown :global(h3) { margin: var(--s3, 12px) 0 var(--s2, 8px); font-size: 0.95rem; }
  .markdown :global(code) {
    background: var(--hover, #0c0c0c);
    padding: 2px var(--s1, 4px);
    border-radius: var(--r, 4px);
    font-family: var(--font-mono, monospace);
    font-size: 0.8rem;
  }
  .markdown :global(pre) {
    background: var(--hover, #0c0c0c);
    padding: var(--s3, 12px);
    border-radius: var(--r, 4px);
    overflow-x: auto;
    margin: 0 0 var(--s2, 8px);
  }
  .markdown :global(pre code) { background: none; padding: 0; }
  .markdown :global(blockquote) {
    border-left: 3px solid var(--xp, #c8a96e);
    margin: 0 0 var(--s2, 8px);
    padding-left: var(--s3, 12px);
    color: var(--text-muted, #888);
  }
  .markdown :global(a) { color: var(--link, #3b82f6); }
  .markdown :global(strong) { font-weight: 600; }
  .chat-input {
    display: flex;
    align-items: flex-end;
    gap: var(--s2, 8px);
    padding: var(--s3, 12px) var(--s4, 16px);
    border-top: 1px solid var(--border, #1a1a1a);
    flex-shrink: 0;
  }
  .chat-input textarea {
    flex: 1;
    resize: none;
    max-height: 120px;
    background: var(--elevated, #000);
    border: 1px solid var(--border, #1a1a1a);
    border-radius: var(--r-lg, 8px);
    color: var(--text-primary, #fff);
    padding: var(--s3, 12px);
    font-family: var(--font-sans, sans-serif);
    font-size: 0.875rem;
    line-height: 1.5;
    outline: none;
    transition: border-color var(--t-fast, 50ms);
  }
  .chat-input textarea:focus {
    border-color: var(--xp, #c8a96e);
  }
  .chat-input textarea::placeholder {
    color: var(--text-muted, #888);
  }
  .send-btn {
    flex-shrink: 0;
    background: var(--xp, #c8a96e);
    color: #1a1a1a;
    border: none;
    border-radius: var(--r-lg, 8px);
    padding: var(--s3, 12px);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity var(--t-fast, 50ms), background var(--t-fast, 50ms);
  }
  .send-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  .send-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  @media (max-width: 768px) {
    .bubble { max-width: 90%; }
  }
</style>
