<script lang="ts">
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import * as d3 from 'd3';
  import { graphData, selectedTag } from '$lib/stores/graph';
  import type { GraphNode, GraphEdge } from '$lib/api';

  export let width = 800;
  export let height = 600;
  export let focusId: number | null = null;

  let svgEl: SVGSVGElement;
  let canvasEl: HTMLCanvasElement;
  let tooltip = { visible: false, x: 0, y: 0, text: '', node: null as GraphNode | null };
  let showLabels = true;
  let showParticles = true;
  let filterType: 'all' | 'notes' | 'tags' = 'all';
  let showOrphans = true;
  let searchQuery = '';
  let hoveredId: number | null = null;
  let lastFocusId: number | null = null;

  let ctx: CanvasRenderingContext2D | null = null;
  let animationFrame: number;
  let sim: d3.Simulation<SimNode, undefined> | undefined;
  let zoom: d3.ZoomBehavior<SVGSVGElement, unknown>;
  let currentTransform = d3.zoomIdentity;
  let neighborMap = new Map<number, Set<number>>();
  let labelIndex = new Map<number, string>();

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

  interface SimNode extends GraphNode {
    x?: number;
    y?: number;
    fx?: number | null;
    fy?: number | null;
    vx?: number;
    vy?: number;
  }

  interface SimLink extends d3.SimulationLinkDatum<SimNode> {
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
    cancelAnimationFrame(animationFrame);
    d3.select(svgEl).selectAll('*').remove();

    let filteredNodes = filterNodes(nodes);
    if (filteredNodes.length === 0) return;

    let nodeIds = new Set(filteredNodes.map(n => n.id));
    let filteredEdges = edges.filter(e =>
      nodeIds.has(e.source as number) && nodeIds.has(e.target as number)
    );

    if (!showOrphans) {
      const degreeMap = new Map<number, number>();
      filteredEdges.forEach((e) => {
        degreeMap.set(e.source as number, (degreeMap.get(e.source as number) ?? 0) + 1);
        degreeMap.set(e.target as number, (degreeMap.get(e.target as number) ?? 0) + 1);
      });
      filteredNodes = filteredNodes.filter(n => (degreeMap.get(n.id) ?? 0) > 0);
      nodeIds = new Set(filteredNodes.map(n => n.id));
      filteredEdges = filteredEdges.filter(e =>
        nodeIds.has(e.source as number) && nodeIds.has(e.target as number)
      );
    }

    const svg = d3.select(svgEl);
    const g = svg.append('g');

    currentTransform = d3.zoomIdentity;

    zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 4])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        currentTransform = event.transform;
        g.attr('transform', event.transform.toString());
      });
    svg.call(zoom);
    
    // Give nodes random initial positions spread across the canvas
    const simNodes: SimNode[] = filteredNodes.map((n) => ({
      ...n,
      x: width/2 + (Math.random() - 0.5) * width * 0.8,
      y: height/2 + (Math.random() - 0.5) * height * 0.8,
    }));
    const nodeMap = new Map(simNodes.map(n => [n.id, n]));
    neighborMap = new Map();
    labelIndex = new Map(simNodes.map(n => [n.id, getNodeLabel(n).toLowerCase()]));

    const simLinks: SimLink[] = filteredEdges.map((e: GraphEdge) => ({
      source: nodeMap.get(e.source as number) as SimNode,
      target: nodeMap.get(e.target as number) as SimNode,
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

    const simulation = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks)
        .id((d: SimNode) => d.id)
        .distance(60)
        .strength(0.3))
      .force('charge', d3.forceManyBody().strength(-150).theta(0.8))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
      .force('collision', d3.forceCollide().radius((d: SimNode) => nodeRadiusBase(d) + 6))
      .alphaDecay(0.03)
      .velocityDecay(0.3)
      .alphaMin(0.001);

    simulation.on('tick', () => {
      draw();
    });

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
          x: event.pageX,
          y: event.pageY,
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
          x: event.pageX + 10,
          y: event.pageY - 10,
          text: `${nodeType === 'note' ? d.title : d.name} ${count}`.trim(),
          node: d,
        };
      })
      .on('mouseout', () => {
        hoveredId = null;
        tooltip = { ...tooltip, visible: false };
      })
      .call(d3.drag<SVGGElement, SimNode>()
        .on('start', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d: SimNode) => {
          if (!event.active) simulation?.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d: SimNode) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d: SimNode) => {
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
        if (!link.source.x || !link.source.y || !link.target.x || !link.target.y) return;

        const sx = link.source.x, sy = link.source.y;
        const tx = link.target.x, ty = link.target.y;

        let linkAlpha = link.type === 'cooccurrence' ? 0.3 : 0.5;
        if (focus !== null) {
          const sourceId = (link.source as SimNode).id;
          const targetId = (link.target as SimNode).id;
          linkAlpha = (sourceId === focus || targetId === focus) ? 0.9 : 0.08;
        } else if (hasQuery) {
          const sourceNode = link.source as SimNode;
          const targetNode = link.target as SimNode;
          linkAlpha = (matchesQuery(sourceNode) || matchesQuery(targetNode)) ? 0.55 : 0.05;
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

        ctx!.beginPath();
        const gradient = ctx!.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r);
        gradient.addColorStop(0, nodeType === 'tag' ? '#9d8bb0' : '#5ba3b8');
        gradient.addColorStop(1, nodeType === 'tag' ? COLORS.tag : COLORS.note);
        ctx!.fillStyle = gradient;
        ctx!.globalAlpha = nodeAlpha;
        ctx!.arc(node.x, node.y, r, 0, Math.PI * 2);
        ctx!.fill();

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
      animationFrame = requestAnimationFrame(draw);
    }

    return simulation;
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

    d3.select(svgEl).transition().duration(500).call(
      zoom.transform as never,
      d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-centerX, -centerY)
    );
  }

  function resetView() {
    if (!svgEl) return;
    d3.select(svgEl).transition().duration(300).call(
      zoom.transform as never,
      d3.zoomIdentity
    );
  }

  function rerender() {
    if (sim) sim.stop();
    cancelAnimationFrame(animationFrame);
    sim = render($graphData.nodes, $graphData.edges) as typeof sim;
  }

  function recenter() {
    zoomToFit();
  }

  function focusOnNode(id: number) {
    if (!svgEl || !sim) return;
    const node = sim.nodes().find(n => n.id === id);
    if (!node || node.x === undefined || node.y === undefined) return;
    const scale = Math.min(Math.max(currentTransform.k, 0.7), 2.4);
    d3.select(svgEl).transition().duration(450).call(
      zoom.transform as never,
      d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-node.x, -node.y)
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


  onDestroy(() => {
    if (sim) sim.stop();
    cancelAnimationFrame(animationFrame);
  });
</script>

<div class="graph-wrapper" style="width:100%; height:100%; position:relative; min-height: 400px;">
  <canvas bind:this={canvasEl} width={width} height={height} style="position:absolute; top:0; left:0; z-index:1;" />
  <svg bind:this={svgEl} width={width} height={height} style="position:absolute; top:0; left:0; z-index:2; background:transparent;" />

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
        placeholder="Buscar nodos..."
        bind:value={searchQuery}
        on:input={rerender}
      />
      {#if searchQuery.trim().length > 0}
        <button class="search-clear" on:click={clearHighlights} aria-label="Limpiar busqueda">×</button>
      {/if}
    </div>
    <button class="btn btn-ghost btn-icon" title="Alternar etiquetas" on:click={() => { showLabels = !showLabels; rerender(); }}>
      <span style="font-size:10px; font-family: var(--font-mono);">Aa</span>
    </button>
    <button class="btn btn-ghost btn-icon" title="Particulas" class:active={showParticles} on:click={() => { showParticles = !showParticles; }}>
      <span style="font-size:12px;">✨</span>
    </button>
    <button class="btn btn-ghost btn-icon" title="Ajustar" on:click={recenter}>
      <span style="font-size:11px;">⊡</span>
    </button>
    <button class="btn btn-ghost btn-icon" title="Restablecer vista" on:click={resetView}>
      <span style="font-size:11px;">⊙</span>
    </button>
    <button class="btn btn-ghost btn-icon" title="Ocultar huerfanos" class:active={!showOrphans} on:click={() => { showOrphans = !showOrphans; rerender(); }}>
      <span style="font-size:11px;">◌</span>
    </button>
    <div class="filter-group">
      <select bind:value={filterType} on:change={rerender}>
        <option value="all">Todo</option>
        <option value="notes">Notas</option>
        <option value="tags">Tags</option>
      </select>
    </div>
  </div>
</div>

<style>
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
</style>
