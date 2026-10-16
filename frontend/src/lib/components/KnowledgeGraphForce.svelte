<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { graphData, selectedTag } from '$lib/stores/graph';
  import type { GraphNode, GraphEdge } from '$lib/api';
  import { forceCollide } from 'd3';
  import type { NodeObject } from 'force-graph';
  import GraphSettingsPanel from './GraphSettingsPanel.svelte';
  import GraphQuickActions from './GraphQuickActions.svelte';
  import { getNodeType, COLOR_PRESETS, type ColorGroup } from '$lib/utils/graphUtils';
  import { applyGraphStyling } from '$lib/utils/graphStyling';
  import { filterGraphData } from '$lib/utils/graphFilters';
  import { t } from 'svelte-i18n';

  // ForceGraph constructor is dynamically imported; typed loosely since
  // force-graph uses a Kapsule factory pattern with complex generics not
  // fully captured by its .d.ts (callbacks expect NodeObject, we use GraphNode).
  let ForceGraph: any = null;

  // GraphNode extended with force-graph runtime properties (x, y added by the simulation)
  type ForceGraphNode = GraphNode & NodeObject;

  export let width = 800;
  export let height = 600;
  export let focusId: number | string | null = null;
  // Optional override data — when provided, uses this instead of the store
  // (used by the timeline/search filter in graph/+page.svelte, #373).
  export let data: { nodes: GraphNode[]; edges: GraphEdge[] } | null = null;

  let containerEl: HTMLDivElement;
  let graph: any = null;
  let lastFocusId: number | string | null = null;
  let searchQuery = '';

  // Toggles and Filter settings (Obsidian styles)
  let showNotes = true;
  let showTags = true;
  let showUnresolved = true;
  let showAttachments = true; // attachments toggle
  let showOrphans = true;
  let showCooccurrences = false; // default off to avoid clutter

  // Color Query Groups
  let colorGroups: ColorGroup[] = [];

  // Display Settings
  let showLabels = true;
  let showArrows = false;
  let nodeSizeScale = 1.0; // node size scale slider
  let linkThicknessScale = 1.0; // link thickness scale slider
  let textScale = 1.0;
  let labelThreshold = 0.8; // zoom level above which labels are shown by default
  let enableCollision = true;

  // Physics Force Settings
  let centerForce = 0.5;
  let repelForce = 150;
  let linkForce = 1.0;
  let linkDistance = 30;

  // Interaction State
  let hoveredNode: GraphNode | null = null;
  let loaded = false;

  // Use the `data` prop if provided (for timeline/search filtering, #373),
  // otherwise fall back to the global graph store.
  $: effectiveData = data || $graphData;

  // Helper function to build neighbor map for smart highlighting
  let neighbors = new Map<number | string, Set<number | string>>();
  $: {
    neighbors.clear();
    const edges = effectiveData.edges;
    edges.forEach((edge) => {
      const s = typeof edge.source === 'object' ? (edge.source as GraphNode).id : edge.source;
      const t = typeof edge.target === 'object' ? (edge.target as GraphNode).id : edge.target;

      if (!neighbors.has(s)) neighbors.set(s, new Set());
      if (!neighbors.has(t)) neighbors.set(t, new Set());

      neighbors.get(s)!.add(t);
      neighbors.get(t)!.add(s);
    });
  }

  function addColorGroup() {
    colorGroups = [
      ...colorGroups,
      { query: '', color: COLOR_PRESETS[colorGroups.length % COLOR_PRESETS.length] },
    ];
    saveGroups();
  }

  function removeColorGroup(idx: number) {
    colorGroups = colorGroups.filter((_, i) => i !== idx);
    saveGroups();
  }

  function saveGroups() {
    if (browser) {
      localStorage.setItem('joidy-graph-color-groups', JSON.stringify(colorGroups));
      applyStyling();
    }
  }

  function resetForces() {
    centerForce = 0.5;
    repelForce = 150;
    linkForce = 1.0;
    linkDistance = 30;
    enableCollision = true;
    nodeSizeScale = 1.0;
    linkThicknessScale = 1.0;
  }

  function rebuildGraph() {
    if (!graph) return;
    const src = data || $graphData;
    const { nodes, edges } = filterGraphData(src, {
      showNotes,
      showTags,
      showUnresolved,
      showAttachments,
      showOrphans,
      showCooccurrences,
    });
    graph.graphData({ nodes, links: edges });
    graph.d3ReheatSimulation();
  }

  function applyStyling() {
    if (!graph) return;
    applyGraphStyling(graph, {
      hoveredNode,
      selectedTag: $selectedTag,
      searchQuery,
      focusId,
      neighbors,
      nodeSizeScale,
      linkThicknessScale,
      showLabels,
      textScale,
      labelThreshold,
      colorGroups,
    });
  }

  function focusOnNode(id: number | string) {
    if (!graph) return;
    const node = graph.graphData().nodes.find((n: ForceGraphNode) => n.id === id) as
      ForceGraphNode | undefined;
    if (!node) return;
    graph.centerAt(node.x ?? 0, node.y ?? 0, 400);
    graph.zoom(1.2, 400);
  }

  function resetView() {
    if (!graph) return;
    graph.centerAt(0, 0, 300);
    graph.zoom(0.8, 300);
  }

  function zoomToFit() {
    if (!graph) return;
    graph.zoomToFit(500, 50);
  }

  function zoomIn() {
    if (!graph) return;
    const cur = graph.zoom();
    graph.zoom(Math.min(cur * 1.3, 8), 300);
  }

  function zoomOut() {
    if (!graph) return;
    const cur = graph.zoom();
    graph.zoom(Math.max(cur / 1.3, 0.1), 300);
  }

  function clearHighlights() {
    hoveredNode = null;
    selectedTag.set(null);
    searchQuery = '';
    rebuildGraph();
  }

  let lastClickTime = 0;
  function handleNodeClick(node: GraphNode) {
    const currentTime = Date.now();
    const delay = currentTime - lastClickTime;

    selectedTag.set(node.id);

    if (delay < 300) {
      const nodeType = getNodeType(node);
      if (nodeType === 'note') {
        window.location.href = `/notes?id=${node.id}`;
      } else if (nodeType === 'tag') {
        window.location.href = `/notes?search=${encodeURIComponent('tag:' + node.name)}`;
      } else if (nodeType === 'unresolved') {
        window.location.href = `/notes?new=1&title=${encodeURIComponent(node.title || '')}`;
      }
    }
    lastClickTime = currentTime;
  }

  onMount(async () => {
    if (!browser) return;

    // Load saved color query groups
    const saved = localStorage.getItem('joidy-graph-color-groups');
    if (saved) {
      try {
        colorGroups = JSON.parse(saved);
      } catch (e) {}
    } else {
      // Default presets
      colorGroups = [
        { query: 'tag:importante', color: '#f59e0b' },
        { query: 'tag:idea', color: '#10b981' },
      ];
    }

    const module = await import('force-graph');
    if (!containerEl) return; // Prevent crash if unmounted during import

    // force-graph uses a Kapsule factory pattern: ForceGraph() returns a
    // constructor, then calling it with the element creates a chainable instance.
    ForceGraph = module.default;
    graph = ForceGraph()(containerEl)
      .width(width)
      .height(height)
      .backgroundColor('transparent')
      .enableNodeDrag(true)
      .onNodeClick(handleNodeClick)
      .onNodeHover((node: ForceGraphNode | null) => {
        hoveredNode = node as GraphNode | null;
      });

    // NOTE: a `.minimap('#graph-minimap', ...)` chain used to be appended here,
    // but `force-graph` (>=1.48) does not expose a `minimap()` method, so the
    // call threw `TypeError: ...minimap is not a function` and left the graph
    // stuck on "Cargando grafo de conocimiento..." (#201). The minimap can be
    // re-implemented as a separate <canvas> overlay in a follow-up.

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

  $: if (graph && loaded) {
    rebuildGraph();
  }

  // Reactive simulation force properties
  $: if (graph && loaded) {
    const charge = graph.d3Force('charge');
    if (charge) {
      charge.strength(-repelForce);
    }

    const link = graph.d3Force('link');
    if (link) {
      link.distance(linkDistance).strength(linkForce * 0.15);
    }

    if (enableCollision) {
      graph.d3Force(
        'collide',
        forceCollide((node: any) => {
          const isTag = node.type === 'tag';
          const r = isTag ? 4.8 : 3.4;
          return r + 8; // radius + padding for collision physics
        })
      );
    } else {
      graph.d3Force('collide', null);
    }

    graph.d3ReheatSimulation();
  }

  $: if (focusId !== null && focusId !== lastFocusId) {
    lastFocusId = focusId;
    focusOnNode(focusId);
  }

  onDestroy(() => {
    graph = null;
  });
</script>

<div class="graph-wrapper" style="width:100%; height:100%; position:relative; min-height: 450px;">
  {#if !loaded}
    <div class="graph-loading">{$t('knowledgeGraphForce.loading')}</div>
  {/if}

  <div bind:this={containerEl} class="graph-canvas"></div>

  {#if loaded}
    <GraphSettingsPanel
      bind:searchQuery
      bind:showNotes
      bind:showTags
      bind:showUnresolved
      bind:showAttachments
      bind:showOrphans
      bind:showCooccurrences
      bind:colorGroups
      bind:showLabels
      bind:showArrows
      bind:nodeSizeScale
      bind:linkThicknessScale
      bind:textScale
      bind:labelThreshold
      bind:enableCollision
      bind:centerForce
      bind:repelForce
      bind:linkForce
      bind:linkDistance
      {applyStyling}
      {rebuildGraph}
      {saveGroups}
      {addColorGroup}
      {removeColorGroup}
      {resetForces}
    />

    <GraphQuickActions {zoomIn} {zoomOut} {zoomToFit} {resetView} {clearHighlights} />
  {/if}
</div>

<style>
  .graph-wrapper {
    width: 100%;
    height: 100%;
    position: relative;
    overflow: hidden;
  }

  .graph-canvas {
    width: 100%;
    height: 100%;
    cursor: grab;
  }

  .graph-canvas:active {
    cursor: grabbing;
  }

  .graph-loading {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-muted);
    font-size: 13px;
    z-index: var(--z-sticky);
  }
</style>
