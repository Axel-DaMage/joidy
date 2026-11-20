import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// Mock $app/env so `browser` is true (jsdom provides sessionStorage).
vi.mock('$app/env', () => ({ browser: true, dev: false }));

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    ai: {
      chat: vi.fn(),
      chatStream: vi.fn(),
      chatHistory: vi.fn(),
      clearChatHistory: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

vi.mock('./notifications', () => ({ showNotification: vi.fn() }));

import {
  messages,
  isLoading,
  isStreaming,
  suggestions,
  chatError,
  sessionId,
  sendMessage,
  retryLast,
  clearChat,
  loadHistory,
} from './chat';

function reset() {
  messages.set([]);
  suggestions.set([]);
  chatError.set(null);
  sessionId.set(null);
  isLoading.set(false);
  isStreaming.set(false);
  sessionStorage.clear();
  vi.clearAllMocks();
  apiMock.ai.chatHistory.mockResolvedValue({ session_id: null, messages: [] });
  apiMock.ai.clearChatHistory.mockResolvedValue({ status: 'cleared' });
}

/** Configure chatStream to emit the given frames then resolve 'streamed'. */
function mockStream(emit: (h: Record<string, (v?: unknown) => void>) => void) {
  apiMock.ai.chatStream.mockImplementation(async (_msgs, _sid, handlers) => {
    emit(handlers);
    return { status: 'streamed' };
  });
}

describe('chat store (#1131)', () => {
  beforeEach(reset);

  it('streams tokens into an assistant bubble and stores sources', async () => {
    mockStream((h) => {
      h.onSession?.(42);
      h.onMeta?.({ sources: ['Note A'] });
      h.onToken?.('Hello');
      h.onToken?.(' world');
      h.onDone?.({ suggestions: ['next q'] });
    });

    await sendMessage('hola');

    const msgs = get(messages);
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant']);
    expect(msgs[1].content).toBe('Hello world');
    expect(msgs[1].sources).toEqual(['Note A']);
    expect(get(suggestions)).toEqual(['next q']);
    expect(get(sessionId)).toBe(42);
    expect(get(chatError)).toBeNull();
  });

  it('handles a JSON fallback response (AI disabled)', async () => {
    apiMock.ai.chatStream.mockResolvedValue({
      status: 'disabled',
      response: 'IA deshabilitada',
      suggestions: [],
      session_id: 7,
    });

    await sendMessage('hola');

    const msgs = get(messages);
    expect(msgs[msgs.length - 1].content).toBe('IA deshabilitada');
    expect(get(sessionId)).toBe(7);
    expect(get(chatError)).toBe('hola');
  });

  it('sets chatError and drops the partial bubble on stream failure', async () => {
    apiMock.ai.chatStream.mockImplementation(async (_m, _s, handlers) => {
      handlers.onToken?.('partial');
      throw new Error('network down');
    });

    await sendMessage('failing msg');

    // The partial assistant bubble is removed so a retry starts clean.
    expect(get(messages).map((m) => m.role)).toEqual(['user']);
    expect(get(chatError)).toBe('failing msg');
  });

  it('retryLast resends without duplicating the user bubble', async () => {
    apiMock.ai.chatStream.mockRejectedValueOnce(new Error('boom'));
    await sendMessage('retry me');
    expect(get(chatError)).toBe('retry me');

    mockStream((h) => {
      h.onToken?.('ok');
      h.onDone?.({});
    });
    await retryLast();

    const msgs = get(messages);
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant']);
    expect(msgs.filter((m) => m.role === 'user' && m.content === 'retry me')).toHaveLength(1);
    expect(get(chatError)).toBeNull();
    // Second call carries the same single user turn.
    expect(apiMock.ai.chatStream).toHaveBeenCalledTimes(2);
    const secondHistory = apiMock.ai.chatStream.mock.calls[1][0];
    expect(secondHistory).toEqual([{ role: 'user', content: 'retry me' }]);
  });

  it('loadHistory restores persisted messages once', async () => {
    apiMock.ai.chatHistory.mockResolvedValue({
      session_id: 9,
      messages: [
        { role: 'user', content: 'q1', ts: 1000 },
        { role: 'assistant', content: 'a1', ts: 1001 },
      ],
    });

    await loadHistory();

    const msgs = get(messages);
    expect(msgs).toHaveLength(2);
    expect(msgs[0]).toMatchObject({ role: 'user', content: 'q1', timestamp: 1000 });
    expect(get(sessionId)).toBe(9);
  });

  it('clearChat resets stores and clears server history', async () => {
    mockStream((h) => h.onToken?.('x'));
    await sendMessage('q');
    clearChat();

    expect(get(messages)).toEqual([]);
    expect(get(sessionId)).toBeNull();
    expect(apiMock.ai.clearChatHistory).toHaveBeenCalled();
  });
});
