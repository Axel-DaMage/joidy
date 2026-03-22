<script lang="ts">
  import { onMount } from 'svelte';
  import * as d3 from 'd3';
  import type { SkillTree } from '$lib/api';

  export let data: SkillTree = { nodes: [], edges: [] };

  let svgEl: SVGSVGElement;
  let width = 700;
  let height = 500;

  const LEVEL_ORDER = ['locked', 'apprentice', 'journeyman', 'expert', 'master'];
  const LEVEL_LABELS: Record<string, string> = {
    locked: 'bloqueado',
    apprentice: 'aprendiz',
    journeyman: 'oficial',
    expert: 'experto',
    master: 'maestro',
  };

  function render() {
    if (!svgEl || data.nodes.length === 0) return;
    d3.select(svgEl).selectAll('*').remove();

    const svg = d3.select(svgEl);
    const g = svg.append('g').attr('transform', `translate(${width / 2}, 40)`);

    // Build D3 hierarchy
    const nodeMap = new Map(data.nodes.map(n => [n.id, { ...n, children: [] as typeof n[] }]));
    const roots: typeof data.nodes[0][] = [];

    data.edges.forEach(e => {
      const src = nodeMap.get(typeof e.source === 'number' ? e.source : (e.source as {id:number}).id);
      const tgt = nodeMap.get(typeof e.target === 'number' ? e.target : (e.target as {id:number}).id);
      if (src && tgt) (src as {children: typeof data.nodes[0][]}).children.push(tgt as typeof data.nodes[0]);
    });

    nodeMap.forEach((n, id) => {
      const hasParent = data.edges.some(e => {
        const tgtId = typeof e.target === 'number' ? e.target : (e.target as {id:number}).id;
        return tgtId === id;
      });
      if (!hasParent) roots.push(n as typeof data.nodes[0]);
    });

    if (roots.length === 0) return;

    const rootData = roots.length === 1 ? roots[0] : { id: -1, name: 'Skills', level: 'master', note_count: 0, xp: 0, children: roots };
    const root = d3.hierarchy(rootData);
    const treeLayout = d3.tree().size([width - 80, height - 100]);
    treeLayout(root as d3.HierarchyNode<typeof rootData>);

    // Links
    g.append('g')
      .selectAll('path')
      .data(root.links())
      .join('path')
      .attr('d', d3.linkVertical<d3.HierarchyPointLink<typeof rootData>, d3.HierarchyPointNode<typeof rootData>>()
        .x(d => d.x - width / 2)
        .y(d => d.y)
      )
      .attr('fill', 'none')
      .attr('stroke', 'var(--border)')
      .attr('stroke-width', 1);

    // Nodes
    const node = g.append('g')
      .selectAll('g')
      .data(root.descendants())
      .join('g')
      .attr('transform', d => `translate(${(d as d3.HierarchyPointNode<typeof rootData>).x - width / 2},${(d as d3.HierarchyPointNode<typeof rootData>).y})`);

    node.append('circle')
      .attr('r', d => nodeR(d.data.level))
      .attr('fill', 'var(--elevated)')
      .attr('stroke', d => nodeStroke(d.data.level))
      .attr('stroke-width', d => d.data.level === 'master' ? 1.5 : 1)
      .attr('stroke-dasharray', d => d.data.level === 'locked' ? '3 3' : null)
      .attr('opacity', d => d.data.level === 'locked' ? 0.3 : 1);

    node.append('text')
      .attr('dy', -12)
      .attr('text-anchor', 'middle')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '9px')
      .attr('fill', d => d.data.level === 'locked' ? 'var(--text-muted)' : 'var(--text-primary)')
      .attr('opacity', d => d.data.level === 'locked' ? 0.4 : 1)
      .text(d => d.data.id === -1 ? '' : d.data.name);

    node.append('text')
      .attr('dy', 18)
      .attr('text-anchor', 'middle')
      .attr('font-family', 'var(--font-mono)')
      .attr('font-size', '7px')
      .attr('fill', 'var(--text-muted)')
      .attr('letter-spacing', '0.06em')
      .text(d => d.data.id === -1 ? '' : LEVEL_LABELS[d.data.level]?.toUpperCase() ?? '');
  }

  function nodeR(level: string): number {
    return { locked: 4, apprentice: 6, journeyman: 7, expert: 9, master: 11 }[level] ?? 6;
  }

  function nodeStroke(level: string): string {
    return { locked: 'var(--text-muted)', apprentice: 'var(--border)', journeyman: 'var(--text-secondary)', expert: 'var(--accent)', master: 'var(--text-primary)' }[level] ?? 'var(--border)';
  }

  $: data, render();
  onMount(render);
</script>

<svg bind:this={svgEl} {width} {height} style="overflow:visible;" />
