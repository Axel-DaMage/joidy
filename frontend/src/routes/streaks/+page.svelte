<script lang="ts">
  import { onMount } from 'svelte';
  import { Plus, Pencil, Trash2, Check, X, Flame } from 'lucide-svelte';
  import { api, type PersonalStreak } from '$lib/api';

  let streaks: PersonalStreak[] = [];
  let loading = true;
  let error = '';

  // ── Create form ────────────────────────────────────────────────────────────
  let showCreate = false;
  let newName = '';
  let newEmoji = '🔥';
  let newDesc = '';
  let saving = false;

  // ── Edit form ──────────────────────────────────────────────────────────────
  let editingId: number | null = null;
  let editName = '';
  let editEmoji = '';
  let editDesc = '';

  // ── Emoji picker ───────────────────────────────────────────────────────────
  const EMOJIS = ['🔥','💪','🏃','📚','🎸','🎹','🧘','🥗','💧','🛌','✍️','🎯','🗣️',
                  '🚴','🏊','🧠','💻','🎨','🎬','☕','🍎','🌿','⚡','🔒','🌅'];

  onMount(async () => {
    try {
      streaks = await api.personalStreaks.list();
    } catch (e) {
      error = 'No se pudo cargar las rachas.';
      console.error('[streaks]', e);
    } finally {
      loading = false;
    }
  });

  // ── Actions ────────────────────────────────────────────────────────────────
  async function createStreak() {
    if (!newName.trim()) return;
    saving = true;
    try {
      const s = await api.personalStreaks.create({ name: newName.trim(), emoji: newEmoji, description: newDesc });
      streaks = [...streaks, s];
      newName = ''; newEmoji = '🔥'; newDesc = '';
      showCreate = false;
    } finally {
      saving = false;
    }
  }

  async function checkin(id: number) {
    const updated = await api.personalStreaks.checkin(id);
    streaks = streaks.map(s => s.id === id ? updated : s);
  }

  async function undo(id: number) {
    const updated = await api.personalStreaks.undo(id);
    streaks = streaks.map(s => s.id === id ? updated : s);
  }

  async function deleteStreak(id: number) {
    await api.personalStreaks.delete(id);
    streaks = streaks.filter(s => s.id !== id);
  }

  function startEdit(s: PersonalStreak) {
    editingId = s.id;
    editName = s.name;
    editEmoji = s.emoji;
    editDesc = s.description;
  }

  async function saveEdit() {
    if (!editName.trim() || editingId === null) return;
    const updated = await api.personalStreaks.update(editingId, {
      name: editName.trim(),
      emoji: editEmoji,
      description: editDesc,
    });
    streaks = streaks.map(s => s.id === editingId ? updated : s);
    editingId = null;
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  // Show last 14 days as dots in mini-calendar
  function last14(streak: PersonalStreak) {
    return streak.history.slice(-14);
  }

  function streakLabel(n: number): string {
    if (n === 0) return 'sin racha';
    if (n === 1) return '1 día';
    return `${n} días`;
  }

  $: pending = streaks.filter(s => !s.today_checked);
  $: done = streaks.filter(s => s.today_checked);
</script>

<div class="streaks-page">
  <!-- Header -->
  <div class="page-header">
    <div class="header-left">
      <h1 class="page-title">Rachas</h1>
      <span class="page-sub mono">
        {#if loading}cargando...{:else}
          {done.length}/{streaks.length} completadas hoy
        {/if}
      </span>
    </div>
    <button class="new-btn" on:click={() => { showCreate = !showCreate; }}>
      <Plus size={13} />
      <span>Nueva racha</span>
    </button>
  </div>

  <!-- Create form -->
  {#if showCreate}
    <div class="create-form">
      <div class="form-row">
        <div class="emoji-display">{newEmoji}</div>
        <input
          class="input name-input"
          bind:value={newName}
          placeholder="Nombre de la racha..."
          on:keydown={(e) => e.key === 'Enter' && createStreak()}
          autofocus
        />
      </div>
      <div class="emoji-grid">
        {#each EMOJIS as e}
          <button
            class="emoji-btn"
            class:selected={newEmoji === e}
            on:click={() => newEmoji = e}
          >{e}</button>
        {/each}
      </div>
      <input
        class="input desc-input"
        bind:value={newDesc}
        placeholder="Descripción opcional..."
      />
      <div class="form-actions">
        <button class="btn-cancel" on:click={() => showCreate = false}>Cancelar</button>
        <button class="btn-save" on:click={createStreak} disabled={saving || !newName.trim()}>
          {saving ? '...' : 'Crear'}
        </button>
      </div>
    </div>
  {/if}

  {#if error}
    <div class="error-msg">{error}</div>
  {:else if loading}
    <div class="empty-state mono">Cargando...</div>
  {:else if streaks.length === 0}
    <div class="empty-state">
      <Flame size={28} style="opacity:.3; margin-bottom:12px;" />
      <p>No tienes rachas todavía.</p>
      <p class="mono" style="font-size:11px; margin-top:4px;">Crea una para empezar a llevar la cuenta.</p>
    </div>
  {:else}
    <!-- Pending today -->
    {#if pending.length > 0}
      <div class="section-label mono">pendientes hoy — {pending.length}</div>
      <div class="streaks-grid">
        {#each pending as streak (streak.id)}
          <div class="streak-card at-risk">
            {#if editingId === streak.id}
              <!-- Edit mode -->
              <div class="edit-form">
                <div class="form-row">
                  <div class="emoji-display small">{editEmoji}</div>
                  <input class="input" bind:value={editName} on:keydown={(e) => e.key === 'Enter' && saveEdit()} autofocus />
                </div>
                <div class="emoji-grid small">
                  {#each EMOJIS as e}
                    <button class="emoji-btn" class:selected={editEmoji === e} on:click={() => editEmoji = e}>{e}</button>
                  {/each}
                </div>
                <div class="edit-actions">
                  <button class="icon-action" on:click={() => editingId = null} title="Cancelar"><X size={12} /></button>
                  <button class="icon-action accent" on:click={saveEdit} title="Guardar"><Check size={12} /></button>
                </div>
              </div>
            {:else}
              <div class="card-top">
                <span class="card-emoji">{streak.emoji}</span>
                <div class="card-meta">
                  <span class="card-name">{streak.name}</span>
                  {#if streak.description}
                    <span class="card-desc mono">{streak.description}</span>
                  {/if}
                </div>
                <div class="card-actions">
                  <button class="icon-action" on:click={() => startEdit(streak)} title="Editar"><Pencil size={11} /></button>
                  <button class="icon-action danger" on:click={() => deleteStreak(streak.id)} title="Eliminar"><Trash2 size={11} /></button>
                </div>
              </div>

              <div class="streak-count-row">
                <span class="streak-number">{streak.current_streak}</span>
                <div class="streak-count-meta">
                  <span class="streak-unit">días</span>
                  {#if streak.longest_streak > streak.current_streak}
                    <span class="best-label mono">mejor: {streak.longest_streak}</span>
                  {/if}
                </div>
              </div>

              <div class="dots-row">
                {#each last14(streak) as day}
                  <span class="dot" class:filled={day.checked} title={day.date}></span>
                {/each}
              </div>

              <button class="checkin-btn" on:click={() => checkin(streak.id)}>
                <Check size={12} />
                Marcar hoy
              </button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Done today -->
    {#if done.length > 0}
      <div class="section-label mono" style="margin-top: {pending.length > 0 ? '24px' : '0'};">completadas hoy — {done.length}</div>
      <div class="streaks-grid">
        {#each done as streak (streak.id)}
          <div class="streak-card done">
            {#if editingId === streak.id}
              <div class="edit-form">
                <div class="form-row">
                  <div class="emoji-display small">{editEmoji}</div>
                  <input class="input" bind:value={editName} on:keydown={(e) => e.key === 'Enter' && saveEdit()} autofocus />
                </div>
                <div class="emoji-grid small">
                  {#each EMOJIS as e}
                    <button class="emoji-btn" class:selected={editEmoji === e} on:click={() => editEmoji = e}>{e}</button>
                  {/each}
                </div>
                <div class="edit-actions">
                  <button class="icon-action" on:click={() => editingId = null} title="Cancelar"><X size={12} /></button>
                  <button class="icon-action accent" on:click={saveEdit} title="Guardar"><Check size={12} /></button>
                </div>
              </div>
            {:else}
              <div class="card-top">
                <span class="card-emoji">{streak.emoji}</span>
                <div class="card-meta">
                  <span class="card-name">{streak.name}</span>
                  {#if streak.description}
                    <span class="card-desc mono">{streak.description}</span>
                  {/if}
                </div>
                <div class="card-actions">
                  <button class="icon-action" on:click={() => startEdit(streak)} title="Editar"><Pencil size={11} /></button>
                  <button class="icon-action danger" on:click={() => deleteStreak(streak.id)} title="Eliminar"><Trash2 size={11} /></button>
                </div>
              </div>

              <div class="streak-count-row">
                <span class="streak-number">{streak.current_streak}</span>
                <div class="streak-count-meta">
                  <span class="streak-unit">días</span>
                  {#if streak.longest_streak > streak.current_streak}
                    <span class="best-label mono">mejor: {streak.longest_streak}</span>
                  {/if}
                </div>
              </div>

              <div class="dots-row">
                {#each last14(streak) as day}
                  <span class="dot" class:filled={day.checked} title={day.date}></span>
                {/each}
              </div>

              <button class="undo-btn" on:click={() => undo(streak.id)}>
                <X size={11} />
                Deshacer
              </button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .streaks-page {
    padding: 28px 32px;
    max-width: 960px;
    height: 100%;
    overflow-y: auto;
  }

  /* ── Header ── */
  .page-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  .header-left { display: flex; align-items: baseline; gap: 14px; }

  .page-title {
    font-size: 20px;
    font-weight: 400;
    color: var(--text-primary);
    margin: 0;
  }

  .page-sub {
    font-size: 11px;
    color: var(--text-muted);
  }

  .new-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: var(--r);
    font-size: 12px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: opacity var(--t-fast);
  }
  .new-btn:hover { opacity: 0.8; }

  /* ── Create / Edit form ── */
  .create-form {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 16px;
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .form-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .emoji-display {
    font-size: 24px;
    width: 36px;
    text-align: center;
    flex-shrink: 0;
  }
  .emoji-display.small { font-size: 18px; width: 28px; }

  .input {
    flex: 1;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 10px;
    font-size: 13px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    outline: none;
  }
  .input:focus { border-color: var(--text-muted); }
  .input::placeholder { color: var(--text-muted); }

  .name-input { font-size: 14px; }
  .desc-input { font-size: 12px; font-family: var(--font-mono); }

  .emoji-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .emoji-grid.small { gap: 3px; }

  .emoji-btn {
    font-size: 16px;
    width: 30px;
    height: 30px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all var(--t-fast);
  }
  .emoji-grid.small .emoji-btn { font-size: 14px; width: 26px; height: 26px; }
  .emoji-btn:hover { background: var(--elevated); border-color: var(--border); }
  .emoji-btn.selected { background: var(--elevated); border-color: var(--text-secondary); }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .btn-cancel {
    padding: 5px 14px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
  }

  .btn-save {
    padding: 5px 14px;
    background: var(--accent);
    border: none;
    border-radius: var(--r);
    color: var(--bg);
    font-size: 12px;
    cursor: pointer;
    transition: opacity var(--t-fast);
  }
  .btn-save:hover { opacity: 0.8; }
  .btn-save:disabled { opacity: 0.4; cursor: default; }

  /* ── Section label ── */
  .section-label {
    font-size: 10px;
    color: var(--text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 10px;
  }

  /* ── Grid ── */
  .streaks-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }

  /* ── Card ── */
  .streak-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: border-color var(--t-fast);
  }

  .streak-card.at-risk {
    border-color: var(--xp);
  }

  .streak-card.done {
    border-color: var(--border);
    opacity: 0.75;
  }

  .card-top {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  .card-emoji {
    font-size: 20px;
    line-height: 1;
    flex-shrink: 0;
    margin-top: 1px;
  }

  .card-meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .card-name {
    font-size: 13px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-desc {
    font-size: 10px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-actions {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity var(--t-fast);
  }
  .streak-card:hover .card-actions { opacity: 1; }

  .icon-action {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .icon-action:hover { background: var(--elevated); color: var(--text-secondary); border-color: var(--border); }
  .icon-action.danger:hover { color: var(--error); border-color: var(--error); }
  .icon-action.accent:hover { color: var(--success); border-color: var(--success); }

  /* ── Streak count ── */
  .streak-count-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .streak-number {
    font-size: 36px;
    font-family: var(--font-mono);
    font-weight: 400;
    color: var(--text-primary);
    line-height: 1;
  }

  .at-risk .streak-number { color: var(--xp); }

  .streak-count-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .streak-unit {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .best-label {
    font-size: 10px;
    color: var(--text-muted);
    opacity: 0.6;
  }

  /* ── Dots ── */
  .dots-row {
    display: flex;
    gap: 3px;
    flex-wrap: wrap;
  }

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--elevated);
    border: 1px solid var(--border);
    flex-shrink: 0;
    transition: background var(--t-fast);
  }

  .dot.filled {
    background: var(--text-secondary);
    border-color: var(--text-secondary);
  }

  .at-risk .dot.filled {
    background: var(--xp);
    border-color: var(--xp);
  }

  .done .dot.filled {
    background: var(--success);
    border-color: var(--success);
  }

  /* ── Buttons ── */
  .checkin-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    width: 100%;
    padding: 7px 0;
    background: color-mix(in srgb, var(--xp) 12%, transparent);
    border: 1px solid var(--xp);
    border-radius: var(--r);
    color: var(--xp);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
    margin-top: auto;
  }
  .checkin-btn:hover {
    background: var(--xp);
    color: var(--bg);
  }

  .undo-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    width: 100%;
    padding: 6px 0;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
    margin-top: auto;
  }
  .undo-btn:hover { border-color: var(--error); color: var(--error); }

  /* ── Edit form inside card ── */
  .edit-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 4px;
  }

  /* ── States ── */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 0;
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
  }

  .error-msg {
    padding: 12px 16px;
    border: 1px solid var(--error);
    border-radius: var(--r);
    color: var(--error);
    font-size: 12px;
  }
</style>
