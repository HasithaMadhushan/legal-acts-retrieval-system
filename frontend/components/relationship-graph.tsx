"use client";

import { StatusBadge } from "@/components/status-badge";

interface Edge {
  id: string;
  source: string;
  target: string;
  label: string;
  status: string;
}

interface Node {
  id: string;
  label: string;
  type: string;
}

export function RelationshipGraph({
  nodes,
  edges,
  unresolvedCount = 0
}: {
  nodes: Node[];
  edges: Edge[];
  unresolvedCount?: number;
}) {
  const labelById = new Map(nodes.map((node) => [node.id, node.label]));
  if (!edges.length) {
    return (
      <div className="empty">
        No verified relationships are available yet. Unresolved relationships: {unresolvedCount}
      </div>
    );
  }
  return (
    <div className="panel graph">
      <p className="muted">Mapped Act-to-Act graph edges only. Unresolved relationships: {unresolvedCount}</p>
      {edges.map((edge) => (
        <div className="graph-row" key={edge.id}>
          <strong>{labelById.get(edge.source) ?? edge.source}</strong>
          <span>
            <StatusBadge value={edge.label} /> <StatusBadge value={edge.status} />
          </span>
          <strong>{labelById.get(edge.target) ?? edge.target}</strong>
        </div>
      ))}
    </div>
  );
}
