<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api, type Goal, type Tag as TagType, type Note } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import GoalEditor from '$lib/components/GoalEditor.svelte';
  import IconPicker from '$lib/components/IconPicker.svelte';
  import StreakIcon from '$lib/components/StreakIcon.svelte';

  let goal: Goal | null = null;
  let goalContent: string = '';
  let loading = true;
  let loadError: string | null = null;

  let tags: TagType[] = [];
  let notes: Note[] = [];

  const EMOJIS = Array.from(new Set([
    '🔴','❌','⚠️','📉','⛔','🌧️','🔥','💪','🏃','🚴','🏊','🏋️','🤸','🧘',
    '❤️','💚','💙','💛','🧠','👁️','👂','👃','💊','💉','🩹','🩺',
    '📚','📖','📝','✍️','📓','📔','📕','📗','📘','🖊️','🖍️','📜','📋','🗂️',
    '🎨','🎭','🎬','🎤','🎧','🎵','🎶','🎸','🎹','🎺','🎷','📸','🖼️',
    '🌿','🍀','🌱','🌲','🌳','🌴','🌵','🌾','🌻','🌺','🌸','🌼','🌷','🌹','🌎',
    '🍎','🍊','🍋','🍌','🍇','🍓','🥗','🥙','🍕','🍔','🍟','🌮','☕','🍵',
    '💻','📱','⌚','🎮','🧩','🪀','🪁','🎯','🔐','🔒','🔓','🔑','⚙️','🔧','🔨','⚒️',
    '✈️','🚂','🚗','🚙','🚕','🚌','🚎','🏎️','🚓','🚑','🚒','🚐','🛻','🚚','🚛','🚜',
    '☀️','🌤️','⛅','🌥️','☁️','🌦️','🌧️','⛈️','🌩️','🌨️','❄️','☃️','⛄','🌊','💧','💦',
    '😀','😃','😄','😁','😆','😊','☺️','😉','😌','😚','😍','🤩','😘','🥰','😏','😐',
    '🥇','🥈','🥉','🏆','🎖️','🏅','⭐','🌟','✨','💫','🎊','🎉','🎁'
  ]));

  const TEMPORALITIES: Goal['temporality'][] = ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'];
  const COLOR_PRESETS = [
    { name: 'Gold',      hex: '#c8a96e' },
    { name: 'Esmeralda', hex: '#10b981' },
    { name: 'Cyan',      hex: '#06b6d4' },
    { name: 'Azul',      hex: '#3b82f6' },
    { name: 'Violeta',   hex: '#8b5cf6' },
    { name: 'Rosa',      hex: '#ec4899' },
    { name: 'Ámbar',     hex: '#f59e0b' },
    { name: 'Coral',     hex: '#ef4444' },
    { name: 'Lima',      hex: '#84cc16' },
    { name: 'Slate',     hex: '#64748b' },
    { name: 'Teal',      hex: '#14b8a6' },
    { name: 'Blanco',    hex: '#e2e8f0' },
  ];

  let showSettings = false;
  let settingsSection: 'basics' | 'appearance' | 'advanced' = 'basics';
  let editTitle = '';
  let editDescription = '';
  let editTemporality: Goal['temporality'] = 'DAILY';
  let editMeasurement: Goal['measurement_type'] = 'COUNT';
  let editTargetValue = 1;
  let editFailConfig: Goal['fail_config'] = 'STATIC';
  let editColor = '#c8a96e';
  let editMaxAssignmentDays: number | null = null;
  let editNoteId: number | null = null;
  let editTagId: number | null = null;
  let editUseFailIcon = false;
  let editFailEmoji = '🔴';
  let editFailIcon = 'Activity';
  let savingSettings = false;

  $: goalId = parseInt($page.params.id || "0");

  onMount(async () => {
    await Promise.all([loadGoal(), loadMeta()]);
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

  async function loadMeta() {
    try {
      [tags, notes] = await Promise.all([api.tags.list(), api.notes.list()]);
    } catch (e) {
      logger.error('Error al cargar notas/tags:', e);
    }
  }

  function openSettings() {
    if (!goal) return;
    editTitle = goal.title || '';
    editDescription = goal.description || '';
    editTemporality = goal.temporality || 'DAILY';
    editMeasurement = goal.measurement_type || 'COUNT';
    editTargetValue = goal.target_value || 1;
    editFailConfig = goal.fail_config || 'STATIC';
    editColor = goal.color || '#c8a96e';
    editMaxAssignmentDays = goal.max_assignment_days ?? null;
    editNoteId = goal.note_id ?? null;
    editTagId = goal.tag_id ?? null;

    const failVal = goal.fail_emoji || '🔴';
    if (EMOJIS.includes(failVal)) {
      editUseFailIcon = false;
      editFailEmoji = failVal;
      editFailIcon = 'Activity';
    } else {
      editUseFailIcon = true;
      editFailIcon = failVal;
      editFailEmoji = '🔴';
    }

    settingsSection = 'basics';
    showSettings = true;
  }

  async function saveSettings() {
    if (!goal || !editTitle.trim()) return;
    savingSettings = true;
    try {
      const result = await api.goals.update(goalId, {
        title: editTitle.trim(),
        description: editDescription,
        temporality: editTemporality,
        measurement_type: editMeasurement,
        target_value: editTargetValue,
        fail_config: editFailConfig,
        fail_emoji: editUseFailIcon ? editFailIcon : editFailEmoji,
        color: editColor,
        note_id: editNoteId,
        tag_id: editTagId,
        max_assignment_days: editMaxAssignmentDays,
      });
      goal = result;
      showSettings = false;
    } catch (e) {
      logger.error('Error al guardar ajustes:', e);
    } finally {
      savingSettings = false;
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
      logger.error('Save error:', e);
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
      on:edit={openSettings}
      on:cancel={handleCancel}
    />
  {:else}
    <div class="error">Objetivo no encontrado</div>
  {/if}
</div>

{#if showSettings}
  <div class="goal-settings-backdrop" on:click={() => showSettings = false} role="dialog" tabindex="-1">
    <div class="goal-settings-panel slide-down" on:click|stopPropagation>
      <div class="goal-settings-header">
        <div class="goal-settings-title-row">
          <div class="goal-settings-icon-wrap">
            <StreakIcon name={editUseFailIcon ? editFailIcon : editFailEmoji} size={16} color={editColor} />
          </div>
          <div>
            <h3 class="goal-settings-heading">Editar objetivo</h3>
            <span class="goal-settings-sub">Ajusta los detalles de este objetivo</span>
          </div>
        </div>
        <button class="history-close-btn" on:click={() => showSettings = false} title="Cerrar">×</button>
      </div>

      <div class="goal-settings-body">
        <div class="ng-tabs-container">
          <button class="ng-tab" class:active={settingsSection === 'basics'} on:click={() => settingsSection = 'basics'}>Basico</button>
          <button class="ng-tab" class:active={settingsSection === 'appearance'} on:click={() => settingsSection = 'appearance'}>Apariencia</button>
          <button class="ng-tab" class:active={settingsSection === 'advanced'} on:click={() => settingsSection = 'advanced'}>Avanzado</button>
        </div>

        <div class="ng-content-area">
          {#if settingsSection === 'basics'}
            <div class="ng-section-fade settings-basics">
              <div class="form-field">
                <label class="label">Titulo del objetivo</label>
                <input class="input w-full" bind:value={editTitle} maxlength="38" />
              </div>
              <div class="form-field">
                <label class="label">Descripcion</label>
                <textarea class="input w-full" bind:value={editDescription} rows="2"></textarea>
              </div>
              <div class="form-field basics-frequency">
                <label class="label">Frecuencia</label>
                <div class="ng-freq-grid">
                  {#each TEMPORALITIES as temp}
                    <button class="ng-freq-btn" class:active={editTemporality === temp} on:click={() => editTemporality = temp}>
                      {temp === 'DAILY' ? 'Diario' : temp === 'WEEKLY' ? 'Semanal' : temp === 'MONTHLY' ? 'Mensual' : 'Anual'}
                    </button>
                  {/each}
                </div>
              </div>
            </div>
          {/if}

          {#if settingsSection === 'appearance'}
            <div class="ng-section-fade settings-appearance">
              <div class="form-field appearance-icon">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <label class="label" style="margin:0;">Icono / Emoji de Fallo</label>
                  <div class="icon-toggle-row">
                    <button class="icon-type-btn" class:selected={!editUseFailIcon} on:click={() => editUseFailIcon = false}>Emoji</button>
                    <button class="icon-type-btn" class:selected={editUseFailIcon} on:click={() => editUseFailIcon = true}>Icono</button>
                  </div>
                </div>
                {#if !editUseFailIcon}
                  <div class="emoji-grid ng-large-grid">
                    {#each EMOJIS as e}
                      <button class="emoji-btn" class:selected={editFailEmoji === e} on:click={() => editFailEmoji = e}>{e}</button>
                    {/each}
                  </div>
                {:else}
                  <div class="field ng-large-grid" style="display: flex; flex-direction: column; height: 280px; padding: 8px; border: 1px solid var(--border); border-radius: var(--r); background: var(--surface-hover); overflow: hidden;">
                    <IconPicker selected={editFailIcon} color={editColor} onSelect={(ic) => editFailIcon = ic} />
                  </div>
                {/if}
              </div>

              <div class="form-field appearance-color">
                <label class="label">Color de Identidad</label>
                <div class="color-presets ng-expanded-presets">
                  {#each COLOR_PRESETS as c}
                    <button class="color-dot" class:selected={editColor === c.hex} style="background: {c.hex}; color: {c.hex};" on:click={() => editColor = c.hex}></button>
                  {/each}
                  <div class="color-custom" style="background: {editColor};">
                    <input type="color" bind:value={editColor} class="color-picker" />
                  </div>
                </div>
              </div>
            </div>
          {/if}

          {#if settingsSection === 'advanced'}
            <div class="ng-section-fade settings-advanced">
              <div class="form-row adv-measure">
                <div class="form-field" style="flex:1;">
                  <label class="label">Tipo de medicion</label>
                  <select class="input w-full" bind:value={editMeasurement}>
                    <option value="COUNT">Cuenta Numerica</option>
                    <option value="BOOLEAN">Hecho / No Hecho</option>
                    <option value="PERCENT">Porcentaje</option>
                  </select>
                </div>
                <div class="form-field" style="width: 140px;">
                  <label class="label">Meta</label>
                  <input class="input w-full" type="number" bind:value={editTargetValue} min="1" disabled={editMeasurement === 'BOOLEAN'} />
                </div>
                <div class="form-field" style="width: 140px;">
                  <label class="label">Limite dias</label>
                  <input class="input w-full" type="number" bind:value={editMaxAssignmentDays} min="1" placeholder="Ilimitado" />
                </div>
              </div>

              <div class="form-field adv-fail">
                <label class="label">Politica de fallo</label>
                <div class="ng-fail-options">
                  <button class="ng-fail-btn" class:active={editFailConfig === 'STATIC'} on:click={() => editFailConfig = 'STATIC'}>
                    <strong>Estatico</strong>
                    <span>Se reinicia a cero cada periodo</span>
                  </button>
                  <button class="ng-fail-btn" class:active={editFailConfig === 'ROLLOVER'} on:click={() => editFailConfig = 'ROLLOVER'}>
                    <strong>Traspaso</strong>
                    <span>La meta pendiente pasa al siguiente dia</span>
                  </button>
                  <button class="ng-fail-btn" class:active={editFailConfig === 'SNOWBALL'} on:click={() => editFailConfig = 'SNOWBALL'}>
                    <strong>Acumulativo</strong>
                    <span>La deuda se acumula exponencialmente</span>
                  </button>
                </div>
              </div>

              <div class="form-row adv-links">
                <div class="form-field" style="flex:1;">
                  <label class="label">Vincular a proyecto (nota)</label>
                  <select class="input w-full" bind:value={editNoteId}>
                    <option value={null}>Sin nota vinculada</option>
                    {#each notes as n}
                      <option value={n.id}>{n.title}</option>
                    {/each}
                  </select>
                </div>
                <div class="form-field" style="flex:1;">
                  <label class="label">Sincronizacion de tag</label>
                  <select class="input w-full" bind:value={editTagId}>
                    <option value={null}>Actualizacion manual</option>
                    {#each notes as n}
                      {@const tagId = tags.find(t => t.name === n.title)?.id}
                      {#if tagId}
                        <option value={tagId}>{n.title} (Auto-rastreo)</option>
                      {/if}
                    {/each}
                  </select>
                </div>
              </div>
            </div>
          {/if}
        </div>

        <div class="ng-bottom-preview">
          <span class="ng-preview-label">Vista previa</span>
          <div class="goal-card preview-card-live" style="border-color: {editColor}; background: color-mix(in srgb, {editColor} 5%, var(--surface));">
            <div class="goal-main">
              <div class="goal-title">
                <span class="emoji-badge" style="display:flex; align-items:center; margin-right:8px;">
                  {#if editUseFailIcon}
                    <StreakIcon name={editFailIcon} size={16} color={editColor} />
                  {:else}
                    {editFailEmoji}
                  {/if}
                </span>
                {editTitle || 'Nombre del objetivo...'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="goal-settings-footer">
        <span></span>
        <div class="new-goal-actions">
          <button class="btn btn-ghost" on:click={() => showSettings = false}>Cancelar</button>
          <button class="btn btn-primary" on:click={saveSettings} disabled={savingSettings || !editTitle.trim()}>
            {savingSettings ? 'Guardando...' : 'Guardar cambios'}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

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

  .goal-settings-backdrop {
    position: fixed;
    inset: 0;
    z-index: 200;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .goal-settings-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: 0 24px 80px rgba(0,0,0,0.6);
    display: flex;
    flex-direction: column;
    height: calc(100vh - 40px);
    max-height: calc(100vh - 40px);
    width: min(720px, 100%);
    border-radius: 16px;
    overflow: hidden;
  }

  .slide-down {
    animation: modalPopIn 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  }

  @keyframes modalPopIn {
    from { transform: scale(0.95) translateY(10px); opacity: 0; }
    to { transform: scale(1) translateY(0); opacity: 1; }
  }

  .goal-settings-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s6);
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }

  .history-close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 18px;
    line-height: 1;
  }

  .history-close-btn:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
  }

  .goal-settings-title-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }

  .goal-settings-icon-wrap {
    width: 32px;
    height: 32px;
    background: var(--surface-active);
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .goal-settings-heading {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-family: var(--font-mono);
  }

  .goal-settings-sub {
    display: none;
  }

  .goal-settings-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--s5) var(--s6);
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    min-height: 0;
  }

  .goal-settings-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s6);
    border-top: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }

  .new-goal-actions {
    display: flex;
    gap: var(--s3);
  }

  .ng-tabs-container {
    display: flex;
    gap: 4px;
    background: var(--surface-hover);
    padding: 3px;
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .ng-tab {
    flex: 1;
    padding: 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--text-disabled);
    background: transparent;
    border: none;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s;
  }

  .ng-tab:hover { color: var(--text-secondary); }
  .ng-tab.active { background: var(--surface); color: var(--text-primary); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }

  .ng-content-area {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .ng-section-fade {
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    animation: ngFadeIn 0.3s ease;
    flex: 1;
    min-height: 0;
  }

  .settings-basics {
    justify-content: space-between;
  }

  .settings-basics .basics-frequency {
    margin-top: auto;
  }

  .settings-appearance {
    justify-content: space-between;
  }

  .settings-appearance .appearance-icon {
    flex: 1;
  }

  .settings-appearance .appearance-color {
    margin-top: auto;
  }

  .settings-advanced {
    justify-content: space-between;
  }

  .settings-advanced .adv-fail {
    flex: 1;
  }

  .settings-advanced .adv-links {
    margin-top: auto;
  }

  @keyframes ngFadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .ng-freq-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }

  .ng-freq-btn {
    padding: 10px;
    font-size: 12px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
  }

  .ng-freq-btn:hover { border-color: var(--text-muted); }
  .ng-freq-btn.active { background: var(--surface-active); color: var(--text-primary); border-color: var(--text-primary); }

  .ng-large-grid {
    max-height: 280px !important;
  }

  .ng-fail-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ng-fail-btn {
    display: flex;
    flex-direction: column;
    padding: 12px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: 8px;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
  }

  .ng-fail-btn strong { font-size: 13px; color: var(--text-secondary); }
  .ng-fail-btn span { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
  .ng-fail-btn:hover { border-color: var(--text-muted); }
  .ng-fail-btn.active { background: rgba(var(--primary-rgb, 139, 92, 246), 0.1); border-color: var(--primary); }

  .ng-expanded-presets {
    justify-content: center;
    gap: 12px;
    padding: 12px;
    background: var(--surface-hover);
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .icon-toggle-row { display: flex; gap: 6px; }
  .icon-type-btn {
    flex: 1; padding: 4px 12px; font-size: 11px; font-family: var(--font-mono);
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted); cursor: pointer;
    transition: all 0.15s;
  }
  .icon-type-btn.selected { border-color: var(--text-primary); color: var(--text-primary); }

  .emoji-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
    background: var(--surface-hover);
    padding: 8px;
    border-radius: var(--r);
    border: 1px solid var(--border);
    max-height: 200px;
    overflow-y: auto;
  }

  .emoji-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .emoji-btn:hover { background: var(--elevated); }
  .emoji-btn.selected { border-color: var(--text-primary); background: var(--elevated); }

  .color-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 6px 0;
    align-items: center;
  }

  .color-dot {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .color-dot:hover { transform: scale(1.15); }
  .color-dot.selected { border-color: var(--text-primary); box-shadow: 0 0 0 2px var(--bg), 0 0 0 4px currentColor; }

  .color-custom {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--border);
    position: relative;
    cursor: pointer;
    transition: all 0.15s;
  }

  .color-custom:hover { transform: scale(1.1); border-color: var(--text-muted); }

  .color-picker {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    cursor: pointer;
    border: none;
    padding: 0;
  }

  .form-row {
    display: flex;
    gap: var(--s3);
    align-items: flex-start;
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0px;
  }

  .label {
    display: block;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
  }

  .ng-bottom-preview {
    margin-top: var(--s2);
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: auto;
  }

  .ng-preview-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-disabled);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: center;
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

  .goal-main { flex: 1; min-width: 0; }

  .goal-title {
    font-size: 14px;
    color: var(--text-primary);
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .emoji-badge { font-size: 16px; }

  .preview-card-live {
    border-width: 1px;
  }
</style>