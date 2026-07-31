import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { api } from '$lib/api';
import { showNotification } from './notifications';
import { logger } from '$lib/utils/logger';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

const STORAGE_KEY = 'joidy_chat_messages';

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
export const suggestions = writable<string[]>([]);

messages.subscribe((msgs) => persistMessages(msgs));

function getMessages(): ChatMessage[] {
  let current: ChatMessage[] = [];
  messages.subscribe((m) => (current = m))();
  return current;
}

/** Send a user message and append the AI response. */
export async function sendMessage(text: string): Promise<void> {
  const content = text.trim();
  if (!content) return;

  // Capture current history before appending the new user message.
  const prior = getMessages();
  const userMsg: ChatMessage = { role: 'user', content, timestamp: Date.now() };
  messages.update((m) => [...m, userMsg]);
  isLoading.set(true);
  suggestions.set([]);

  const history = [...prior, { role: 'user' as const, content }];

  try {
    const res = await api.ai.chat(history);
    const aiMsg: ChatMessage = {
      role: 'assistant',
      content: res.response,
      timestamp: Date.now(),
    };
    messages.update((m) => [...m, aiMsg]);
    if (res.suggestions && res.suggestions.length) {
      suggestions.set(res.suggestions);
    }
  } catch (err) {
    logger.error('Chat request failed:', err);
    showNotification('No se pudo obtener respuesta del asistente.', 'error');
    const aiMsg: ChatMessage = {
      role: 'assistant',
      content: 'Lo siento, ocurrió un error al contactar al asistente. Inténtalo de nuevo.',
      timestamp: Date.now(),
    };
    messages.update((m) => [...m, aiMsg]);
  } finally {
    isLoading.set(false);
  }
}

/** Clear all messages and suggestions. */
export function clearChat(): void {
  messages.set([]);
  suggestions.set([]);
  if (browser) {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }
}
