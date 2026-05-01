<script lang="ts">
  import { onMount } from 'svelte';
  import KnowledgeGraph from '$lib/components/KnowledgeGraph.svelte';
  import { graphData, graphLoading, loadGraph, selectedTag } from '$lib/stores/graph';

  let containerEl: HTMLDivElement;
  let w = 800, h = 600;

  onMount(() => {
    void loadGraph();
    if (!containerEl) return;

    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        w = e.contentRect.width;
        h = e.contentRect.height;
      }
    });

    ro.observe(containerEl);
    return () => ro.disconnect();
  });
</script>

<div class="graph-page">
  <div class="graph-header">
    <div>
      <h3>Grafo de conocimiento</h3>
      <span class="caption">{$graphData.nodes.length} temas · {$graphData.edges.length} conexiones</span>
    </div>
    {#if $selectedTag !== null}
      <button class="btn btn-ghost" on:click={() => selectedTag.set(null)}>
        Limpiar selección
      </button>
    {/if}
  </div>

  <div class="graph-container" bind:this={containerEl}>
    {#if $graphLoading}
      <div class="loading-state caption">Cargando grafo...</div>
    {:else if $graphData.nodes.length === 0}
      <div class="loading-state caption">
        Sin datos aún. Crea notas y agrega tags para ver el grafo.
      </div>
    {:else}
      <KnowledgeGraph width={w} height={h} />
    {/if}
  </div>

  <div class="graph-legend caption">
    <span class="legend-item">─── jerarquía</span>
    <span class="legend-item">- - - co-ocurrencia</span>
    <span class="legend-item">● tamaño = notas</span>
  </div>
</div>

<style>
  .graph-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .graph-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s5);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .graph-header h3 {
    font-size: 14px;
    font-weight: 400;
    color: var(--text-secondary);
  }

  .graph-container {
    flex: 1;
    overflow: hidden;
    position: relative;
    min-height: 0;
  }

  .loading-state {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-muted);
  }

  .graph-legend {
    display: flex;
    gap: var(--s5);
    padding: var(--s3) var(--s5);
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    flex-shrink: 0;
    font-family: var(--font-mono);
  }
</style>
