import type { AggregatedGraphEdge } from "./graph-edges";

export type LinkedActTypeCount = {
  type: string;
  count: number;
  pending: boolean;
};

export type LinkedActSummary = {
  actId: string;
  title: string;
  total: number;
  pending: boolean;
  types: LinkedActTypeCount[];
};

export function summarizeLinkedActs(
  edges: readonly AggregatedGraphEdge[],
  nodes: readonly { id: string; label: string }[],
  focusId: string
): LinkedActSummary[] {
  const titleById = new Map(nodes.map((node) => [node.id, node.label]));
  const byAct = new Map<string, LinkedActSummary>();

  for (const edge of edges) {
    const actId = otherActId(edge, focusId);
    if (!actId) continue;
    const current = byAct.get(actId) ?? {
      actId,
      title: titleById.get(actId) ?? actId,
      total: 0,
      pending: false,
      types: []
    };
    current.total += edge.count;
    current.pending = current.pending || edge.pending;
    const existingType = current.types.find((entry) => entry.type === edge.label);
    if (existingType) {
      existingType.count += edge.count;
      existingType.pending = existingType.pending || edge.pending;
    } else {
      current.types.push({ type: edge.label, count: edge.count, pending: edge.pending });
    }
    byAct.set(actId, current);
  }

  return [...byAct.values()].sort((left, right) => right.total - left.total || left.title.localeCompare(right.title));
}

export function otherActId(edge: Pick<AggregatedGraphEdge, "source" | "target">, focusId: string) {
  if (edge.source === focusId) return edge.target;
  if (edge.target === focusId) return edge.source;
  return null;
}

export function incidentCitationCount(
  nodeId: string,
  edges: readonly Pick<AggregatedGraphEdge, "source" | "target" | "count">[]
) {
  return edges
    .filter((edge) => edge.source === nodeId || edge.target === nodeId)
    .reduce((sum, edge) => sum + edge.count, 0);
}
