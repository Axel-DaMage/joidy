<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  // Named imports — `import * as d3` pulled every subpackage into the chunk.
  import {
    drag,
    forceCenter,
    forceCollide,
    forceLink,
    forceManyBody,
    forceSimulation,
    select,
    zoom,
    zoomIdentity,
  } from 'd3';
  // Side-effect: `.transition()` on selections lives in d3-transition.
  import 'd3-transition';
  import type {
    D3DragEvent,
    D3ZoomEvent,
    Simulation,
    SimulationLinkDatum,
    SimulationNodeDatum,
    ZoomBehavior,
  } from 'd3';
  import { graphData, selectedTag } from '$lib/stores/graph';
  import type { GraphNode, GraphEdge } from '$lib/api';
  import { t } from 'svelte-i18n';

  export let width = 800;
  export let height = 600;
  export let focusId: number | string | null = null;

  let svgEl: SVGSVGElement;
  let canvasEl: HTMLCanvasElement;
  let tooltip = { visible: false, x: 0, y: 0, text: '', node: null as GraphNode | null };
  let showLabels = true;
  let showParticles = true;
  let filterType: 'all' | 'notes' | 'tags' = 'all';
  let showOrphans = true;
  let searchQuery = '';
  let hoveredId: number | string | null = null;
  let lastFocusId: number | string | null = null;

  let ctx: CanvasRenderingContext2D | null = null;
  let rafId: number | null = null;
  let drawFn: (() => void) | null = null;
  let sim: Simulation<SimNode, undefined> | undefined;
  let zoomBehavior: ZoomBehavior<SVGSVGElement, unknown>;
  let currentTransform = zoomIdentity;

  // Radial node gradients depend only on (type, radius) — cache them instead
  // of allocating one per node per frame (#1311).
  const gradientCache = new Map<string, CanvasGradient>();
  let neighborMap = new Map<number | string, Set<number | string>>();
  let labelIndex = new Map<number | string, string>();

  // ── Accessibility (#1309) ──────────────────────────────────────────────
  // Mirror of the *filtered* node set so assistive tech can navigate the
  // same data the canvas draws (WCAG 1.1.1 / 2.1.1).
  let accessibleNodes: GraphNode[] = [];
  let accessibleEdgeCount = 0;
  let announcement = '';

  $: graphSummary = $t('a11y.graphSummary', {
    values: {
      notes: accessibleNodes.filter((n) => getNodeType(n) === 'note').length,
      tags: accessibleNodes.filter((n) => getNodeType(n) === 'tag').length,
      links: accessibleEdgeCount,
    },
  });

  function selectNodeFromList(node: GraphNode) {
    selectedTag.set(node.id);
    announcement = getNodeLabel(node);
    focusOnNode(node.id);
  }

  const COLORS = {
    tag: '#7d6b91',
    note: '#4a90a4',
    selected: '#e8a838',
    hierarchy: '#666',
    cooccurrence: '#999',
    linked: '#3b82f6',
    tagged: '#8b5cf6',
    default: '#888',
  };

  function getLinkColor(type: string): string {
    return COLORS[type as keyof typeof COLORS] || COLORS.default;
  }

  interface SimNode extends GraphNode, SimulationNodeDatum {
  }

  interface SimLink extends SimulationLinkDatum<SimNode> {
    type: GraphEdge['type'];
    weight: number;
    particles?: Particle[];
  }

  interface Particle {
    offset: number;
    speed: number;
  }

  function getNodeType(n: GraphNode): 'tag' | 'note' {
    return (n.type === 'note' || n.type === 'tag') ? n.type : 'tag';
  }

  function getNodeLabel(n: GraphNode): string {
    return getNodeType(n) === 'note' ? (n.title || '') : (n.name || '');
  }

  function getTooltipTypeLabel(node: GraphNode | null): string {
    if (!node) return '';
    return getNodeType(node) === 'note' ? '📄 Nota' : '🏷️ Tag';
  }

  function filterNodes(nodes: GraphNode[]): GraphNode[] {
    if (filterType === 'all') return nodes;
    if (filterType === 'notes') return nodes.filter(n => getNodeType(n) === 'note');
    if (filterType === 'tags') return nodes.filter(n => getNodeType(n) === 'tag');
    return nodes;
  }

  function render(nodes: GraphNode[], edges: GraphEdge[]) {
    if (!svgEl || !canvasEl || nodes.length === 0) return;

    ctx = canvasEl.getContext('2d');
    if (!ctx) return;

    if (sim) sim.stop();
    cancelPendingFrame();
    select(svgEl).selectAll('*').remove();

    let filteredNodes = filterNodes(nodes);
    if (filteredNodes.length === 0) {
      // Keep the accessible mirror in sync with what is actually drawn
      accessibleNodes = [];
      accessibleEdgeCount = 0;
      return;
    }

    let nodeIds = new Set<number | string>(filteredNodes.map(n => n.id));
    let filteredEdges = edges.filter(e =>
      nodeIds.has(e.source) && nodeIds.has(e.target)
    );

    if (!showOrphans) {
      const degreeMap = new Map<number | string, number>();
      filteredEdges.forEach((e) => {
        degreeMap.set(e.source, (degreeMap.get(e.source) ?? 0) + 1);
        degreeMap.set(e.target, (degreeMap.get(e.target) ?? 0) + 1);
      });
      filteredNodes = filteredNodes.filter(n => (degreeMap.get(n.id) ?? 0) > 0);
      nodeIds = new Set(filteredNodes.map(n => n.id));
      filteredEdges = filteredEdges.filter(e =>
        nodeIds.has(e.source) && nodeIds.has(e.target)
      );
    }

    // Publish the exact filtered set for the non-visual node list (#1309)
    accessibleNodes = filteredNodes;
    accessibleEdgeCount = filteredEdges.length;

    const svg = select(svgEl);
    const g = svg.append('g');

    currentTransform = zoomIdentity;

    zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 4])
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        currentTransform = event.transform;
        g.attr('transform', event.transform.toString());
        scheduleDraw();
      });
    svg.call(zoomBehavior);
    
    // Give nodes random initial positions spread across the canvas
    const simNodes: SimNode[] = filteredNodes.map((n) => ({
      ...n,
      x: width/2 + (Math.random() - 0.5) * width * 0.8,
      y: height/2 + (Math.random() - 0.5) * height * 0.8,
    }));
    const nodeMap = new Map<number | string, SimNode>(simNodes.map(n => [n.id, n]));
    neighborMap = new Map();
    labelIndex = new Map(simNodes.map(n => [n.id, getNodeLabel(n).toLowerCase()]));

    const simLinks: SimLink[] = filteredEdges.map((e: GraphEdge) => ({
      source: nodeMap.get(e.source) as SimNode,
      target: nodeMap.get(e.target) as SimNode,
      type: e.type,
      weight: e.weight ?? 1,
      particles: e.type === 'linked' || e.type === 'tagged' ? [
        { offset: 0, speed: 0.002 + Math.random() * 0.001 },
        { offset: 0.33, speed: 0.002 + Math.random() * 0.001 },
        { offset: 0.66, speed: 0.002 + Math.random() * 0.001 }
      ] : undefined,
    })).filter(l => l.source && l.target);

    simLinks.forEach((l) => {
      const sourceId = (l.source as SimNode).id;
      const targetId = (l.target as SimNode).id;
      if (!neighborMap.has(sourceId)) neighborMap.set(sourceId, new Set());
      if (!neighborMap.has(targetId)) neighborMap.set(targetId, new Set());
      neighborMap.get(sourceId)?.add(targetId);
      neighborMap.get(targetId)?.add(sourceId);
    });

    const nodeRadiusBase = (n: SimNode) => getNodeType(n) === 'note' ? 4 : 6;

    const simulation = forceSimulation(simNodes)
      .force('link', forceLink<SimNode, SimLink>(simLinks)
        .id((d: SimNode) => d.id)
        .distance(60)
        .strength(0.3))
      .force('charge', forceManyBody().strength(-150).theta(0.8))
      .force('center', forceCenter(width / 2, height / 2).strength(0.05))
      .force('collision', forceCollide<SimNode>().radius((d: SimNode) => nodeRadiusBase(d) + 6))
      .alphaDecay(0.03)
      .velocityDecay(0.3)
      .alphaMin(0.001);

    // Demand-driven rendering (#1311): each simulation tick schedules ONE
    // paint on the next animation frame. The loop stops on its own when the
    // layout cools (alpha < alphaMin stops d3's internal timer), while the
    // tab is hidden, or on destroy — the old code re-scheduled rAF forever.
    simulation.on('tick', scheduleDraw);

    svg.on('click', () => {
      selectedTag.set(null);
    });

    const nodeElements = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .on('click', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        selectedTag.set(d.id);
      })
      .on('dblclick', (event: MouseEvent, d: SimNode) => {
        event.stopPropagation();
        const nodeType = getNodeType(d);
        if (nodeType === 'note' && d.path) {
          window.location.href = `/notes?q=${encodeURIComponent(d.title || '')}`;
        } else if (nodeType === 'tag') {
          window.location.href = `/notes?tag=${encodeURIComponent(d.name || '')}`;
        }
      })
      .on('contextmenu', (event: MouseEvent, d: SimNode) => {
        event.preventDefault();
        event.stopPropagation();
        selectedTag.set(d.id);
        const nodeType = getNodeType(d);
        tooltip = {
          visible: true,
          x: event.clientX,
          y: event.clientY,
          text: `${nodeType === 'note' ? d.title : d.name}`,
          node: d,
        };
      })
      .on('mouseover', (event: MouseEvent, d: SimNode) => {
        hoveredId = d.id;
        const nodeType = getNodeType(d);
        const count = nodeType === 'tag' ? `${d.note_count || 0} notas` : '';
        tooltip = {
          visible: true,
          x: event.clientX + 10,
          y: event.clientY - 10,
          text: `${nodeType === 'note' ? d.title : d.name} ${count}`.trim(),
          node: d,
        };
        scheduleDraw();
      })
      .on('mouseout', () => {
        hoveredId = null;
        tooltip = { ...tooltip, visible: false };
        scheduleDraw();
      })
      .call(drag<SVGGElement, SimNode>()
        .on('start', (event: D3DragEvent<SVGGElement, SimNode, SimNode>, d: SimNode) => {
          if (!event.active) simulation?.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event: D3DragEvent<SVGGElement, SimNode, SimNode>, d: SimNode) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event: D3DragEvent<SVGGElement, SimNode, SimNode>, d: SimNode) => {
          if (!event.active) simulation?.alphaTarget(0);
        }) as any);

    nodeElements.append('circle')
      .attr('r', (d: SimNode) => nodeRadiusBase(d))
      .attr('fill', 'transparent')
      .attr('stroke', 'transparent')
      .attr('stroke-width', 1);

    if (showLabels) {
      nodeElements.append('text')
        .attr('dy', (d: SimNode) => nodeRadiusBase(d) + 12)
        .attr('text-anchor', 'middle')
        .attr('font-family', 'var(--font-sans)')
        .attr('font-size', '10px')
        .attr('fill', 'var(--text-secondary)')
        .attr('pointer-events', 'none')
        .text((d: SimNode) => getNodeType(d) === 'note' ? (d.title || '').slice(0, 20) : (d.name || ''));
    }

    function draw() {
      if (!ctx) return;
      ctx.save();
      ctx.clearRect(0, 0, width, height);
      ctx.setTransform(1, 0, 0, 1, 0, 0);

      if (currentTransform) {
        ctx.translate(currentTransform.x, currentTransform.y);
        ctx.scale(currentTransform.k, currentTransform.k);
      }

      const focus = hoveredId ?? $selectedTag;
      const query = searchQuery.trim().toLowerCase();
      const hasQuery = query.length > 0;
      const matchesQuery = (node: SimNode) => {
        if (!hasQuery) return true;
        const label = labelIndex.get(node.id) ?? '';
        return label.includes(query);
      };

      simLinks.forEach((link: SimLink) => {
        const source = link.source as SimNode;
        const target = link.target as SimNode;
        if (!source.x || !source.y || !target.x || !target.y) return;

        const sx = source.x, sy = source.y;
        const tx = target.x, ty = target.y;

        let linkAlpha = link.type === 'cooccurrence' ? 0.3 : 0.5;
        if (focus !== null) {
          const sourceId = source.id;
          const targetId = target.id;
          linkAlpha = (sourceId === focus || targetId === focus) ? 0.9 : 0.08;
        } else if (hasQuery) {
          linkAlpha = (matchesQuery(source) || matchesQuery(target)) ? 0.55 : 0.05;
        }

        ctx!.beginPath();
        ctx!.strokeStyle = getLinkColor(link.type);
        ctx!.globalAlpha = linkAlpha;
        ctx!.lineWidth = link.type === 'hierarchy' ? 1.2 : 0.8;

        if (link.type === 'cooccurrence') {
          ctx!.setLineDash([3, 3]);
        } else {
          ctx!.setLineDash([]);
        }

        ctx!.moveTo(sx, sy);
        ctx!.lineTo(tx, ty);
        ctx!.stroke();
        ctx!.setLineDash([]);
        ctx!.globalAlpha = 1;

        if (showParticles && link.particles && (link.type === 'linked' || link.type === 'tagged')) {
          const dx = tx - sx, dy = ty - sy;
          const len = Math.sqrt(dx * dx + dy * dy);
          if (len === 0) return;

          link.particles.forEach((p: Particle) => {
            p.offset = (p.offset + p.speed) % 1;
            const px = sx + dx * p.offset;
            const py = sy + dy * p.offset;
            ctx!.beginPath();
            ctx!.arc(px, py, 1.5, 0, Math.PI * 2);
            ctx!.fillStyle = getLinkColor(link.type);
            ctx!.globalAlpha = focus !== null ? 0.8 : 0.7;
            ctx!.fill();
          });
        }
      });

      simNodes.forEach((node: SimNode) => {
        if (node.x === undefined || node.y === undefined) return;
        const r = nodeRadiusBase(node);
        const nodeType = getNodeType(node);
        const isFocus = focus !== null && (node.id === focus || neighborMap.get(focus)?.has(node.id));
        const matches = matchesQuery(node);
        const nodeAlpha = focus !== null
          ? (isFocus ? 1 : 0.15)
          : (hasQuery ? (matches ? 1 : 0.15) : 1);

        const gradientKey = `${nodeType}:${r}`;
        let gradient = gradientCache.get(gradientKey);
        if (!gradient) {
          gradient = ctx!.createRadialGradient(-r * 0.3, -r * 0.3, 0, 0, 0, r);
          gradient.addColorStop(0, nodeType === 'tag' ? '#9d8bb0' : '#5ba3b8');
          gradient.addColorStop(1, nodeType === 'tag' ? COLORS.tag : COLORS.note);
          gradientCache.set(gradientKey, gradient);
        }
        ctx!.globalAlpha = nodeAlpha;
        ctx!.save();
        ctx!.translate(node.x, node.y);
        ctx!.beginPath();
        ctx!.fillStyle = gradient;
        ctx!.arc(0, 0, r, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();

        if (node.id === hoveredId) {
          ctx!.beginPath();
          ctx!.strokeStyle = '#ffffff';
          ctx!.lineWidth = 1.5;
          ctx!.globalAlpha = 0.9;
          ctx!.arc(node.x, node.y, r + 2, 0, Math.PI * 2);
          ctx!.stroke();
        }

        if (node.id === $selectedTag) {
          ctx!.beginPath();
          ctx!.strokeStyle = COLORS.selected;
          ctx!.lineWidth = 2;
          ctx!.arc(node.x, node.y, r + 3, 0, Math.PI * 2);
          ctx!.stroke();
        }

        if (hasQuery && matches && focus === null) {
          ctx!.beginPath();
          ctx!.strokeStyle = '#e8a838';
          ctx!.lineWidth = 1.5;
          ctx!.globalAlpha = 0.8;
          ctx!.arc(node.x, node.y, r + 2.5, 0, Math.PI * 2);
          ctx!.stroke();
        }
      });

      ctx.restore();
    }

    // Paints are requested via scheduleDraw() — no self-rescheduling rAF.
    drawFn = draw;

    return simulation;
  }

  function scheduleDraw() {
    if (rafId === null && typeof document !== 'undefined' && !document.hidden) {
      rafId = requestAnimationFrame(drawFrame);
    }
  }

  function drawFrame() {
    rafId = null;
    drawFn?.();
    // Link particles are continuous animation — keep the loop alive only
    // while they are enabled and the tab is visible (#1311).
    if (showParticles && typeof document !== 'undefined' && !document.hidden) {
      scheduleDraw();
    }
  }

  function cancelPendingFrame() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  function handleVisibilityChange() {
    if (typeof document === 'undefined') return;
    if (document.hidden) {
      cancelPendingFrame();
    } else {
      scheduleDraw();
    }
  }

  function zoomToFit() {
    if (!svgEl || !sim) return;
    const nodes = sim.nodes();
    if (nodes.length === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    nodes.forEach((n: SimNode) => {
      if (n.x !== undefined && n.y !== undefined) {
        minX = Math.min(minX, n.x);
        minY = Math.min(minY, n.y);
        maxX = Math.max(maxX, n.x);
        maxY = Math.max(maxY, n.y);
      }
    });

    const padding = 50;
    const graphWidth = maxX - minX + padding * 2;
    const graphHeight = maxY - minY + padding * 2;
    const scale = Math.min(width / graphWidth, height / graphHeight, 2);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    select(svgEl).transition().duration(500).call(
      zoomBehavior.transform as never,
      zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-centerX, -centerY)
    );
  }

  function resetView() {
    if (!svgEl) return;
    select(svgEl).transition().duration(300).call(
      zoomBehavior.transform as never,
      zoomIdentity
    );
  }

  function rerender() {
    if (sim) sim.stop();
    cancelPendingFrame();
    sim = render($graphData.nodes, $graphData.edges) as typeof sim;
  }

  function recenter() {
    zoomToFit();
  }

  function focusOnNode(id: number | string) {
    if (!svgEl || !sim) return;
    const node = sim.nodes().find(n => n.id === id);
    if (!node || node.x === undefined || node.y === undefined) return;
    const scale = Math.min(Math.max(currentTransform.k, 0.7), 2.4);
    select(svgEl).transition().duration(450).call(
      zoomBehavior.transform as never,
      zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-node.x, -node.y)
    );
  }

  function clearHighlights() {
    hoveredId = null;
    selectedTag.set(null);
    searchQuery = '';
    rerender();
  }

  $: if (svgEl && $graphData && width && height) {
    rerender();
  }

  $: if (focusId !== null && focusId !== lastFocusId) {
    lastFocusId = focusId;
    focusOnNode(focusId);
  }

  // Repaint on selection changes — the canvas only highlights what it is told
  // to redraw (#1311).
  $: if ($selectedTag !== undefined) scheduleDraw();


  onMount(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  });

  onDestroy(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    if (sim) sim.stop();
    cancelPendingFrame();
    drawFn = null;
  });
