export type GraphPoint = {
  x: number;
  y: number;
};

export type GraphRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export const GRAPH_VIEW = { width: 784, height: 560 };
const NODE_HALF = { x: 90, y: 42 };

export const DEFAULT_NODE_SLOTS: GraphPoint[] = [
  { x: 376, y: 252 },
  { x: 126, y: 236 },
  { x: 610, y: 212 },
  { x: 236, y: 436 },
  { x: 548, y: 436 },
  { x: 392, y: 96 },
  { x: 120, y: 360 },
  { x: 660, y: 360 }
];

export function defaultNodePosition(
  id: string,
  nodes: readonly { id: string }[],
  focusId: string | null
): GraphPoint {
  if (focusId && id === focusId) return DEFAULT_NODE_SLOTS[0] ?? { x: 376, y: 252 };
  const others = nodes.filter((node) => node.id !== focusId);
  const index = Math.max(0, others.findIndex((node) => node.id === id));
  return DEFAULT_NODE_SLOTS[(index % (DEFAULT_NODE_SLOTS.length - 1)) + 1] ?? { x: 126, y: 236 };
}

export function clampNodePosition(point: GraphPoint): GraphPoint {
  return {
    x: Math.min(GRAPH_VIEW.width - NODE_HALF.x, Math.max(NODE_HALF.x, point.x)),
    y: Math.min(GRAPH_VIEW.height - NODE_HALF.y, Math.max(NODE_HALF.y, point.y))
  };
}

export function resolvedNodePosition(
  id: string,
  nodes: readonly { id: string }[],
  focusId: string | null,
  overrides: Readonly<Record<string, GraphPoint>>
): GraphPoint {
  const override = overrides[id];
  if (override) return clampNodePosition(override);
  return defaultNodePosition(id, nodes, focusId);
}

export function clientPointToGraph(client: GraphPoint, svg: GraphRect, zoom: number): GraphPoint {
  const scale = zoom === 0 ? 1 : zoom;
  const viewX = ((client.x - svg.left) / svg.width) * GRAPH_VIEW.width;
  const viewY = ((client.y - svg.top) / svg.height) * GRAPH_VIEW.height;
  const originX = (GRAPH_VIEW.width / 2) * (1 - scale);
  const originY = (GRAPH_VIEW.height / 2) * (1 - scale);
  return {
    x: (viewX - originX) / scale,
    y: (viewY - originY) / scale
  };
}

export function dragNodePosition(
  client: GraphPoint,
  svg: GraphRect,
  zoom: number,
  grabOffset: GraphPoint
): GraphPoint {
  const local = clientPointToGraph(client, svg, zoom);
  return clampNodePosition({ x: local.x - grabOffset.x, y: local.y - grabOffset.y });
}
