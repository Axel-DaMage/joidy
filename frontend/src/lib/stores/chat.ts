import { writable, get } from 'svelte/store';
import { browser } from '$app/env';
import { api } from '$lib/api';
import { showNotification } from './notifications';
import { SESSION_RESET_EVENT } from './session';
import { logger } from '$lib/utils/logger';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  /** Titles of the notes the answer was grounded in (RAG, #1131). */
  sources?: string[];
}

const STORAGE_KEY = 'joidy_chat_messages';
/** Cap the history sent to the backend so prompts stay bounded. */
const HISTORY_LIMIT = 20;

function loadMessages(): ChatMessage[] {
  if (!browser) return [];
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (m) => m && m.role && typeof m.content === 'string' && typeof m.timestamp === 'number',
    );
  } catch {
    return [];
  }
}

function persistMessages(msgs: ChatMessage[]) {
  if (!browser) return;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(msgs));
  } catch {
    /* quota / private mode — ignore */
  }
}

export const messages = writable<ChatMessage[]>(loadMessages());
export const isLoading = writable(false);
/** True while assistant tokens are actively streaming into the last bubble. */
export const isStreaming = writable(false);
export const suggestions = writable<string[]>([]);
/** Text of the last user message that failed to send — drives the retry button (#1131). */
export const chatError = writable<string | null>(null);
export const sessionId = writable<number | null>(null);

// Drop chat history on session reset (logout / 401) so the next user on the
// same browser profile never sees the previous conversation (#1305). The
// backend session id and any streaming/error state also point at the old
// user — reset them too (#1325).
if (browser) {
  window.addEventListener(SESSION_RESET_EVENT, () => {
    messages.set([]);
    isLoading.set(false);
    suggestions.set([]);
    isStreaming.set(false);
    chatError.set(null);
    sessionId.set(null);
    historyLoaded = false;
  });
}

messages.subscribe((msgs) => persistMessages(msgs));

let historyLoaded = false;

/** Restore the persisted conversation from the backend once per page load (#1131 AC2). */
export async function loadHistory(): Promise<void> {
  if (!browser || historyLoaded) return;
  historyLoaded = true;
  try {
    const h = await api.ai.chatHistory();
    if (h.session_id != null) sessionId.set(h.session_id);
    if (h.messages && h.messages.length) {
      messages.set(
        h.messages.map((m) => ({
          role: m.role,
          content: m.content,
          timestamp: m.ts ?? Date.now(),
        })),
      );
    }
  } catch (err) {
    logger.warn('Could not load chat history:', err);
  }
}

function wireMessages(): { role: 'user' | 'assistant'; content: string }[] {
  return get(messages)
    .slice(-HISTORY_LIMIT)
    .map((m) => ({ role: m.role, content: m.content }));
}

function setLastAssistant(updater: (m: ChatMessage) => ChatMessage) {
  messages.update((msgs) => {
    if (!msgs.length) return msgs;
    const copy = [...msgs];
    copy[copy.length - 1] = updater(copy[copy.length - 1]);
    return copy;
  });
}

function dropTrailingAssistant() {
  messages.update((msgs) =>
    msgs.length && msgs[msgs.length - 1].role === 'assistant' ? msgs.slice(0, -1) : msgs,
  );
}

/**
 * Send a user message and stream the AI response (#1131).
 *
 * ``reuseLast`` resends the message already sitting at the tail of the
 * conversation (retry path) instead of appending a new bubble.
 */
export async function sendMessage(text: string, opts?: { reuseLast?: boolean }): Promise<void> {
  const content = text.trim();
  if (!content) return;

  if (!opts?.reuseLast) {
    const userMsg: ChatMessage = { role: 'user', content, timestamp: Date.now() };
    messages.update((m) => [...m, userMsg]);
  } else {
    // Retry: normalize the tail to the failed user message — drop a degraded
    // assistant bubble left behind by the failed attempt.
    dropTrailingAssistant();
  }
  isLoading.set(true);
  isStreaming.set(false);
  chatError.set(null);
  suggestions.set([]);

  const history = wireMessages();

  let streamedText = '';
  let assistantStarted = false;
  let assistantSources: string[] | undefined;

  const appendToken = (t: string) => {
    streamedText += t;
    if (!assistantStarted) {
      assistantStarted = true;
      isStreaming.set(true);
      messages.update((m) => [
        ...m,
        { role: 'assistant', content: streamedText, timestamp: Date.now() },
      ]);
    } else {
      setLastAssistant((m) => ({ ...m, content: streamedText }));
    }
  };

  try {
    const result = await api.ai.chatStream(history, get(sessionId), {
      onSession: (id) => sessionId.set(id),
      onMeta: (meta) => {
        assistantSources = meta?.sources;
      },
      onToken: appendToken,
      onDone: (d) => {
        if (d?.suggestions?.length) suggestions.set(d.suggestions);
      },
    });

    if (result.status === 'streamed') {
      if (assistantStarted) {
        setLastAssistant((m) => ({ ...m, sources: assistantSources }));
      } else {
        // Stream ended without tokens — treat as a failed attempt.
        chatError.set(content);
      }
    } else {
      // JSON fallback (AI disabled / unavailable / degraded).
      if (result.session_id != null) sessionId.set(result.session_id);
      const answer =
        result.response ?? 'Lo siento, ocurrió un error al contactar al asistente.';
      messages.update((m) => [
        ...m,
        {
          role: 'assistant',
          content: answer,
          timestamp: Date.now(),
          sources: result.sources ?? assistantSources,
        },
      ]);
      if (result.suggestions?.length) suggestions.set(result.suggestions);
      if (result.status !== 'success' && result.status !== 'streamed') {
        chatError.set(content);
      }
    }
  } catch (err) {
    logger.error('Chat request failed:', err);
    // Remove the half-streamed assistant bubble so the retry starts clean.
    if (assistantStarted) dropTrailingAssistant();
    chatError.set(content);
    showNotification('No se pudo obtener respuesta del asistente.', 'error');
  } finally {
    isLoading.set(false);
    isStreaming.set(false);
  }
}

/** Resend the last failed user message (retry button, #1131). */
export async function retryLast(): Promise<void> {
  const failed = get(chatError);
  if (!failed) return;
  chatError.set(null);
  await sendMessage(failed, { reuseLast: true });
}

/** Clear all messages, suggestions, server-side history and the session id. */
export function clearChat(): void {
  messages.set([]);
  suggestions.set([]);
  chatError.set(null);
  sessionId.set(null);
  if (browser) {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    api.ai.clearChatHistory().catch((err) => logger.warn('Could not clear chat history:', err));
  }
}
