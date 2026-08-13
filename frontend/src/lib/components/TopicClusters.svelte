<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { goto } from '$app/navigation';
  import DynamicIcon from './DynamicIcon.svelte';
  import { t } from 'svelte-i18n';

  let clusters = $state<{ cluster_id: number; note_ids: number[]; note_count: number; representative_title: string; titles: string[] }[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expanded = $state<Set<number>>(new Set());

  onMount(async () => {
    try {
      const resp = await api.ai.cluster();
      if (resp.error) {
        error = resp.error;
      } else {
        clusters = resp.clusters;
      }
    } catch (e: any) {
      error = e.message || 'Error al cargar temas';
    } finally {
      loading = false;
    }
  });

  function toggle(clusterId: number) {
    const next = new Set(expanded);
    if (next.has(clusterId)) next.delete(clusterId);
    else next.add(clusterId);
    expanded = next;
  }
</script>

<div class="topic-clusters">
  <div class="clusters-header">
    <h4><DynamicIcon name="Layers" size={16} /> Temas detectados</h4>
    {#if loading}<span class="caption">{$t('topicClusters.analyzing')}</span>{/if}
  </div>

  {#if error}
    <div class="clusters-error caption">{error}</div>
  {/if}

  {#if !loading && clusters.length === 0 && !error}
    <div class="caption">{$t('topicClusters.noTopics')}</div>
  {/if}

  {#each clusters as cluster (cluster.cluster_id)}
    <button class="cluster-card" onclick={() => toggle(cluster.cluster_id)}>
      <div class="cluster-header-row">
        <span class="cluster-title">{cluster.representative_title}</span>
        <span class="cluster-count mono">{cluster.note_count}</span>
      </div>
      {#if expanded.has(cluster.cluster_id)}
        <div class="cluster-titles">
          {#each cluster.titles as title}
            <div class="cluster-title-item">• {title}</div>
          {/each}
          {#if cluster.note_ids.length > 0}
            <button class="cluster-open-btn" onclick={(e) => { e.stopPropagation(); goto(`/notes?id=${cluster.note_ids[0]}`); }}>
              Abrir primera nota
            </button>
          {/if}
        </div>
      {/if}
    </button>
  {/each}
</div>

<style>
  .topic-clusters {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
  }

  .clusters-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .clusters-header h4 {
    font-size: 13px;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .clusters-error {
    color: var(--error);
    font-size: 11px;
  }

  .cluster-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid var(--border-light);
    border-radius: var(--r);
    background: var(--elevated);
    cursor: pointer;
    text-align: left;
    transition: all var(--t-fast);
  }

  .cluster-card:hover {
    border-color: var(--accent);
  }

  .cluster-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .cluster-title {
    font-size: 13px;
    color: var(--text-primary);
  }

  .cluster-count {
    font-size: 12px;
    color: var(--xp);
  }

  .cluster-titles {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 4px;
  }

  .cluster-title-item {
    font-size: 11px;
    color: var(--text-muted);
    padding-left: 4px;
  }

  .cluster-open-btn {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--accent);
    cursor: pointer;
    font-size: 11px;
    padding: 4px 8px;
    margin-top: 4px;
    align-self: flex-start;
  }

  .cluster-open-btn:hover {
    background: var(--hover);
  }
</style>
