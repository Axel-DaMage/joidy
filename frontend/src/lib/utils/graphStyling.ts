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

// Styling inputs the paint callbacks need live — read via getters so a
// hover/selection/search change is picked up by the very next repaint without
// re-registering callbacks (#1311 — the by-value captures left highlights
// permanently stale).
export interface GraphStylingContext {
  getHoveredNode: () => GraphNode | null;
  getSelectedTag: () => number | string | null;
  getSearchQuery: () => string;
  getFocusId: () => number | string | null;
  neighbors: Map<number | string, Set<number | string>>;
  getNodeSizeScale: () => number;
  getLinkThicknessScale: () => number;
  getShowLabels: () => boolean;
  getTextScale: () => number;
  getLabelThreshold: () => number;
  getColorGroups: () => ColorGroup[];
}

// Radial gradients are position-independent once the context is translated to
// the node center — cache one per (color, radius) instead of allocating a new
// CanvasGradient for every node on every frame.
const gradientCache = new WeakMap<object, Map<string, CanvasGradient>>();

function getNodeGradient(
  graph: object,
  ctx2: CanvasRenderingContext2D,
  color: string,
  r: number,
): CanvasGradient {
  let cache = gradientCache.get(graph);
  if (!cache) {
    cache = new Map();
    gradientCache.set(graph, cache);
  }
  const key = `${color}:${r}`;
  let gradient = cache.get(key);
  if (!gradient) {
    gradient = ctx2.createRadialGradient(-r * 0.3, -r * 0.3, 0, 0, 0, r);
    gradient.addColorStop(0, lightenColor(color, 0.25));
    gradient.addColorStop(1, color);
    cache.set(key, gradient);
  }
  return gradient;
}

export function applyGraphStyling(graph: any, ctx: GraphStylingContext) {
  if (!graph) return;
  const {
    getHoveredNode,
    getSelectedTag,
    getSearchQuery,
    getFocusId,
    neighbors,
    getNodeSizeScale,
    getLinkThicknessScale,
    getShowLabels,
    getTextScale,
    getLabelThreshold,
    getColorGroups,
  } = ctx;

  graph
    .nodeRelSize(3.2)
    .nodeCanvasObject((node: ForceGraphNode, ctx2: CanvasRenderingContext2D, scale: number) => {
      const x = node.x;
      const y = node.y;
      if (x === undefined || y === undefined || !Number.isFinite(x) || !Number.isFinite(y)) return;

      const hoveredNode = getHoveredNode();
      const selectedTag = getSelectedTag();
      const q = getSearchQuery().trim().toLowerCase();
      const focusId = getFocusId();
      const nodeSizeScale = getNodeSizeScale();
      const showLabels = getShowLabels();
      const textScale = getTextScale();
      const labelThreshold = getLabelThreshold();
      const colorGroups = getColorGroups();
      const focus = hoveredNode?.id ?? selectedTag;

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
      if (isUnresolved) {
        ctx2.beginPath();
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
        // Normal nodes draw with a cached gradient fill (#1311)
        ctx2.save();
        ctx2.translate(x, y);
        ctx2.beginPath();
        ctx2.fillStyle = getNodeGradient(graph, ctx2, nodeColor, r);
        ctx2.arc(0, 0, r, 0, Math.PI * 2);
        ctx2.fill();
        ctx2.restore();
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
      const linkThicknessScale = getLinkThicknessScale();
      const focus = getHoveredNode()?.id ?? getSelectedTag();
      let baseWidth = l.type === 'hierarchy' ? 1.5 : 0.8;
      if (l.weight) {
        baseWidth *= Math.sqrt(l.weight);
      }
      baseWidth *= linkThicknessScale;

      if (focus === null || focus === undefined) return baseWidth;

      const sourceId = typeof l.source === 'object' ? (l.source as any).id : l.source;
      const targetId = typeof l.target === 'object' ? (l.target as any).id : l.target;
      return sourceId === focus || targetId === focus ? baseWidth * 1.5 : baseWidth * 0.2;
    })
    .linkColor((l: GraphEdge) => {
      const focus = getHoveredNode()?.id ?? getSelectedTag();
      const sourceId = typeof l.source === 'object' ? (l.source as any).id : l.source;
      const targetId = typeof l.target === 'object' ? (l.target as any).id : l.target;

      // Hover highlighting of links
      let color = '#383838'; // very subtle dark grey in dark mode
      if (l.type === 'hierarchy') color = '#525252';
      else if (l.type === 'cooccurrence') color = '#2c2c2c';
      else if (l.type === 'linked') color = '#404040';
      else if (l.type === 'tagged') color = '#4a4a4a';

      if (focus === null || focus === undefined) return color;

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
