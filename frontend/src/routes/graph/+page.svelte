<script lang="ts">
  import { onMount } from 'svelte';
  import KnowledgeGraphForce from '$lib/components/KnowledgeGraphForce.svelte';
  import TopicClusters from '$lib/components/TopicClusters.svelte';
  import { graphData, graphLoading, loadGraph, selectedTag } from '$lib/stores/graph';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { devMode } from '$lib/stores/settings';
  import type { GraphNode, GraphEdge } from '$lib/api';

  // Lazy-load the heavy graph component (d3 + force-graph, 1300+ lines) so it
  // is split into a separate chunk and only downloaded when the user actually
  // opens the graph page in dev mode (#347).
  let KnowledgeGraphForce: typeof import('$lib/components/KnowledgeGraphForce.svelte').default | null = null;
  $: if ($devMode && !KnowledgeGraphForce) {
    import('$lib/components/KnowledgeGraphForce.svelte').then(m => KnowledgeGraphForce = m.default);
  }

  let containerEl: HTMLDivElement;
  let w = 800, h = 600;

  // Timeline filter (#373) — filter notes by date range
  let dateFilterEnabled = $state(false);
  let dateRange = $state(365); // days back from today
  let graphSearch = $state('');

  let noteCount = $derived($graphData.nodes.filter((n: GraphNode) => n.type === 'note').length);
  let tagCount = $derived($graphData.nodes.filter((n: GraphNode) => n.type === 'tag').length);
  let linkCount = $derived($graphData.edges.filter((e: GraphEdge) => e.type === 'linked').length);
  let taggedCount = $derived($graphData.edges.filter((e: GraphEdge) => e.type === 'tagged').length);

  // Filtered graph data based on timeline and search (#373)
  let filteredGraphData = $derived.by(() => {
    if (!dateFilterEnabled && !graphSearch) return $graphData;

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - dateRange);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    const searchLower = graphSearch.toLowerCase();

    let nodes = $graphData.nodes.filter((n: GraphNode) => {
      if (n.type === 'tag') return true; // always keep tags
      if (dateFilterEnabled && n.path && n.path < cutoffStr) return false;
      if (graphSearch) {
        const name = (n.title || n.name || '').toLowerCase();
        if (!name.includes(searchLower)) return false;
      }
      return true;
    });

    const visibleIds = new Set(nodes.map(n => n.id));
    const edges = $graphData.edges.filter(
      (e: GraphEdge) => visibleIds.has(e.source) && visibleIds.has(e.target)
    );

    // Remove tags with no connections after filtering
    const connectedTagIds = new Set(edges.filter(e => e.type === 'tagged').map(e => e.target));
    nodes = nodes.filter(n => n.type !== 'tag' || connectedTagIds.has(n.id));

    return { nodes, edges };
  });

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

<svelte:head>
  <title>Grafo de Conocimiento — Joidy</title>
</svelte:head>

{#if $devMode}
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
      <button class="btn btn-ghost" onclick={() => selectedTag.set(null)}>
        Limpiar seleccion
      </button>
    {/if}
  </div>

  <!-- Timeline filter + search (#373) -->
  <div class="graph-controls">
    <div class="control-group">
      <label class="control-toggle">
        <input type="checkbox" bind:checked={dateFilterEnabled} />
        <span class="caption">Timeline</span>
      </label>
      {#if dateFilterEnabled}
        <input
          type="range"
          min="7"
          max="365"
          step="7"
          bind:value={dateRange}
          class="timeline-slider"
        />
        <span class="caption mono">{dateRange}d</span>
      {/if}
    </div>
    <input
      type="text"
      class="graph-search-input"
      placeholder="Buscar en grafo..."
      bind:value={graphSearch}
    />
  </div>

  <div class="graph-container" bind:this={containerEl}>
    {#if $graphLoading}
      <div class="loading-state caption">Cargando grafo...</div>
    {:else if filteredGraphData.nodes.length === 0}
      <div class="loading-state caption">
        {#if $graphData.nodes.length === 0}
          Sin datos aún. Crea notas y agrega tags para ver el grafo.
        {:else}
          Sin resultados para el filtro actual.
        {/if}
      </div>
    {:else if KnowledgeGraphForce}
      <svelte:component this={KnowledgeGraphForce} width={w} height={h} focusId={$selectedTag} />
    {:else}
      <KnowledgeGraphForce width={w} height={h} focusId={$selectedTag} data={filteredGraphData} />
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

  <TopicClusters />
</div>
{:else}
<div class="construction-page">
  <div class="construction-box">
    <DynamicIcon name="Network" size={48} />
    <h3>En Construcción</h3>
    <p>Activa el Modo Desarrollo en Ajustes para acceder al Grafo de Conocimiento.</p>
  </div>
</div>
{/if}

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
    z-index: var(--z-base); /* Ensure graph content (incl. settings panel) is above the nav sidebar (#274) */
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

  .graph-controls {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .control-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .control-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
  }

  .control-toggle input {
    cursor: pointer;
  }

  .timeline-slider {
    width: 120px;
    accent-color: var(--xp);
  }

  .graph-search-input {
    flex: 1;
    max-width: 200px;
    padding: 4px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--elevated);
    color: var(--text-primary);
    font-size: 12px;
    outline: none;
  }

  .graph-search-input:focus {
    border-color: var(--accent);
  }

  .graph-search-input::placeholder {
    color: var(--text-muted);
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

  .construction-page {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    width: 100%;
  }

  .construction-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 40px;
  }

  .construction-box h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-secondary);
    margin: 0;
  }

  .construction-box p {
    font-size: 13px;
    margin: 0;
    max-width: 320px;
  }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    .graph-header {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--s2);
      padding: var(--s3) var(--s3);
    }

    .graph-header h3 {
      font-size: 13px;
    }

    .stats {
      flex-wrap: wrap;
      gap: var(--s2);
      font-size: 10px;
    }

    .graph-legend {
      gap: var(--s3);
      padding: var(--s2) var(--s3);
      font-size: 9px;
    }

    .legend-hint {
      width: 100%;
      margin-left: 0;
      margin-top: var(--s1);
    }

    .construction-box {
      padding: var(--s4);
    }

    .construction-box p {
      max-width: 100%;
    }
  }

  @media (max-width: 480px) {
    .graph-header {
      padding: var(--s2) var(--s2);
    }

    .stats {
      gap: var(--s1);
    }

    .graph-legend {
      gap: var(--s2);
      padding: var(--s1) var(--s2);
    }
  }
</style>
