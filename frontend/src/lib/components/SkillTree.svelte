<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as d3 from 'd3';
  import type { SkillTree, SkillNode } from '$lib/api';
  import { Star, Hash, Zap, Shield, Sparkles } from 'lucide-svelte';

  export let data: SkillTree = { nodes: [], edges: [] };
  export let width = 800;
  export let height = 600;

  let svgEl: SVGSVGElement;
  let simulation: d3.Simulation<any, undefined>;
  let tooltip = { visible: false, x: 0, y: 0, node: null as SkillNode | null };

  const COLORS = {
    locked: '#333333',
    apprentice: '#4ade80', // Emerald
    journeyman: '#3b82f6', // Blue
    expert: '#a855f7',     // Purple
    master: '#f59e0b',     // Amber
  };

  const GLOWS = {
    locked: 'none',
    apprentice: '0 0 10px rgba(74, 222, 128, 0.4)',
    journeyman: '0 0 15px rgba(59, 130, 246, 0.5)',
    expert: '0 0 20px rgba(168, 85, 247, 0.6)',
    master: '0 0 30px rgba(245, 158, 11, 0.8)',
  };

  function render() {
    if (!svgEl || data.nodes.length === 0) return;
    
    // Clear previous
    d3.select(svgEl).selectAll('*').remove();
    if (simulation) simulation.stop();

    const svg = d3.select(svgEl);
    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on('zoom', (e) => g.attr('transform', e.transform));
    svg.call(zoom);

    // Filters for glow
    const defs = svg.append('defs');
    Object.entries(COLORS).forEach(([id, color]) => {
      const filter = defs.append('filter').attr('id', `glow-${id}`).attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
      filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur');
      filter.append('feComposite').attr('in', 'SourceGraphic').attr('in2', 'blur').attr('operator', 'over');
    });

    const nodes = data.nodes.map(d => ({ ...d }));
    const links = data.edges.map(d => ({
      source: nodes.find(n => n.id === (typeof d.source === 'number' ? d.source : (d.source as any).id)),
      target: nodes.find(n => n.id === (typeof d.target === 'number' ? d.target : (d.target as any).id)),
    })).filter(l => l.source && l.target);

    simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(100).strength(0.5))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    // Links (Pulse animation)
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.4);

    // Nodes
    const node = g.append('g')
      .selectAll('g')
      .data(nodes, (d: any) => d.id) // STABLE ID JOIN
      .join('g')
      .style('cursor', 'pointer')
      .on('mouseover', (e, d: any) => {
        tooltip = { visible: true, x: e.pageX, y: e.pageY, node: d };
      })
      .on('mouseout', () => tooltip.visible = false)
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended) as any
      );

    // Node outer circle (Glow)
    node.append('circle')
      .attr('r', d => nodeSize(d.level) + 4)
      .attr('fill', 'none')
      .attr('stroke', d => (COLORS as any)[d.level])
      .attr('stroke-width', 2)
      .style('filter', d => `url(#glow-${d.level})`)
      .style('opacity', d => d.level === 'locked' ? 0.2 : 0.6);

    // Node inner circle
    node.append('circle')
      .attr('r', d => nodeSize(d.level))
      .attr('fill', 'var(--bg)')
      .attr('stroke', d => (COLORS as any)[d.level])
      .attr('stroke-width', 2);

    // Labels
    node.append('text')
      .attr('dy', d => nodeSize(d.level) + 16)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('font-family', 'var(--font-mono)')
      .attr('fill', 'var(--text-primary)')
      .text(d => d.name.toUpperCase());

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }
    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }
    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }
  }

  function nodeSize(level: string): number {
    return { locked: 8, apprentice: 12, journeyman: 14, expert: 18, master: 22 }[level] ?? 12;
  }

  $: data && svgEl && render();
  
  onMount(() => {
    width = svgEl.clientWidth;
    height = svgEl.clientHeight;
    render();
    window.addEventListener('resize', handleResize);
  });

  onDestroy(() => {
    simulation?.stop();
    window.removeEventListener('resize', handleResize);
  });

  function handleResize() {
    width = svgEl.clientWidth;
    height = svgEl.clientHeight;
    render();
  }
</script>

<div class="skill-tree-container">
  <svg bind:this={svgEl} />

  {#if tooltip.visible && tooltip.node}
    <div class="skill-tooltip" style="left: {tooltip.x + 15}px; top: {tooltip.y - 15}px;">
      <div class="tooltip-header">
        <span class="level-tag" style="background: {COLORS[tooltip.node.level as keyof typeof COLORS]}">
          {tooltip.node.level.toUpperCase()}
        </span>
        <h4>{tooltip.node.name}</h4>
      </div>
      <div class="tooltip-body">
        <div class="stat"><Zap size={10}/> {tooltip.node.note_count} Notas</div>
        <div class="stat"><Sparkles size={10}/> {tooltip.node.xp} XP acumulada</div>
        {#if tooltip.node.level === 'locked'}
          <p class="req">Requiere {3 - tooltip.node.note_count} notas más para desbloquear</p>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .skill-tree-container {
    width: 100%;
    height: 100%;
    position: relative;
    background: radial-gradient(circle at center, #1a1a1a 0%, #0a0a0a 100%);
    border-radius: var(--r-xl);
    overflow: hidden;
    border: 1px solid var(--border);
  }

  svg { width: 100%; height: 100%; }

  .skill-tooltip {
    position: fixed;
    z-index: 1000;
    width: 180px;
    background: rgba(15, 15, 15, 0.95);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 12px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    pointer-events: none;
    animation: fade-in 0.15s ease-out;
  }

  .tooltip-header { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
  .level-tag { font-size: 8px; font-family: var(--font-mono); color: #000; padding: 1px 4px; border-radius: 2px; width: fit-content; font-weight: bold; }
  h4 { margin: 0; font-size: 14px; color: var(--text-primary); }

  .tooltip-body { display: flex; flex-direction: column; gap: 4px; }
  .stat { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-secondary); font-family: var(--font-mono); }
  .req { margin-top: 8px; font-size: 10px; color: var(--accent); font-style: italic; }

  @keyframes fade-in {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>

