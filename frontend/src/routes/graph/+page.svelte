<script lang="ts">
  import { onMount } from 'svelte';
  import KnowledgeGraphForce from '$lib/components/KnowledgeGraphForce.svelte';
  import { graphData, graphLoading, loadGraph, selectedTag } from '$lib/stores/graph';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import type { GraphNode, GraphEdge } from '$lib/api';

  let containerEl: HTMLDivElement;
  let w = 800, h = 600;

  $: noteCount = $graphData.nodes.filter((n: GraphNode) => n.type === 'note').length;
  $: tagCount = $graphData.nodes.filter((n: GraphNode) => n.type === 'tag').length;
  $: linkCount = $graphData.edges.filter((e: GraphEdge) => e.type === 'linked').length;
  $: taggedCount = $graphData.edges.filter((e: GraphEdge) => e.type === 'tagged').length;

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
      <span class="stats">
        <span class="stat"><span class="dot note"></span>{noteCount} notas</span>
        <span class="stat"><span class="dot tag"></span>{tagCount} tags</span>
        <span class="stat">{linkCount} links</span>
        <span class="stat">{taggedCount} etiquetas</span>
      </span>
    </div>
    {#if $selectedTag !== null}
      <button class="btn btn-ghost" on:click={() => selectedTag.set(null)}>
        Limpiar seleccion
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
      <KnowledgeGraphForce width={w} height={h} focusId={$selectedTag} />
    {/if}
  </div>

  <div class="graph-legend caption">
    <span class="legend-item"><span class="line solid"></span>jerarquía</span>
    <span class="legend-item"><span class="line dashed"></span>co-ocurrencia</span>
    <span class="legend-item"><span class="line linked"></span>enlazado</span>
    <span class="legend-item"><span class="dot note"></span>nota</span>
    <span class="legend-item"><span class="dot tag"></span>tag</span>
    <span class="legend-hint">doble-click para abrir · drag parafixar</span>
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
    margin-bottom: 4px;
  }

  .stats {
    display: flex;
    gap: var(--s4);
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }

  .stat {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .dot.note { background: #4a90a4; }
  .dot.tag { background: #7d6b91; }

  .graph-container {
    flex: 1;
    overflow: hidden;
    position: relative;
    min-height: 0;
    background: var(--bg);
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
    font-size: 10px;
    flex-wrap: wrap;
    align-items: center;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .line {
    width: 16px;
    height: 1px;
    display: inline-block;
  }

  .line.solid { background: var(--border); }
  .line.dashed {
    background: transparent;
    border-top: 1px dashed var(--text-muted);
  }
  .line.linked { background: var(--accent); }

  .legend-hint {
    margin-left: auto;
    color: var(--text-muted);
    opacity: 0.7;
  }
</style>
