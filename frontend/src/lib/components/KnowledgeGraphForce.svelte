<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { graphData, selectedTag } from '$lib/stores/graph';
  import type { GraphNode, GraphEdge } from '$lib/api';

  let ForceGraph: typeof import('force-graph') | null = null;

  export let width = 800;
  export let height = 600;
  export let focusId: number | null = null;

  let containerEl: HTMLDivElement;
  let graph: ReturnType<typeof import('force-graph')['default']> | null = null;
  let lastFocusId: number | null = null;
  let searchQuery = '';
  let showLabels = true;
  let showParticles = true;
  let filterType: 'all' | 'notes' | 'tags' = 'all';
  let showOrphans = true;
  let hoveredNode: GraphNode | null = null;
  let loaded = false;

  const COLORS = {
    tag: '#7d6b91',
    note: '#4a90a4',
    selected: '#e8a838',
    hierarchy: '#666',
    cooccurrence: '#999',
    linked: '#3b82f6',
    tagged: '#8b5cf6',
    default: '#888'
  } as const;

  const getNodeType = (n: GraphNode) => (n.type === 'note' || n.type === 'tag') ? n.type : 'tag';
  const getNodeLabel = (n: GraphNode) => getNodeType(n) === 'note' ? (n.title || '') : (n.name || '');
  const getLinkColor = (t: GraphEdge['type']) => COLORS[t as keyof typeof COLORS] || COLORS.default;

  function rebuildGraph() {
    if (!graph) return;
    const nodes = $graphData.nodes.slice();
    const edges = $graphData.edges.slice();

    let filteredNodes = nodes;
    if (filterType === 'notes') filteredNodes = nodes.filter(n => getNodeType(n) === 'note');
    if (filterType === 'tags') filteredNodes = nodes.filter(n => getNodeType(n) === 'tag');

    let nodeIds = new Set(filteredNodes.map(n => n.id));
    const getEdgeSourceId = (e: any) => typeof e.source === 'object' ? e.source.id : e.source;
    const getEdgeTargetId = (e: any) => typeof e.target === 'object' ? e.target.id : e.target;
    let filteredEdges = edges.filter(e => nodeIds.has(getEdgeSourceId(e)) && nodeIds.has(getEdgeTargetId(e)));

    if (!showOrphans) {
      const degree = new Map<number, number>();
      filteredEdges.forEach((e) => {
        const s = getEdgeSourceId(e);
        const t = getEdgeTargetId(e);
        degree.set(s, (degree.get(s) ?? 0) + 1);
        degree.set(t, (degree.get(t) ?? 0) + 1);
      });
      filteredNodes = filteredNodes.filter(n => (degree.get(n.id) ?? 0) > 0);
      nodeIds = new Set(filteredNodes.map(n => n.id));
      filteredEdges = filteredEdges.filter(e => nodeIds.has(getEdgeSourceId(e)) && nodeIds.has(getEdgeTargetId(e)));
    }

    graph.graphData({ nodes: filteredNodes, links: filteredEdges });
    graph.d3ReheatSimulation();
    graph.zoomToFit(0, 60);
  }

  function applyStyling() {
    if (!graph) return;
    const focus = hoveredNode?.id ?? $selectedTag;
    const q = searchQuery.trim().toLowerCase();
    graph
      .nodeRelSize(3.2)
      .nodeColor((n: GraphNode) => getNodeType(n) === 'tag' ? COLORS.tag : COLORS.note)
      .nodeCanvasObject((node: GraphNode, ctx: CanvasRenderingContext2D, scale: number) => {
        const label = getNodeLabel(node);
        const r = getNodeType(node) === 'note' ? 3.4 : 4.6;
        const isSelected = $selectedTag === node.id;
        const isHovered = hoveredNode?.id === node.id;
        const isFocused = focusId !== null && (node.id === focusId);
        const matches = q ? label.toLowerCase().includes(q) : true;
        const focusDim = focus !== null ? (node.id === focus ? 1 : 0.15) : 1;
        const searchDim = q ? (matches ? 1 : 0.18) : 1;
        const alpha = Math.min(focusDim, searchDim);

        ctx.beginPath();
        const gradient = ctx.createRadialGradient(node.x - r * 0.4, node.y - r * 0.4, 0, node.x, node.y, r);
        gradient.addColorStop(0, getNodeType(node) === 'tag' ? '#9d8bb0' : '#5ba3b8');
        gradient.addColorStop(1, getNodeType(node) === 'tag' ? COLORS.tag : COLORS.note);
        ctx.fillStyle = gradient;
        ctx.globalAlpha = alpha;
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
        ctx.fill();

        if (isHovered) {
          ctx.beginPath();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5 / scale;
          ctx.globalAlpha = 0.9;
          ctx.arc(node.x, node.y, r + 2, 0, Math.PI * 2);
          ctx.stroke();
        }

        if (isSelected || isFocused) {
          ctx.beginPath();
          ctx.strokeStyle = COLORS.selected;
          ctx.lineWidth = 2 / scale;
          ctx.globalAlpha = 0.95;
          ctx.arc(node.x, node.y, r + 3, 0, Math.PI * 2);
          ctx.stroke();
        }

        if (showLabels && label) {
          const fontSize = 10 / scale;
          ctx.font = `${fontSize}px var(--font-sans)`;
          ctx.fillStyle = 'rgba(214, 214, 214, 0.85)';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.globalAlpha = alpha;
          ctx.fillText(label.slice(0, 24), node.x, node.y + r + 6 / scale);
        }
      })
      .linkLineDash((l: GraphEdge) => l.type === 'cooccurrence' ? [4, 4] : [])
      .linkDirectionalParticleWidth(() => 2.2)
      .linkDirectionalParticleSpeed(() => 0.008)
      .linkColor((l: GraphEdge) => {
        if (focus === null) return getLinkColor(l.type);
        const sourceId = (l.source as GraphNode).id;
        const targetId = (l.target as GraphNode).id;
        return (sourceId === focus || targetId === focus) ? getLinkColor(l.type) : '#333333';
      })
      .linkWidth((l: GraphEdge) => {
        if (focus === null) return l.type === 'hierarchy' ? 1.4 : 0.8;
        const sourceId = (l.source as GraphNode).id;
        const targetId = (l.target as GraphNode).id;
        return (sourceId === focus || targetId === focus) ? 1.6 : 0.2;
      })
      .linkDirectionalParticles((l: GraphEdge) => {
        if (!showParticles) return 0;
        if (focus === null) return (l.type === 'linked' || l.type === 'tagged') ? 3 : 0;
        const sourceId = (l.source as GraphNode).id;
        const targetId = (l.target as GraphNode).id;
        return (sourceId === focus || targetId === focus) ? 2 : 0;
      });
  }

  function focusOnNode(id: number) {
    if (!graph) return;
    const node = graph.graphData().nodes.find((n: GraphNode) => n.id === id) as GraphNode | undefined;
    if (!node) return;
    graph.centerAt(node.x, node.y, 400);
    graph.zoom(1.2, 400);
  }

  function resetView() {
    if (!graph) return;
    graph.centerAt(0, 0, 300);
    graph.zoom(1, 300);
  }

  function zoomToFit() {
    if (!graph) return;
    graph.zoomToFit(500, 50);
  }

  function clearHighlights() {
    hoveredNode = null;
    selectedTag.set(null);
    searchQuery = '';
    rebuildGraph();
  }

  function matchesQuery(node: GraphNode) {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    return getNodeLabel(node).toLowerCase().includes(q);
  }


  onMount(async () => {
    if (!browser) return;
    const module = await import('force-graph');
    ForceGraph = module.default;
    graph = ForceGraph()(containerEl)
      .width(width)
      .height(height)
      .backgroundColor('transparent')
      .enableNodeDrag(true)
      .onNodeClick((node: GraphNode) => {
        selectedTag.set(node.id);
      })
      .onNodeDblClick((node: GraphNode) => {
        const nodeType = getNodeType(node);
        if (nodeType === 'note') {
          window.location.href = `/notes?q=${encodeURIComponent(node.title || '')}`;
        } else if (nodeType === 'tag') {
          window.location.href = `/notes?tag=${encodeURIComponent(node.name || '')}`;
        }
      })
      .onNodeHover((node: GraphNode | null) => {
        hoveredNode = node;
      });

    applyStyling();
    rebuildGraph();
    loaded = true;
  });

  $: if (graph) {
    graph.width(width).height(height);
  }

  $: if (graph) {
    applyStyling();
  }

  $: if (graph) {
    rebuildGraph();
  }


  $: if (focusId !== null && focusId !== lastFocusId) {
    lastFocusId = focusId;
    focusOnNode(focusId);
  }

  onDestroy(() => {
    graph = null;
  });