</script>

<div class="graph-wrapper" style="width:100%; height:100%; position:relative; min-height: 400px;">
  <!-- Canvas is a raster drawing surface — hidden from AT; the svg carries
       the summary label and the nav below provides the node list (#1309). -->
  <canvas bind:this={canvasEl} width={width} height={height} style="position:absolute; top:0; left:0; z-index:1;" aria-hidden="true"></canvas>
  <svg
    bind:this={svgEl}
    width={width}
    height={height}
    style="position:absolute; top:0; left:0; z-index:2; background:transparent;"
    role="img"
    aria-label={graphSummary}
  ></svg>

  <!-- Keyboard-operable equivalent of the pointer-only node canvas:
       visually collapsed until it receives keyboard focus (#1309). -->
  <nav class="node-list-nav" aria-label={$t('a11y.graphNodesList')}>
    <ul class="node-list">
      {#each accessibleNodes as node (node.id)}
        <li>
          <button type="button" class="node-list-btn" onclick={() => selectNodeFromList(node)}>
            {getNodeLabel(node)}
          </button>
        </li>
      {/each}
    </ul>
  </nav>

  <!-- Announces node selections made through the list or the canvas -->
  <div class="visually-hidden" aria-live="polite">{announcement}</div>

  {#if tooltip.visible}
    <div class="tooltip" style="position:fixed; left:{tooltip.x}px; top:{tooltip.y}px; z-index:100;">
      <div class="tooltip-main">{tooltip.text}</div>
      {#if tooltip.node}
        <div class="tooltip-meta">
          {getTooltipTypeLabel(tooltip.node)}
          {#if getNodeType(tooltip.node) === 'note' && tooltip.node.path}
            <span class="tooltip-path">{tooltip.node.path}</span>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <div class="graph-controls">
    <div class="search-wrap">
      <input
        class="graph-search"
        type="search"
        placeholder={$t('knowledgeGraph.searchPlaceholder')}
        aria-label={$t('knowledgeGraph.searchPlaceholder')}
        bind:value={searchQuery}
        oninput={scheduleDraw}
      />
      {#if searchQuery.trim().length > 0}
        <button class="search-clear" onclick={clearHighlights} aria-label={$t('knowledgeGraph.clearSearch')}>×</button>
      {/if}
    </div>
    <button class="btn btn-ghost btn-icon" title={$t('knowledgeGraph.toggleLabels')} aria-label={$t('knowledgeGraph.toggleLabels')} aria-pressed={showLabels} class:active={showLabels} onclick={() => { showLabels = !showLabels; rerender(); }}>
      <span style="font-size:10px; font-family: var(--font-mono);">Aa</span>
    </button>
    <button class="btn btn-ghost btn-icon" title={$t('knowledgeGraph.particles')} aria-label={$t('knowledgeGraph.particles')} aria-pressed={showParticles} class:active={showParticles} onclick={() => { showParticles = !showParticles; scheduleDraw(); }}>
      <span style="font-size:12px;">✨</span>
    </button>
    <button class="btn btn-ghost btn-icon" title={$t('knowledgeGraph.fit')} aria-label={$t('knowledgeGraph.fit')} onclick={recenter}>
      <span style="font-size:11px;">⊡</span>
    </button>
    <button class="btn btn-ghost btn-icon" title={$t('knowledgeGraph.resetView')} aria-label={$t('knowledgeGraph.resetView')} onclick={resetView}>
      <span style="font-size:11px;">⊙</span>
    </button>
    <button class="btn btn-ghost btn-icon" title={$t('knowledgeGraph.hideOrphans')} aria-label={$t('knowledgeGraph.hideOrphans')} aria-pressed={!showOrphans} class:active={!showOrphans} onclick={() => { showOrphans = !showOrphans; rerender(); }}>
      <span style="font-size:11px;">◌</span>
    </button>
    <div class="filter-group">
      <select bind:value={filterType} onchange={rerender} aria-label={$t('knowledgeGraph.all')}>
        <option value="all">{$t('knowledgeGraph.all')}</option>
        <option value="notes">{$t('knowledgeGraph.notes')}</option>
        <option value="tags">{$t('knowledgeGraph.tags')}</option>
      </select>
    </div>
  </div>
</div>

<style>
  /* Keyboard node list — invisible until it receives focus (#1309) */
  .node-list-nav {
    position: absolute;
    top: 8px;
    left: 8px;
    z-index: calc(var(--z-modal) + 1);
    opacity: 0;
    pointer-events: none;
  }

  /* opacity (not visibility/display) keeps the buttons in the tab order;
     :focus-within reveals the panel as soon as Tab lands inside */
  .node-list-nav:focus-within {
    opacity: 1;
    pointer-events: auto;
  }

  .node-list {
    list-style: none;
    margin: 0;
    padding: 8px;
    max-height: 50vh;
    overflow-y: auto;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: 0 10px 20px rgba(0,0,0,0.25);
  }

  .node-list-btn {
    display: block;
    width: 100%;
    padding: 4px 8px;
    background: none;
    border: none;
    border-radius: 4px;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 11px;
    text-align: left;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 240px;
  }

  .node-list-btn:hover,
  .node-list-btn:focus-visible {
    background: var(--accent);
    color: var(--bg);
    outline: none;
  }

  .tooltip {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 10px;
    font-size: 12px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    pointer-events: none;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }
  .tooltip-main { font-weight: 500; }
  .tooltip-meta {
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 2px;
    display: flex;
    gap: 8px;
  }
  .tooltip-path { opacity: 0.7; font-family: var(--font-mono); }

  .graph-controls {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    z-index: var(--z-modal);
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
  .filter-group select:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
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
  .graph-search:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
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
</style>
