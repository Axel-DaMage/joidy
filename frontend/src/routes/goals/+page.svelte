<script lang="ts">
  import { onMount } from 'svelte';
  import { Plus, Check, ChevronDown } from 'lucide-svelte';
  import { api, type Goal, type Tag } from '$lib/api';
  import { applyGamificationResult, showXPGain } from '$lib/stores/gamification';

  let goals: Goal[] = [];
  let tags: Tag[] = [];
  let showCompleted = false;
  let showAddForm = false;

  // New goal form
  let newTitle = '';
  let newDescription = '';
  let newTargetNotes = 5;
  let newTagId: number | null = null;
  let saving = false;

  $: active = goals.filter(g => !g.is_completed);
  $: completed = goals.filter(g => g.is_completed);

  onMount(async () => {
    [goals, tags] = await Promise.all([api.goals.list(), api.tags.list()]);
  });

  let addError = '';

  async function addGoal() {
    if (!newTitle.trim()) return;
    saving = true;
    addError = '';
    try {
      const g = await api.goals.create({
        title: newTitle.trim(),
        description: newDescription,
        target_notes: newTargetNotes,
        tag_id: newTagId,
      });
      goals = [g, ...goals];
      newTitle = ''; newDescription = ''; newTargetNotes = 5; newTagId = null;
      showAddForm = false;
    } catch (e) {
      addError = 'Error al crear el objetivo. Intenta de nuevo.';
    } finally {
      saving = false;
    }
  }

  async function completeGoal(id: number) {
    const result = await api.goals.complete(id);
    goals = goals.map(g => g.id === id ? result.goal : g);
    applyGamificationResult(result.gamification);
    showXPGain(result.gamification.xp_awarded);
  }

  async function deleteGoal(id: number) {
    await api.goals.delete(id);
    goals = goals.filter(g => g.id !== id);
  }
</script>

<div class="goals-page">
  <div class="goals-header">
    <div>
      <h3>Objetivos</h3>
      <span class="caption">{active.length} activos · {completed.length} completados</span>
    </div>
    <button class="btn btn-primary" on:click={() => showAddForm = !showAddForm}>
      <Plus size={13} /> Nuevo objetivo
    </button>
  </div>

  <div class="goals-body">
    <!-- Add form -->
    {#if showAddForm}
      <div class="add-form card fade-in" style="margin-bottom: var(--s4);">
        <div class="form-row">
          <input class="input" bind:value={newTitle} placeholder="Título del objetivo..." style="flex:1;" />
        </div>
        <div class="form-row">
          <select class="input" bind:value={newTagId} style="flex:1;">
            <option value={null}>Sin tag específico</option>
            {#each tags as t}
              <option value={t.id}>{t.name}</option>
            {/each}
          </select>
          <div class="form-field" style="flex-shrink:0; display:flex; align-items:center; gap:6px;">
            <span class="label" style="white-space:nowrap;">meta notas:</span>
            <input class="input" type="number" bind:value={newTargetNotes} min="1" max="100" style="width:60px;" />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" on:click={addGoal} disabled={saving || !newTitle.trim()}>
            {saving ? 'Guardando...' : 'Crear'}
          </button>
          <button class="btn btn-ghost" on:click={() => showAddForm = false}>Cancelar</button>
          {#if addError}
            <span style="font-size:11px; color: var(--error); margin-left: auto;">{addError}</span>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Active goals -->
    {#if active.length === 0 && !showAddForm}
      <div class="empty-state caption">
        Sin objetivos activos. ¡Crea uno para comenzar!
      </div>
    {/if}

    {#each active as goal (goal.id)}
      <div class="goal-card fade-in">
        <div class="goal-main">
          <div class="goal-title">{goal.title}</div>
          {#if goal.tag_id}
            <span class="tag-chip" style="margin-top:4px;">{tags.find(t => t.id === goal.tag_id)?.name ?? ''}</span>
          {/if}
        </div>

        <div class="goal-progress">
          <div class="progress-meta">
            <span class="mono caption" style="color: var(--xp);">{goal.progress}/{goal.target_notes}</span>
            <span class="caption" style="color: var(--text-muted);">{goal.progress_pct}%</span>
          </div>
          <div class="progress-track" style="height: 2px;">
            <div class="progress-fill" class:success={goal.progress_pct >= 100} style="width:{goal.progress_pct}%"></div>
          </div>
        </div>

        <div class="goal-actions">
          <button class="btn btn-ghost" style="padding: 4px 10px; font-size:11px; color: var(--success);"
            on:click={() => completeGoal(goal.id)}>
            <Check size={12} /> Completar
          </button>
          <button class="btn btn-ghost" style="padding: 4px 6px; color: var(--text-muted);"
            on:click={() => deleteGoal(goal.id)}>
            ×
          </button>
        </div>
      </div>
    {/each}

    <!-- Completed toggle -->
    {#if completed.length > 0}
      <button class="completed-toggle btn btn-ghost w-full" on:click={() => showCompleted = !showCompleted}>
        <ChevronDown size={12} style="transform: rotate({showCompleted ? 180 : 0}deg); transition: transform 150ms;" />
        Completados ({completed.length})
      </button>

      {#if showCompleted}
        {#each completed as goal (goal.id)}
          <div class="goal-card completed fade-in">
            <div class="goal-main">
              <div class="goal-title">{goal.title}</div>
              {#if goal.completed_at}
                <span class="caption" style="color: var(--text-muted);">
                  {new Date(goal.completed_at).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })}
                </span>
              {/if}
            </div>
            <span class="level-badge" style="color: var(--success); border-color: var(--success);">✓ completado</span>
          </div>
        {/each}
      {/if}
    {/if}
  </div>
</div>

<style>
  .goals-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .goals-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s5);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .goals-header h3 {
    font-size: 14px;
    font-weight: 400;
    color: var(--text-secondary);
  }

  .goals-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--s5);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    max-width: 640px;
  }

  .add-form {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }

  .form-row {
    display: flex;
    gap: var(--s3);
    align-items: center;
  }

  .form-actions {
    display: flex;
    gap: var(--s2);
  }

  .goal-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    display: flex;
    align-items: center;
    gap: var(--s4);
  }

  .goal-card.completed {
    opacity: 0.5;
  }

  .goal-main {
    flex: 1;
    min-width: 0;
  }

  .goal-title {
    font-size: 13px;
    color: var(--text-primary);
    margin-bottom: 2px;
  }

  .goal-progress {
    width: 120px;
    flex-shrink: 0;
  }

  .progress-meta {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  .goal-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .empty-state {
    color: var(--text-muted);
    text-align: center;
    padding: var(--s6);
  }

  .completed-toggle {
    justify-content: flex-start;
    gap: var(--s2);
    color: var(--text-muted);
    font-size: 12px;
  }

  .level-badge {
    font-size: 9px;
    font-family: var(--font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 2px;
    border: 1px solid var(--border);
    white-space: nowrap;
  }
</style>
