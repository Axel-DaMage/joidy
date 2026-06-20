<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { graphData, selectedTag } from '$lib/stores/graph';
  import type { GraphNode, GraphEdge } from '$lib/api';
  import { forceCollide } from 'd3';

  let ForceGraph: typeof import('force-graph') | null = null;

  export let width = 800;
  export let height = 600;
  export let focusId: number | string | null = null;

  let containerEl: HTMLDivElement;
  let graph: ReturnType<typeof import('force-graph')['default']> | null = null;
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
  interface ColorGroup {
    query: string;
    color: string;
  }
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
  let showSettingsPanel = false; // settings panel toggle
  let activeSection: 'filters' | 'groups' | 'display' | 'forces' | null = 'filters'; // active settings section

  // Pre-configured preset colors for Obsidian-style feel
  const COLOR_PRESETS = [
    '#f59e0b', // Amber
    '#10b981', // Emerald
    '#3b82f6', // Blue
    '#ec4899', // Pink
    '#8b5cf6', // Violet
    '#ef4444', // Red
    '#06b6d4', // Cyan
  ];

  const COLORS = {
    tag: '#1d9c73',        // Emerald Green (Obsidian Tag default)
    note: '#8a8a8a',       // Slate Grey (Obsidian Note default)
    unresolved: '#4f3e3e', // Dim crimson/dark grey (Obsidian Unresolved default)
    selected: '#e8a838',   // Golden amber (Obsidian Selected default)
    default: '#666666'
  } as const;

  // Helper function to build neighbor map for smart highlighting
  let neighbors = new Map<number | string, Set<number | string>>();
  $: {
    neighbors.clear();
    const edges = $graphData.edges;
    edges.forEach(edge => {
      const s = typeof edge.source === 'object' ? (edge.source as GraphNode).id : edge.source;
      const t = typeof edge.target === 'object' ? (edge.target as GraphNode).id : edge.target;
      
      if (!neighbors.has(s)) neighbors.set(s, new Set());
      if (!neighbors.has(t)) neighbors.set(t, new Set());
      
      neighbors.get(s)!.add(t);
      neighbors.get(t)!.add(s);
    });
  }

  const getNodeType = (n: GraphNode) => n.type;
  const getNodeLabel = (n: GraphNode) => n.type === 'note' ? (n.title || '') : (n.name || n.title || '');

  // Hex to RGBA helper for semi-transparent fills
  function hexToRgba(hex: string, alpha: number): string {
    const cleanHex = hex.replace('#', '');
    const r = parseInt(cleanHex.substring(0, 2), 16);
    const g = parseInt(cleanHex.substring(2, 4), 16);
    const b = parseInt(cleanHex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  // Lighten Hex color for radial gradient highlights
  function lightenColor(hex: string, percent: number): string {
    const cleanHex = hex.replace('#', '');
    let r = parseInt(cleanHex.substring(0, 2), 16);
    let g = parseInt(cleanHex.substring(2, 4), 16);
    let b = parseInt(cleanHex.substring(4, 6), 16);

    r = Math.min(255, Math.floor(r + (255 - r) * percent));
    g = Math.min(255, Math.floor(g + (255 - g) * percent));
    b = Math.min(255, Math.floor(b + (255 - b) * percent));

    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
  }

  // Obsidian Query parser for dynamic color groups
  function matchesQuery(node: GraphNode, queryStr: string): boolean {
    const q = queryStr.trim().toLowerCase();
    if (!q) return false;

    const label = getNodeLabel(node);
    const labelLower = label.toLowerCase();

    // 1. Tag query: tag:work or tag:#work
    if (q.startsWith('tag:')) {
      const targetTag = q.slice(4).replace(/^#/, '');
      if (node.type === 'tag') {
        return labelLower.replace(/^#/, '') === targetTag;
      }
      if (node.type === 'note' && node.tags) {
        return node.tags.some(t => t.toLowerCase().replace(/^#/, '') === targetTag);
      }
      return false;
    }

    // 2. Path query: path:folder
    if (q.startsWith('path:')) {
      const targetPath = q.slice(5);
      if (node.type === 'note' && node.path) {
        return node.path.toLowerCase().includes(targetPath);
      }
      return false;
    }

    // 3. Title/file query: file:name or title:name
    if (q.startsWith('file:') || q.startsWith('title:')) {
      const targetTitle = q.slice(q.indexOf(':') + 1);
      return labelLower.includes(targetTitle);
    }

    // 4. Default general text search: matches title, tags
    const searchMatch = labelLower.includes(q);
    const tagMatch = node.tags ? node.tags.some(t => t.toLowerCase().includes(q)) : false;
    return searchMatch || tagMatch;
  }

  function addColorGroup() {
    colorGroups = [...colorGroups, { query: '', color: COLOR_PRESETS[colorGroups.length % COLOR_PRESETS.length] }];
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

  function toggleSection(sec: 'filters' | 'groups' | 'display' | 'forces') {
    activeSection = activeSection === sec ? null : sec;
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
    const nodes = $graphData.nodes.slice();
    const edges = $graphData.edges.slice();

    // 1. Filter nodes based on visible types
    let filteredNodes = nodes.filter(n => {
      if (n.type === 'note' && !showNotes) return false;
      if (n.type === 'tag' && !showTags) return false;
      if (n.type === 'unresolved' && !showUnresolved) return false;
      if (n.type === 'attachment' && !showAttachments) return false;
      return true;
    });

    let nodeIds = new Set(filteredNodes.map(n => n.id));
    const getEdgeSourceId = (e: any) => typeof e.source === 'object' ? e.source.id : e.source;
    const getEdgeTargetId = (e: any) => typeof e.target === 'object' ? e.target.id : e.target;

    // 2. Filter edges based on visible nodes and type
    let filteredEdges = edges.filter(e => {
      if (e.type === 'cooccurrence' && !showCooccurrences) return false;
      return nodeIds.has(getEdgeSourceId(e)) && nodeIds.has(getEdgeTargetId(e));
    });

    // 3. Filter orphan nodes if enabled
    if (!showOrphans) {
      const degree = new Map<number | string, number>();
      filteredEdges.forEach((e) => {
        const s = getEdgeSourceId(e);
        const t = getEdgeTargetId(e);
        degree.set(s, (degree.get(s) ?? 0) + 1);
        degree.set(t, (degree.get(t) ?? 0) + 1);
      });
      filteredNodes = filteredNodes.filter(n => (degree.get(n.id) ?? 0) > 0);
      
      const finalNodeIds = new Set(filteredNodes.map(n => n.id));
      filteredEdges = filteredEdges.filter(e => finalNodeIds.has(getEdgeSourceId(e)) && finalNodeIds.has(getEdgeTargetId(e)));
    }

    graph.graphData({ nodes: filteredNodes, links: filteredEdges });
    graph.d3ReheatSimulation();
  }

  function applyStyling() {
    if (!graph) return;
    const focus = hoveredNode?.id ?? $selectedTag;
    const q = searchQuery.trim().toLowerCase();

    graph
      .nodeRelSize(3.2)
      .nodeCanvasObject((node: GraphNode, ctx: CanvasRenderingContext2D, scale: number) => {
        const label = getNodeLabel(node);
        const isNote = node.type === 'note';
        const isTag = node.type === 'tag';
        const isUnresolved = node.type === 'unresolved';

        // Size configuration
        const r = (isTag ? 4.8 : 3.4) * nodeSizeScale;

        // Selection & Hover States
        const isSelected = $selectedTag === node.id;
        const isHovered = hoveredNode?.id === node.id;
        const isFocused = focusId !== null && (node.id === focusId);
        const isNeighborOfFocus = focus !== null && neighbors.get(focus)?.has(node.id);

        // Fading Logic
        const matchesSearch = q ? label.toLowerCase().includes(q) : true;
        const focusDim = focus !== null ? (node.id === focus || isNeighborOfFocus ? 1.0 : 0.15) : 1.0;
        const searchDim = q ? (matchesSearch ? 1.0 : 0.15) : 1.0;
        const alpha = Math.min(focusDim, searchDim);

        ctx.globalAlpha = alpha;

        // Custom Color Queries Evaluation
        let nodeColor = isTag ? COLORS.tag : (isUnresolved ? COLORS.unresolved : COLORS.note);
        for (const group of colorGroups) {
          if (matchesQuery(node, group.query)) {
            nodeColor = group.color;
            break;
          }
        }

        // Draw node shape
        ctx.beginPath();
        if (isUnresolved) {
          // Unresolved nodes draw with a dashed border
          ctx.strokeStyle = nodeColor;
          ctx.lineWidth = 1.2 / scale;
          ctx.setLineDash([2, 2]);
          ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]); // reset dash

          ctx.fillStyle = hexToRgba(nodeColor, 0.15);
          ctx.fill();
        } else {
          // Normal nodes draw with gradient fill
          const gradient = ctx.createRadialGradient(
            node.x - r * 0.3,
            node.y - r * 0.3,
            0,
            node.x,
            node.y,
            r
          );
          gradient.addColorStop(0, lightenColor(nodeColor, 0.25));
          gradient.addColorStop(1, nodeColor);
          ctx.fillStyle = gradient;
          ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
          ctx.fill();
        }

        // Draw hover border
        if (isHovered) {
          ctx.beginPath();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5 / scale;
          ctx.globalAlpha = 0.95 * alpha;
          ctx.arc(node.x, node.y, r + 2 / scale, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Draw selected/focused border
        if (isSelected || isFocused) {
          ctx.beginPath();
          ctx.strokeStyle = COLORS.selected;
          ctx.lineWidth = 2.0 / scale;
          ctx.globalAlpha = 0.95 * alpha;
          ctx.arc(node.x, node.y, r + 3 / scale, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Draw label text
        const showThisLabel = showLabels && (scale >= labelThreshold || isHovered || isSelected || isNeighborOfFocus);
        if (showThisLabel && label) {
          const fontSize = (10 * textScale) / scale;
          ctx.font = `${fontSize}px var(--font-sans, system-ui, -apple-system, sans-serif)`;
          ctx.fillStyle = (hoveredNode?.id === node.id || $selectedTag === node.id) ? '#ffffff' : 'rgba(215, 215, 215, 0.8)';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.globalAlpha = alpha;

          const labelText = label.length > 28 ? label.slice(0, 26) + '...' : label;
          ctx.fillText(labelText, node.x, node.y + r + 6 / scale);
        }
      })
      .linkWidth((l: GraphEdge) => {
        let baseWidth = l.type === 'hierarchy' ? 1.5 : 0.8;
        if (l.weight) {
          baseWidth *= Math.sqrt(l.weight);
        }
        baseWidth *= linkThicknessScale;
        
        if (focus === null) return baseWidth;
        
        const sourceId = typeof l.source === 'object' ? (l.source as any).id : l.source;
        const targetId = typeof l.target === 'object' ? (l.target as any).id : l.target;
        return (sourceId === focus || targetId === focus) ? baseWidth * 1.5 : baseWidth * 0.2;
      })
      .linkColor((l: GraphEdge) => {
        const sourceId = typeof l.source === 'object' ? (l.source as any).id : l.source;
        const targetId = typeof l.target === 'object' ? (l.target as any).id : l.target;

        // Hover highlighting of links
        let color = '#383838'; // very subtle dark grey in dark mode
        if (l.type === 'hierarchy') color = '#525252';
        else if (l.type === 'cooccurrence') color = '#2c2c2c';
        else if (l.type === 'linked') color = '#404040';
        else if (l.type === 'tagged') color = '#4a4a4a';

        if (focus === null) return color;

        if (sourceId === focus || targetId === focus) {
          // Highlight color based on type
          if (l.type === 'hierarchy') return '#888888';
          if (l.type === 'linked') return '#3b82f6'; // Bright Blue
          if (l.type === 'tagged') return '#8b5cf6'; // Bright Purple
          if (l.type === 'cooccurrence') return '#6b7280';
          return COLORS.selected;
        }

        return '#1b1b1b'; // dim non-connected lines
      })
      .linkLineDash((l: GraphEdge) => l.type === 'cooccurrence' ? [3, 3] : []);
  }

  function focusOnNode(id: number | string) {
    if (!graph) return;
    const node = graph.graphData().nodes.find((n: GraphNode) => n.id === id) as GraphNode | undefined;
    if (!node) return;
    graph.centerAt(node.x, node.y, 400);
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
        { query: 'tag:idea', color: '#10b981' }
      ];
    }

    const module = await import('force-graph');
    ForceGraph = module.default;
    graph = ForceGraph()(containerEl)
      .width(width)
      .height(height)
      .backgroundColor('transparent')
      .enableNodeDrag(true)
      .onNodeClick(handleNodeClick)
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
      graph.d3Force('collide', forceCollide((node: any) => {
        const isTag = node.type === 'tag';
        const r = isTag ? 4.8 : 3.4;
        return r + 8; // radius + padding for collision physics
      }));
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
    <div class="graph-loading">Cargando grafo de conocimiento...</div>
  {/if}
  
  <div bind:this={containerEl} class="graph-canvas"></div>

  {#if loaded}
    <!-- GEAR / TOGGLE PANEL FLOATING BUTTON -->
    <button 
      class="settings-toggle-btn" 
      class:panel-open={showSettingsPanel} 
      title="Ajustes del Grafo" 
      on:click={() => showSettingsPanel = !showSettingsPanel}
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="gear-icon"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
    </button>

    <!-- OBSIDIAN STYLE COLLAPSIBLE FLOATING SIDEBAR PANEL -->
    <div class="settings-sidebar" class:open={showSettingsPanel}>
      <div class="sidebar-header">
        <h4>Ajustes del Grafo</h4>
        <button class="close-panel-btn" on:click={() => showSettingsPanel = false}>×</button>
      </div>

      <div class="sidebar-scroll">
        <!-- 1. FILTROS -->
        <div class="accordion-item" class:active={activeSection === 'filters'}>
          <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
          <div class="accordion-header" on:click={() => toggleSection('filters')}>
            <span class="chevron" class:expanded={activeSection === 'filters'}>›</span>
            <h5>Filtros</h5>
          </div>
          {#if activeSection === 'filters'}
            <div class="accordion-content">
              <div class="filter-search-wrap">
                <input
                  class="panel-search"
                  type="text"
                  placeholder="Buscar notas o tags..."
                  bind:value={searchQuery}
                  on:input={applyStyling}
                />
                {#if searchQuery}
                  <button class="panel-search-clear" on:click={() => { searchQuery = ''; applyStyling(); }}>×</button>
                {/if}
              </div>

              <label class="toggle-control">
                <span>Archivos</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showNotes} on:change={rebuildGraph} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Etiquetas</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showTags} on:change={rebuildGraph} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Archivos no existentes</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showUnresolved} on:change={rebuildGraph} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Adjuntos</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showAttachments} on:change={rebuildGraph} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Huérfanos</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showOrphans} on:change={rebuildGraph} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Co-ocurrencias de etiquetas</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showCooccurrences} on:change={rebuildGraph} />
                  <span class="slider"></span>
                </span>
              </label>
            </div>
          {/if}
        </div>

        <!-- 2. GRUPOS DE COLOR -->
        <div class="accordion-item" class:active={activeSection === 'groups'}>
          <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
          <div class="accordion-header" on:click={() => toggleSection('groups')}>
            <span class="chevron" class:expanded={activeSection === 'groups'}>›</span>
            <h5>Grupos de color</h5>
          </div>
          {#if activeSection === 'groups'}
            <div class="accordion-content">
              <p class="section-desc">Pinta nodos según consultas (ej. <code>tag:idea</code>, <code>title:nota</code>)</p>
              
              <div class="groups-list">
                {#each colorGroups as group, idx}
                  <div class="group-row">
                    <input 
                      type="color" 
                      class="color-picker-input" 
                      bind:value={group.color} 
                      on:change={saveGroups} 
                    />
                    <input 
                      type="text" 
                      class="group-query-input" 
                      placeholder="tag:idea o palabra clave..." 
                      bind:value={group.query} 
                      on:input={saveGroups} 
                    />
                    <button class="group-delete-btn" title="Eliminar regla" on:click={() => removeColorGroup(idx)}>×</button>
                  </div>
                {/each}
              </div>

              <button class="btn btn-ghost add-group-btn" on:click={addColorGroup}>
                + Añadir grupo
              </button>
            </div>
          {/if}
        </div>

        <!-- 3. VISUALIZACIÓN -->
        <div class="accordion-item" class:active={activeSection === 'display'}>
          <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
          <div class="accordion-header" on:click={() => toggleSection('display')}>
            <span class="chevron" class:expanded={activeSection === 'display'}>›</span>
            <h5>Visualización</h5>
          </div>
          {#if activeSection === 'display'}
            <div class="accordion-content">
              <label class="toggle-control">
                <span>Mostrar etiquetas de texto</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showLabels} on:change={applyStyling} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Flechas de dirección</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={showArrows} />
                  <span class="slider"></span>
                </span>
              </label>

              <label class="toggle-control">
                <span>Evitar solapamiento de nodos</span>
                <span class="switch">
                  <input type="checkbox" bind:checked={enableCollision} />
                  <span class="slider"></span>
                </span>
              </label>

              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Tamaño del nodo</span>
                  <span>{nodeSizeScale.toFixed(1)}x</span>
                </div>
                <input type="range" min="0.5" max="3.0" step="0.1" bind:value={nodeSizeScale} on:input={applyStyling} />
              </div>

              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Grosor de línea</span>
                  <span>{linkThicknessScale.toFixed(1)}x</span>
                </div>
                <input type="range" min="0.1" max="3.0" step="0.1" bind:value={linkThicknessScale} on:input={applyStyling} />
              </div>

              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Escala del texto</span>
                  <span>{textScale.toFixed(1)}x</span>
                </div>
                <input type="range" min="0.5" max="2.0" step="0.1" bind:value={textScale} on:input={applyStyling} />
              </div>

              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Umbral de desvanecimiento</span>
                  <span>{labelThreshold.toFixed(1)}</span>
                </div>
                <input type="range" min="0.2" max="2.5" step="0.1" bind:value={labelThreshold} on:input={applyStyling} />
              </div>
            </div>
          {/if}
        </div>

        <!-- 4. FUERZAS FÍSICAS -->
        <div class="accordion-item" class:active={activeSection === 'forces'}>
          <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
          <div class="accordion-header" on:click={() => toggleSection('forces')}>
            <span class="chevron" class:expanded={activeSection === 'forces'}>›</span>
            <h5>Fuerzas</h5>
          </div>
          {#if activeSection === 'forces'}
            <div class="accordion-content">
              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Repulsión (Fuerza de carga)</span>
                  <span>{repelForce}</span>
                </div>
                <input type="range" min="30" max="600" step="10" bind:value={repelForce} />
              </div>

              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Distancia de enlace</span>
                  <span>{linkDistance}px</span>
                </div>
                <input type="range" min="15" max="180" step="5" bind:value={linkDistance} />
              </div>

              <div class="slider-control">
                <div class="slider-lbl">
                  <span>Atracción de enlace</span>
                  <span>{linkForce.toFixed(1)}</span>
                </div>
                <input type="range" min="0.1" max="2.0" step="0.1" bind:value={linkForce} />
              </div>

              <button class="btn btn-ghost reset-btn" on:click={resetForces}>
                Reestablecer fuerzas predeterminadas
              </button>
            </div>
          {/if}
        </div>
      </div>
    </div>

    <!-- PERSISTENT RIGHT TOOLBAR CONTROLS (FIT AND ZOOM VIEWS) -->
    <div class="graph-quick-actions">
      <button class="quick-btn" title="Ajustar grafo a pantalla" on:click={zoomToFit}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="action-icon"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="9" x2="15" y2="15"></line><line x1="15" y1="9" x2="9" y2="15"></line></svg>
      </button>
      <button class="quick-btn" title="Centrar grafo" on:click={resetView}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="action-icon"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="3"></circle></svg>
      </button>
      <button class="quick-btn" title="Limpiar selecciones y filtros" on:click={clearHighlights}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="action-icon"><path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"></path><line x1="18" y1="9" x2="12" y2="15"></line><line x1="12" y1="9" x2="18" y2="15"></line></svg>
      </button>
    </div>
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
    z-index: 10;
    font-family: var(--font-mono, monospace);
  }

  /* SETTINGS PANEL FLOATING TOGGLE BUTTON */
  .settings-toggle-btn {
    position: absolute;
    top: 16px;
    left: 16px;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--elevated) 85%, transparent);
    border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 1010;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    backdrop-filter: blur(12px);
    transition: all 0.25s ease;
  }

  .settings-toggle-btn:hover {
    color: var(--accent);
    background: var(--elevated);
    border-color: var(--accent);
  }

  .settings-toggle-btn.panel-open {
    left: 352px; /* move to the right of panel */
    color: var(--accent);
  }

  .gear-icon {
    width: 18px;
    height: 18px;
    transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .settings-toggle-btn:hover .gear-icon,
  .settings-toggle-btn.panel-open .gear-icon {
    transform: rotate(45deg);
  }

  /* COLLAPSIBLE FLOATING SIDEBAR (GLASSMORPHISM) */
  .settings-sidebar {
    position: absolute;
    top: 16px;
    left: -336px; /* hide left initially */
    bottom: 16px;
    width: 320px;
    border-radius: 12px;
    background: rgba(20, 20, 20, 0.76);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(20px);
    z-index: 1005;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: left 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .settings-sidebar.open {
    left: 16px;
  }

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
  }

  .sidebar-header h4 {
    font-size: 13px;
    font-weight: 500;
    color: #e5e5e5;
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .close-panel-btn {
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 20px;
    cursor: pointer;
    line-height: 1;
    padding: 0;
    transition: color 0.15s ease;
  }

  .close-panel-btn:hover {
    color: #ffffff;
  }

  .sidebar-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  /* ACCORDION MODULES */
  .accordion-item {
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
    overflow: hidden;
    transition: all 0.2s ease;
  }

  .accordion-item.active {
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(255, 255, 255, 0.08);
  }

  .accordion-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    cursor: pointer;
    user-select: none;
  }

  .accordion-header h5 {
    font-size: 12px;
    font-weight: 500;
    color: #dfdfdf;
    margin: 0;
  }

  .chevron {
    color: rgba(255, 255, 255, 0.35);
    font-size: 14px;
    font-weight: bold;
    display: inline-block;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .chevron.expanded {
    transform: rotate(90deg);
    color: var(--accent);
  }

  .accordion-content {
    padding: 4px 12px 12px 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.03);
    animation: slideDown 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }

  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .section-desc {
    font-size: 10px;
    color: rgba(255, 255, 255, 0.4);
    margin: 0 0 4px 0;
    line-height: 1.3;
  }

  /* FILTERS & TOGGLES STYLE */
  .filter-search-wrap {
    position: relative;
    margin-bottom: 4px;
  }

  .panel-search {
    width: 100%;
    padding: 6px 26px 6px 8px;
    font-size: 11px;
    background: rgba(0, 0, 0, 0.35);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    outline: none;
    transition: border-color 0.15s ease;
  }

  .panel-search:focus {
    border-color: var(--accent);
  }

  .panel-search-clear {
    position: absolute;
    top: 50%;
    right: 8px;
    transform: translateY(-50%);
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 14px;
    cursor: pointer;
    padding: 0;
  }

  .toggle-control {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    font-size: 11px;
    color: #c7c7c7;
    user-select: none;
    padding: 3px 0;
  }

  .toggle-control span {
    transition: color 0.15s ease;
  }

  .toggle-control:hover span {
    color: #ffffff;
  }

  /* Premium iOS-style Switches */
  .switch {
    position: relative;
    display: inline-block;
    width: 28px;
    height: 16px;
    flex-shrink: 0;
  }

  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(255, 255, 255, 0.12);
    transition: .2s;
    border-radius: 16px;
    border: 1.5px solid rgba(255, 255, 255, 0.08);
  }

  .slider:before {
    position: absolute;
    content: "";
    height: 10px;
    width: 10px;
    left: 2px;
    bottom: 1.5px;
    background-color: #ffffff;
    transition: .2s;
    border-radius: 50%;
  }

  input:checked + .slider {
    background-color: var(--accent, #1d9c73);
    border-color: var(--accent, #1d9c73);
  }

  input:checked + .slider:before {
    transform: translateX(12px);
  }

  /* COLOR GROUPS STYLE */
  .groups-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 140px;
    overflow-y: auto;
    padding-right: 2px;
  }

  .group-row {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 0, 0, 0.2);
    padding: 4px 6px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.03);
  }

  .color-picker-input {
    -webkit-appearance: none;
    -moz-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    background: transparent;
    padding: 0;
    flex-shrink: 0;
  }

  .color-picker-input::-webkit-color-swatch-wrapper {
    padding: 0;
  }

  .color-picker-input::-webkit-color-swatch {
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 50%;
  }

  .group-query-input {
    flex: 1;
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: 11px;
    outline: none;
    padding: 2px 0;
  }

  .group-query-input::placeholder {
    color: rgba(255, 255, 255, 0.3);
  }

  .group-delete-btn {
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.4);
    font-size: 15px;
    cursor: pointer;
    padding: 0 4px;
    transition: color 0.15s ease;
  }

  .group-delete-btn:hover {
    color: #ff5555;
  }

  .add-group-btn {
    font-size: 10px;
    padding: 6px;
    width: 100%;
    text-align: center;
    border: 1px dashed rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.6);
    border-radius: 6px;
    transition: all 0.15s ease;
  }

  .add-group-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(255, 255, 255, 0.02);
  }

  /* SLIDERS STYLE */
  .slider-control {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .slider-lbl {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #b7b7b7;
  }

  .slider-lbl span:last-child {
    font-family: var(--font-mono, monospace);
    color: rgba(255, 255, 255, 0.4);
  }

  .slider-control input[type="range"] {
    width: 100%;
    height: 3px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 2px;
    outline: none;
    accent-color: var(--accent);
  }

  .reset-btn {
    font-size: 10px;
    padding: 8px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .reset-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
  }

  /* PERSISTENT FLOATING QUICK ACTIONS (FIT / CENTERING) */
  .graph-quick-actions {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    z-index: 1000;
    background: color-mix(in srgb, var(--elevated) 90%, transparent);
    padding: 8px;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(12px);
  }

  .quick-btn {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .quick-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    color: var(--accent);
  }

  .action-icon {
    width: 15px;
    height: 15px;
  }

  /* Global buttons adjustments inside the widget */
  .btn-ghost {
    background: transparent;
    border: none;
    cursor: pointer;
  }
</style>
