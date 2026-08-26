export type GraphEdgeInput = {
  id: string;
  source: string;
  target: string;
  label: string;
  status: string;
};

export type AggregatedGraphEdge = {
  key: string;
  source: string;
  target: string;
  label: string;
  count: number;
  pending: boolean;
  memberIds: string[];
};

export type GraphEdgeSelection = {
  source: string;
  target: string;
  label: string;
  count: number;
};

export type GraphCitationRow = {
  source_act_id: string;
  target_act_id: string | null;
  relationship_type: string;
};

export function graphEdgeKey(edge: Pick<AggregatedGraphEdge, "source" | "target" | "label">) {
  return `${edge.source}|${edge.target}|${edge.label}`;
}

export function aggregateGraphEdges(edges: readonly GraphEdgeInput[]): AggregatedGraphEdge[] {
  const groups = new Map<string, GraphEdgeInput[]>();
  for (const edge of edges) {
    if (edge.source === edge.target) continue;
    const key = graphEdgeKey(edge);
    const group = groups.get(key);
    if (group) group.push(edge);
    else groups.set(key, [edge]);
  }
  return [...groups.entries()].flatMap(([key, members]) => {
    const first = members[0];
    if (!first) return [];
    return [
      {
        key,
        source: first.source,
        target: first.target,
        label: first.label,
        count: members.length,
        pending: members.some((member) => member.status !== "VERIFIED"),
        memberIds: members.map((member) => member.id)
      }
    ];
  });
}

export function neighborCount(nodeId: string, edges: readonly AggregatedGraphEdge[]): number {
  const neighbors = new Set<string>();
  for (const edge of edges) {
    if (edge.source === nodeId) neighbors.add(edge.target);
    else if (edge.target === nodeId) neighbors.add(edge.source);
  }
  return neighbors.size;
}

export function displayEdgeLabel(label: string, count: number) {
  return `${formatRelationshipType(label).toLowerCase()} · ${count}`;
}

export function formatRelationshipType(type: string) {
  return type
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^\w/, (char) => char.toUpperCase());
}

export function edgeStrokeWidth(count: number) {
  return Math.min(8, 1.75 + Math.log2(Math.max(1, count)) * 1.35);
}

export function withPairOffsets(
  edges: readonly AggregatedGraphEdge[]
): (AggregatedGraphEdge & { pairOffset: number })[] {
  const groups = new Map<string, AggregatedGraphEdge[]>();
  for (const edge of edges) {
    const pair = edge.source < edge.target ? `${edge.source}~${edge.target}` : `${edge.target}~${edge.source}`;
    const group = groups.get(pair);
    if (group) group.push(edge);
    else groups.set(pair, [edge]);
  }
  const offsetByKey = new Map<string, number>();
  for (const group of groups.values()) {
    const mid = (group.length - 1) / 2;
    group.forEach((edge, index) => {
      offsetByKey.set(edge.key, index - mid);
    });
  }
  return edges.map((edge) => ({
    ...edge,
    pairOffset: offsetByKey.get(edge.key) ?? 0
  }));
}

export function rowsMatchingGraphSelection<T extends GraphCitationRow>(
  rows: readonly T[],
  selection: { edge: GraphEdgeSelection | null; nodeId: string | null }
): T[] {
  const selectedEdge = selection.edge;
  if (selectedEdge) {
    return rows.filter(
      (row) =>
        row.source_act_id === selectedEdge.source &&
        row.target_act_id === selectedEdge.target &&
        row.relationship_type === selectedEdge.label
    );
  }
  const nodeId = selection.nodeId;
  if (!nodeId) return [];
  return rows.filter((row) => row.source_act_id === nodeId || row.target_act_id === nodeId);
}

export function totalCitationCount(edges: readonly AggregatedGraphEdge[]) {
  return edges.reduce((sum, edge) => sum + edge.count, 0);
}
