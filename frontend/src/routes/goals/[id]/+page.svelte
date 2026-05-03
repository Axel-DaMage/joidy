<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api, type Goal } from '$lib/api';
  import GoalEditor from '$lib/components/GoalEditor.svelte';

  let goal: Goal | null = null;
  let goalContent: string = '';
  let loading = true;
  let loadError: string | null = null;

  $: goalId = parseInt($page.params.id);

  onMount(async () => {
    await loadGoal();
  });

  async function loadGoal() {
    loading = true;
    loadError = null;
    try {
      goal = await api.goals.get(goalId);
      const res = await api.goals.getContent(goalId);
      if (res) {
        goalContent = res.content || '';
        if (goal && res.title) goal.title = res.title;
      } else {
        goalContent = goal?.description || '';
      }
    } catch (e) {
      loadError = e instanceof Error ? e.message : 'Error al cargar objetivo';
    } finally {
      loading = false;
    }
  }

  async function handleSave(e: CustomEvent<{ title: string; content: string }>) {
    if (!goal) return;
    try {
      await api.goals.saveContent(goalId, {
        ...e.detail,
        temporality: goal.temporality || 'DAILY',
        measurement_type: goal.measurement_type || 'COUNT',
        target_value: goal.target_value || 1,
        state: goal.state || 'ACTIVE',
        fail_config: goal.fail_config || 'STATIC',
        fail_emoji: goal.fail_emoji || '🔴',
        color: goal.color || '#c8a96e',
        theme: goal.theme || 'solid',
        note_id: goal.note_id,
        tag_id: goal.tag_id,
        parent_id: goal.parent_id,
        max_assignment_days: goal.max_assignment_days,
        description: e.detail.content,
      });
    } catch (e) {
      console.error('Save error:', e);
    }
  }

  function handleCancel() {
    goto('/goals');
  }
</script>

<div class="goal-detail-page">
  {#if loading}
    <div class="loading">Cargando...</div>
  {:else if loadError}
    <div class="error">{loadError}</div>
  {:else if goal}
    <GoalEditor
      {goal}
      content={goalContent}
      on:save={handleSave}
      on:cancel={handleCancel}
    />
  {:else}
    <div class="error">Objetivo no encontrado</div>
  {/if}
</div>

<style>
  .goal-detail-page {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: var(--bg);
  }

  .loading, .error {
    padding: 24px;
    color: var(--text-muted);
    font-size: 14px;
  }

  .error {
    color: var(--error);
  }
</style>