import type { GraphNode, GraphEdge } from '$lib/api';
import type { NodeObject } from 'force-graph';
import {
  COLORS,
  getNodeLabel,
  hexToRgba,
  lightenColor,
  matchesQuery,
  type ColorGroup,
} from './graphUtils';

// GraphNode extended with force-graph runtime properties (x, y added by the simulation)
type ForceGraphNode = GraphNode & NodeObject;

export interface GraphStylingContext {
  hoveredNode: GraphNode | null;
  selectedTag: number | string | null;
  searchQuery: string;
  focusId: number | string | null;
  neighbors: Map<number | string, Set<number | string>>;
  nodeSizeScale: number;
  linkThicknessScale: number;
  showLabels: boolean;
  textScale: number;
  labelThreshold: number;
  colorGroups: ColorGroup[];
}

export function applyGraphStyling(graph: any, ctx: GraphStylingContext) {
  if (!graph) return;
  const {
    hoveredNode,
    selectedTag,
    searchQuery,
    focusId,
    neighbors,
    nodeSizeScale,
    linkThicknessScale,
    showLabels,
    textScale,
    labelThreshold,
    colorGroups,
  } = ctx;
  const focus = hoveredNode?.id ?? selectedTag;
  const q = searchQuery.trim().toLowerCase();

  graph
    .nodeRelSize(3.2)
    .nodeCanvasObject((node: ForceGraphNode, ctx2: CanvasRenderingContext2D, scale: number) => {
      const x = node.x;
      const y = node.y;
      if (x === undefined || y === undefined || !Number.isFinite(x) || !Number.isFinite(y)) return;
      const label = getNodeLabel(node);
      const isTag = node.type === 'tag';
      const isUnresolved = node.type === 'unresolved';

      // Size configuration
      const r = (isTag ? 4.8 : 3.4) * nodeSizeScale;

      // Selection & Hover States
      const isSelected = selectedTag === node.id;
      const isHovered = hoveredNode?.id === node.id;
      const isFocused = focusId !== null && node.id === focusId;
      const isNeighborOfFocus = focus !== null && neighbors.get(focus)?.has(node.id);

      // Fading Logic
      const matchesSearch = q ? label.toLowerCase().includes(q) : true;
      const focusDim = focus !== null ? (node.id === focus || isNeighborOfFocus ? 1.0 : 0.15) : 1.0;
      const searchDim = q ? (matchesSearch ? 1.0 : 0.15) : 1.0;
      const alpha = Math.min(focusDim, searchDim);

      ctx2.globalAlpha = alpha;

      // Custom Color Queries Evaluation
      let nodeColor: string = isTag ? COLORS.tag : isUnresolved ? COLORS.unresolved : COLORS.note;
      for (const group of colorGroups) {
        if (matchesQuery(node, group.query)) {
          nodeColor = group.color;
          break;
        }
      }

      // Draw node shape
      ctx2.beginPath();
      if (isUnresolved) {
        // Unresolved nodes draw with a dashed border
        ctx2.strokeStyle = nodeColor;
        ctx2.lineWidth = 1.2 / scale;
        ctx2.setLineDash([2, 2]);
        ctx2.arc(x, y, r, 0, Math.PI * 2);
        ctx2.stroke();
        ctx2.setLineDash([]); // reset dash

        ctx2.fillStyle = hexToRgba(nodeColor, 0.15);
        ctx2.fill();
      } else {
        // Normal nodes draw with gradient fill
        const gradient = ctx2.createRadialGradient(x - r * 0.3, y - r * 0.3, 0, x, y, r);
        gradient.addColorStop(0, lightenColor(nodeColor, 0.25));
        gradient.addColorStop(1, nodeColor);
        ctx2.fillStyle = gradient;
        ctx2.arc(x, y, r, 0, Math.PI * 2);
        ctx2.fill();
      }

      // Draw hover border
      if (isHovered) {
        ctx2.beginPath();
        ctx2.strokeStyle = '#ffffff';
        ctx2.lineWidth = 1.5 / scale;
        ctx2.globalAlpha = 0.95 * alpha;
        ctx2.arc(x, y, r + 2 / scale, 0, Math.PI * 2);
        ctx2.stroke();
      }

      // Draw selected/focused border
      if (isSelected || isFocused) {
        ctx2.beginPath();
        ctx2.strokeStyle = COLORS.selected;
        ctx2.lineWidth = 2.0 / scale;
        ctx2.globalAlpha = 0.95 * alpha;
        ctx2.arc(x, y, r + 3 / scale, 0, Math.PI * 2);
        ctx2.stroke();
      }

      // Draw label text
      const showThisLabel =
        showLabels && (scale >= labelThreshold || isHovered || isSelected || isNeighborOfFocus);
      if (showThisLabel && label) {
        const fontSize = (10 * textScale) / scale;
        ctx2.font = `${fontSize}px var(--font-sans, system-ui, -apple-system, sans-serif)`;
        ctx2.fillStyle =
          hoveredNode?.id === node.id || selectedTag === node.id
            ? '#ffffff'
            : 'rgba(215, 215, 215, 0.8)';
        ctx2.textAlign = 'center';
        ctx2.textBaseline = 'top';
        ctx2.globalAlpha = alpha;

        const labelText = label.length > 28 ? label.slice(0, 26) + '...' : label;
        ctx2.fillText(labelText, x, y + r + 6 / scale);
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
      return sourceId === focus || targetId === focus ? baseWidth * 1.5 : baseWidth * 0.2;
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
    .linkLineDash((l: GraphEdge) => (l.type === 'cooccurrence' ? [3, 3] : []));
}