</script>

<div class="graph-wrapper" style="width:100%; height:100%; position:relative; min-height: 400px;">
  {#if !loaded}
    <div class="graph-loading">Cargando grafo...</div>
  {/if}
  <div bind:this={containerEl} class="graph-canvas"></div>

  {#if loaded}
    <div class="graph-controls">
      <div class="search-wrap">
        <input
          class="graph-search"
          type="search"
          placeholder="Buscar nodos..."
          bind:value={searchQuery}
          on:input={() => { applyStyling(); }}
        />
        {#if searchQuery.trim().length > 0}
          <button class="search-clear" on:click={clearHighlights} aria-label="Limpiar busqueda">×</button>
        {/if}
      </div>
      <button class="btn btn-ghost btn-icon" title="Alternar etiquetas" on:click={() => { showLabels = !showLabels; applyStyling(); }}>
        <span style="font-size:10px; font-family: var(--font-mono);">Aa</span>
      </button>
      <button class="btn btn-ghost btn-icon" title="Particulas" class:active={showParticles} on:click={() => { showParticles = !showParticles; applyStyling(); }}>
        <span style="font-size:12px;">✨</span>
      </button>
      <button class="btn btn-ghost btn-icon" title="Ajustar" on:click={zoomToFit}>
        <span style="font-size:11px;">⊡</span>
      </button>
      <button class="btn btn-ghost btn-icon" title="Restablecer vista" on:click={resetView}>
        <span style="font-size:11px;">⊙</span>
      </button>
      <button class="btn btn-ghost btn-icon" title="Ocultar huerfanos" class:active={!showOrphans} on:click={() => { showOrphans = !showOrphans; rebuildGraph(); }}>
        <span style="font-size:11px;">◌</span>
      </button>
      <div class="filter-group">
        <select bind:value={filterType} on:change={rebuildGraph}>
          <option value="all">Todo</option>
          <option value="notes">Notas</option>
          <option value="tags">Tags</option>
        </select>
      </div>
    </div>
  {/if}
</div>

<style>
  .graph-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
  }

  .graph-canvas {
    width: 100%;
    height: 100%;
  }

  .graph-controls {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    z-index: 1000;
    pointer-events: auto;
    background: color-mix(in srgb, var(--elevated) 92%, transparent);
    padding: 10px;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
    box-shadow: 0 10px 20px rgba(0,0,0,0.25);
    backdrop-filter: blur(10px);
  }

  .btn-icon {
    width: 32px;
    height: 32px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .btn-icon.active {
    background: var(--accent);
    color: var(--bg);
  }

  .filter-group {
    margin-top: 4px;
  }

  .filter-group select {
    width: 100%;
    padding: 4px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    background: var(--elevated);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--r);
    cursor: pointer;
  }

  .filter-group select:focus {
    outline: none;
    border-color: var(--accent);
  }

  .search-wrap {
    position: relative;
  }

  .graph-search {
    width: 180px;
    padding: 6px 26px 6px 8px;
    font-size: 11px;
    font-family: var(--font-sans);
    background: color-mix(in srgb, var(--bg) 60%, transparent);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .graph-search:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent);
  }

  .search-clear {
    position: absolute;
    top: 50%;
    right: 6px;
    transform: translateY(-50%);
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 14px;
    cursor: pointer;
  }

  .graph-loading {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-muted);
    font-size: 13px;
    z-index: 10;
  }
</style>
