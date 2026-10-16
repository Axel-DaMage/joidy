import type { GraphNode, GraphEdge } from '$lib/api';

export interface GraphFilterOptions {
  showNotes: boolean;
  showTags: boolean;
  showUnresolved: boolean;
  showAttachments: boolean;
  showOrphans: boolean;
  showCooccurrences: boolean;
}

export function filterGraphData(
  src: { nodes: GraphNode[]; edges: GraphEdge[] },
  opts: GraphFilterOptions
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const { showNotes, showTags, showUnresolved, showAttachments, showOrphans, showCooccurrences } =
    opts;
  const nodes = src.nodes.slice();
  const edges = src.edges.slice();

  // 1. Filter nodes based on visible types
  let filteredNodes = nodes.filter((n) => {
    if (n.type === 'note' && !showNotes) return false;
    if (n.type === 'tag' && !showTags) return false;
    if (n.type === 'unresolved' && !showUnresolved) return false;
    if ((n.type as string) === 'attachment' && !showAttachments) return false;
    return true;
  });

  const nodeIds = new Set(filteredNodes.map((n) => n.id));
  const getEdgeSourceId = (e: any) => (typeof e.source === 'object' ? e.source.id : e.source);
  const getEdgeTargetId = (e: any) => (typeof e.target === 'object' ? e.target.id : e.target);

  // 2. Filter edges based on visible nodes and type
  let filteredEdges = edges.filter((e) => {
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
    filteredNodes = filteredNodes.filter((n) => (degree.get(n.id) ?? 0) > 0);

    const finalNodeIds = new Set(filteredNodes.map((n) => n.id));
    filteredEdges = filteredEdges.filter(
      (e) => finalNodeIds.has(getEdgeSourceId(e)) && finalNodeIds.has(getEdgeTargetId(e))
    );
  }

  return { nodes: filteredNodes, edges: filteredEdges };
}
