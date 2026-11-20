import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Note } from '$lib/api';
import type { OutboxChange } from '$lib/utils/indexedDB';

// #1304 — offline `create` uses a temp negative id. After the server `create`
// succeeds the temp IDB copy must be removed and queued update/delete entries
// retargeted to the real id, otherwise the note duplicates and its edits are
// dropped after MAX_RETRIES as silent 404s.

const { apiMock, idb } = vi.hoisted(() => ({
  apiMock: {
    notes: {
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
  },
  idb: {
    openDB: vi.fn(async () => ({})),
    getAllNotes: vi.fn(async () => []),
    putNote: vi.fn(async () => {}),
    deleteNote: vi.fn(async () => {}),
    addToOutbox: vi.fn(async () => 1),
    getOutbox: vi.fn(async () => [] as OutboxChange[]),
    removeFromOutbox: vi.fn(async () => {}),
    updateOutboxChange: vi.fn(async () => {}),
    setMeta: vi.fn(async () => {}),
    getMeta: vi.fn(async () => null),
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));
vi.mock('$lib/utils/indexedDB', () => idb);
vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import { processOutbox, onTempIdRemap } from './offlineSync';

const tempNote: Note = {
  id: -123,
  title: 'Offline note',
  content: 'draft',
  source: 'manual',
  source_path: null,
  tags: [],
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

const realNote: Note = { ...tempNote, id: 42 };

const outboxEntries: OutboxChange[] = [
  { id: 1, type: 'create', note: tempNote, timestamp: 1, retries: 0 },
  {
    id: 2,
    type: 'update',
    note: { ...tempNote, content: 'edited offline' },
    timestamp: 2,
    retries: 0,
  },
];

describe('processOutbox — temp id remap (#1304)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.notes.create.mockResolvedValue(realNote);
    apiMock.notes.update.mockResolvedValue({ ...realNote, content: 'edited offline' });
  });

  it('removes the temp IDB copy and retargets queued edits to the real id', async () => {
    idb.getOutbox.mockResolvedValue(outboxEntries);

    const remapped: [number, Note][] = [];
    onTempIdRemap((tempId, real) => {
      remapped.push([tempId, real]);
    });

    await processOutbox();

    // create → real note cached, temp copy deleted
    expect(apiMock.notes.create).toHaveBeenCalledTimes(1);
    expect(idb.putNote).toHaveBeenCalledWith(realNote);
    expect(idb.deleteNote).toHaveBeenCalledWith(-123);

    // the queued update was rewritten to the real id and persisted
    expect(idb.updateOutboxChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: 2, note: expect.objectContaining({ id: 42 }) })
    );
    expect(apiMock.notes.update).toHaveBeenCalledWith(42, expect.any(Object));
    expect(apiMock.notes.update).not.toHaveBeenCalledWith(-123, expect.anything());

    // both outbox entries consumed; in-memory remap notified
    expect(idb.removeFromOutbox).toHaveBeenCalledWith(1);
    expect(idb.removeFromOutbox).toHaveBeenCalledWith(2);
    expect(remapped).toEqual([[-123, realNote]]);
  });
});
