<script lang="ts">
  import { onMount } from 'svelte';
  import SkillTree from '$lib/components/SkillTree.svelte';
  import { api, type Skill, type SkillTree as SkillTreeData } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';

  let skills: Skill[] = [];
  let treeData: SkillTreeData = { nodes: [], edges: [] };
  let loading = true;

  const LEVEL_LABELS: Record<string, string> = {
    locked: 'Bloqueado', apprentice: 'Aprendiz', journeyman: 'Oficial', expert: 'Experto', master: 'Maestro'
  };

  $: topSkill = skills.sort((a, b) => b.note_count - a.note_count)[0];
  $: totalUnlocked = skills.filter(s => s.level !== 'locked').length;
  $: recentlyUnlocked = skills.filter(s => s.first_unlocked_at).sort((a, b) =>
    new Date(b.first_unlocked_at!).getTime() - new Date(a.first_unlocked_at!).getTime()
  ).slice(0, 3);

  onMount(async () => {
    try {
      [skills, treeData] = await Promise.all([api.skills.list(), api.skills.tree()]);
    } catch (e) {
      logger.error(e);
    } finally {
      loading = false;
    }
  });
</script>


<div class="skills-page">
  <div class="skills-header">
    <div>
      <h3>Árbol de habilidades</h3>
      <span class="caption">{totalUnlocked} habilidades desbloqueadas</span>
    </div>
    <div class="skill-stats">
      {#if topSkill}
        <div class="skill-stat">
          <span class="label">mejor habilidad</span>
          <span class="mono" style="color: var(--text-primary); font-size:13px;">{topSkill.tag_name}</span>
          <span class="caption" style="color: var(--text-secondary);">{topSkill.note_count} notas</span>
        </div>
      {/if}
    </div>
  </div>

  <div class="skills-body">
    <!-- Tree visualization -->
    <div class="tree-panel">
      {#if loading}
        <div class="loading-state caption">Cargando árbol...</div>
      {:else if treeData.nodes.length === 0}
        <div class="loading-state caption">
          Agrega 3+ notas con un tag para desbloquear una habilidad.
        </div>
      {:else}
        <SkillTree data={treeData} width={560} height={420} />
      {/if}
    </div>

    <!-- Skills list sidebar -->
    <aside class="skills-list">
      <div class="skills-list-header label">Habilidades</div>

      {#each skills as skill}
        <div class="skill-row">
          <div class="skill-info">
            <span class="skill-name">{skill.tag_name}</span>
            <span class="skill-count caption">{skill.note_count} notas</span>
          </div>
          <span class="level-badge" data-level={skill.level}>
            {LEVEL_LABELS[skill.level] ?? skill.level}
          </span>
        </div>
      {:else}
        <div class="caption" style="padding: 24px 16px; color: var(--text-muted);">Sin habilidades aún.</div>
      {/each}
    </aside>
  </div>

  <!-- Legend -->
  <div class="legend">
    {#each ['apprentice', 'journeyman', 'expert', 'master'] as level}
      <div class="legend-item">
        <div class="legend-dot" data-level={level}></div>
        <span class="caption">{LEVEL_LABELS[level]}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .skills-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .skills-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s5);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .skills-header h3 {
    font-size: 14px;
    font-weight: 400;
    color: var(--text-secondary);
  }

  .skill-stats {
    display: flex;
    gap: var(--s5);
  }

  .skill-stat {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
  }

  .skills-body {
    display: grid;
    grid-template-columns: 1fr 240px;
    flex: 1;
    overflow: hidden;
  }

  .tree-panel {
    overflow: auto;
    padding: var(--s5);
    position: relative;
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }

  .loading-state {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-muted);
  }

  .skills-list {
    border-left: 1px solid var(--border);
    overflow-y: auto;
  }

  .skills-list-header {
    padding: var(--s3) var(--s4);
    border-bottom: 1px solid var(--border-light);
    position: sticky;
    top: 0;
    background: var(--bg);
  }

  .skill-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s2) var(--s4);
    border-bottom: 1px solid var(--border-light);
    gap: var(--s3);
  }

  .skill-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .skill-name {
    font-size: 13px;
    color: var(--text-primary);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .level-badge {
    font-size: 9px;
    font-family: var(--font-mono);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 2px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  [data-level='apprentice'] { color: var(--text-secondary); border: 1px solid var(--border); }
  [data-level='journeyman'] { color: var(--text-secondary); border: 1px solid var(--border); }
  [data-level='expert'] { color: var(--accent); border: 1px solid var(--text-secondary); }
  [data-level='master'] { color: var(--accent-contrast-text, var(--bg)); background: var(--accent); border: 1px solid var(--accent); }
  [data-level='locked'] { color: var(--text-muted); border: 1px dashed var(--border); opacity: 0.5; }

  .legend {
    display: flex;
    gap: var(--s5);
    padding: var(--s3) var(--s5);
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 1px solid var(--border);
  }
  .legend-dot[data-level='apprentice'] { border-color: var(--text-muted); }
  .legend-dot[data-level='journeyman'] { border-color: var(--text-secondary); }
  .legend-dot[data-level='expert']     { border-color: var(--accent); }
  .legend-dot[data-level='master']     { background: var(--accent); border-color: var(--accent); }
</style>
