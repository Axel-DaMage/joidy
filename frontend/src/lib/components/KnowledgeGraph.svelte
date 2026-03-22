<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as d3 from 'd3';
  import { graphData, selectedTag } from '$lib/stores/graph';
  import type { GraphNode, GraphEdge } from '$lib/api';

  export let width = 800;
  export let height = 600;

  let svgEl: SVGSVGElement;
  let tooltip = { visible: false, x: 0, y: 0, text: '' };
  let showLabels = true;

  interface SimNode extends GraphNode { x?: number; y?: number; fx?: number | null; fy?: number | null; }

  function render(nodes: GraphNode[], edges: GraphEdge[]) {
    if (!svgEl || nodes.length === 0) return;
    d3.select(svgEl).selectAll('*').remove();

    const svg = d3.select(svgEl);
    const g = svg.append('g');

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => g.attr('transform', event.transform.toString()));
    svg.call(zoom);

    // Simulation
    const simNodes: SimNode[] = nodes.map(n => ({ ...n }));
    const nodeMap = new Map(simNodes.map(n => [n.id, n]));

    const simLinks = edges.map(e => ({
      source: nodeMap.get(typeof e.source === 'number' ? e.source : (e.source as SimNode).id) as SimNode,
      target: nodeMap.get(typeof e.target === 'number' ? e.target : (e.target as SimNode).id) as SimNode,
      type: e.type,
      weight: e.weight ?? 1,
    })).filter(l => l.source && l.target);

    const simulation = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink(simLinks).id((d: SimNode) => d.id).distance(80).strength(0.4))
      .force('charge', d3.forceManyBody().strength(-200).theta(0.9))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: SimNode) => nodeRadius(d) + 8));

    // Edges
    const link = g.append('g').attr('class', 'links')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', d => d.type === 'hierarchy' ? 1 : 0.6)
      .attr('stroke-dasharray', d => d.type === 'cooccurrence' ? '3 3' : null)
      .attr('opacity', 0.6);

    // Nodes
    const node = g.append('g').attr('class', 'nodes')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
      )
      .on('click', (event, d) => {
        event.stopPropagation();
        selectedTag.update(t => t === d.id ? null : d.id);
      })
      .on('mouseover', (event, d) => {
        tooltip = { visible: true, x: event.pageX + 10, y: event.pageY - 10, text: `${d.name} · ${d.note_count} notas` };
      })
      .on('mouseout', () => { tooltip = { ...tooltip, visible: false }; });

    node.append('circle')
      .attr('r', (d: SimNode) => nodeRadius(d))
      .attr('fill', 'var(--elevated)')
      .attr('stroke', (d: SimNode) => d.id === $selectedTag ? 'var(--text-primary)' : 'var(--border)')
      .attr('stroke-width', (d: SimNode) => d.id === $selectedTag ? 1.5 : 1);

    if (showLabels) {
      node.append('text')
        .attr('dy', (d: SimNode) => nodeRadius(d) + 12)
        .attr('text-anchor', 'middle')
        .attr('font-family', 'var(--font-mono)')
        .attr('font-size', '9px')
        .attr('fill', 'var(--text-secondary)')
        .attr('pointer-events', 'none')
        .text((d: SimNode) => d.name);
    }

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x ?? 0)
        .attr('y1', d => (d.source as SimNode).y ?? 0)
        .attr('x2', d => (d.target as SimNode).x ?? 0)
        .attr('y2', d => (d.target as SimNode).y ?? 0);

      node.attr('transform', (d: SimNode) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return simulation;
  }

  function nodeRadius(d: GraphNode): number {
    return Math.max(4, Math.min(16, 4 + d.note_count * 1.5));
  }

  let sim: d3.Simulation<SimNode, undefined> | undefined;

  $: if (svgEl && $graphData) {
    sim?.stop();
    sim = render($graphData.nodes, $graphData.edges) as d3.Simulation<SimNode, undefined> | undefined;
  }

  onDestroy(() => sim?.stop());
</script>

<div class="graph-wrapper" style="width:{width}px; height:{height}px; position:relative;">
  <svg bind:this={svgEl} {width} {height} style="background: var(--bg);" />

  {#if tooltip.visible}
    <div
      class="tooltip"
      style="position:fixed; left:{tooltip.x}px; top:{tooltip.y}px;"
    >
      {tooltip.text}
    </div>
  {/if}

  <div class="graph-controls">
    <button class="btn btn-ghost btn-icon" title="Toggle labels" on:click={() => { showLabels = !showLabels; sim?.stop(); sim = render($graphData.nodes, $graphData.edges) as d3.Simulation<SimNode, undefined> | undefined; }}>
      <span style="font-size:10px; font-family: var(--font-mono);">Aa</span>
    </button>
    <button class="btn btn-ghost btn-icon" title="Reset view" on:click={() => { d3.select(svgEl).transition().call(d3.zoom<SVGSVGElement, unknown>().transform as never, d3.zoomIdentity); }}>
      <span style="font-size:11px;">⊙</span>
    </button>
  </div>
</div>

<style>
  .tooltip {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-primary);
    pointer-events: none;
    z-index: 100;
    white-space: nowrap;
  }

  .graph-controls {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
</style>
