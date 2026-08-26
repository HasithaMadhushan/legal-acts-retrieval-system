"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { Button } from "@/components/ui/button";
import { displayActTitle } from "@/lib/act-display";
import {
  aggregateGraphEdges,
  displayEdgeLabel,
  edgeStrokeWidth,
  neighborCount,
  totalCitationCount,
  withPairOffsets,
  type AggregatedGraphEdge,
  type GraphEdgeInput,
  type GraphEdgeSelection
} from "@/lib/graph-edges";
import {
  clientPointToGraph,
  dragNodePosition,
  GRAPH_VIEW,
  resolvedNodePosition,
  type GraphPoint
} from "@/lib/graph-layout";
import { incidentCitationCount } from "@/lib/linked-acts";
import { cn } from "@/lib/utils";

interface Node {
  id: string;
  label: string;
  type: string;
}

type RelationshipGraphProps = Readonly<{
  nodes: Node[];
  edges: GraphEdgeInput[];
  focusId?: string | null;
  focusLabel?: string;
  depth?: number;
  unresolvedCount?: number;
  selectedNodeId?: string | null;
  selectedEdgeKey?: string | null;
  hasRendered?: boolean;
  statusFilter?: string;
  totalResults?: number;
  onSelectNode?: (nodeId: string) => void;
  onSelectEdge?: (edge: GraphEdgeSelection) => void;
  onRefocusNode?: (nodeId: string) => void;
}>;

export function RelationshipGraph({
  nodes,
  edges,
  focusId = null,
  focusLabel,
  depth = 1,
  unresolvedCount = 0,
  selectedNodeId = null,
  selectedEdgeKey = null,
  hasRendered = false,
  statusFilter = "verified_pending",
  totalResults = 0,
  onSelectNode,
  onSelectEdge,
  onRefocusNode
}: RelationshipGraphProps) {
  const [zoom, setZoom] = useState(1);
  const labelById = new Map(nodes.map((node) => [node.id, node.label]));
  const activeFocusId = focusId ?? nodes[0]?.id ?? null;
  const displayFocusLabel = readableActLabel(
    focusLabel ?? (activeFocusId ? labelById.get(activeFocusId) : undefined) ?? "Focus act"
  );

  const aggregatedEdges = useMemo(() => withPairOffsets(aggregateGraphEdges(edges)), [edges]);
  const selfLoopCount = edges.filter((edge) => edge.source === edge.target).length;
  const graphNodes = useMemo(
    () => visibleNodes(nodes, aggregatedEdges, activeFocusId),
    [nodes, aggregatedEdges, activeFocusId]
  );
  const selfLoopOnly = edges.length > 0 && aggregatedEdges.length === 0;
  const selectedLink = aggregatedEdges.find((edge) => edge.key === selectedEdgeKey) ?? null;
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ id: string; offset: GraphPoint } | null>(null);
  const [overrides, setOverrides] = useState<Record<string, GraphPoint>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const layoutKey = `${activeFocusId ?? ""}:${graphNodes.map((node) => node.id).join(",")}`;

  useEffect(() => {
    setOverrides({});
    setDraggingId(null);
    dragRef.current = null;
  }, [layoutKey]);

  useEffect(() => {
    if (!draggingId) return;

    function onMove(event: PointerEvent) {
      const drag = dragRef.current;
      const svg = svgRef.current;
      if (!drag || !svg) return;
      const rect = svg.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const next = dragNodePosition(
        { x: event.clientX, y: event.clientY },
        rect,
        zoom,
        drag.offset
      );
      setOverrides((current) => ({ ...current, [drag.id]: next }));
    }

    function onUp() {
      dragRef.current = null;
      setDraggingId(null);
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [draggingId, zoom]);

  function positionOf(id: string) {
    return resolvedNodePosition(id, graphNodes, activeFocusId, overrides);
  }

  function beginNodeDrag(nodeId: string, event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    event.preventDefault();
    event.stopPropagation();
    const local = clientPointToGraph({ x: event.clientX, y: event.clientY }, rect, zoom);
    const pos = positionOf(nodeId);
    dragRef.current = {
      id: nodeId,
      offset: { x: local.x - pos.x, y: local.y - pos.y }
    };
    setDraggingId(nodeId);
    onSelectNode?.(nodeId);
  }

  function resetView() {
    setZoom(1);
    setOverrides({});
    setDraggingId(null);
    dragRef.current = null;
  }

  if (!edges.length) {
    return (
      <div className="relative min-h-[420px] overflow-hidden rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
        <EmptyGraphState
          unresolvedCount={unresolvedCount}
          hasRendered={hasRendered}
          hasFocus={Boolean(activeFocusId)}
          statusFilter={statusFilter}
          totalResults={totalResults}
        />
      </div>
    );
  }

  if (selfLoopOnly) {
    const focusNode = nodes.find((node) => node.id === activeFocusId) ?? nodes[0];
    return (
      <div className="relative min-h-[420px] overflow-hidden rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
        <GraphChrome
          displayFocusLabel={displayFocusLabel}
          depth={depth}
          citationCount={0}
          linkedCount={0}
        />
        <SelfReferentialGraphState
          focusNode={focusNode}
          mappedCount={edges.length}
          selfLoopCount={selfLoopCount}
          unresolvedCount={unresolvedCount}
          selectedNodeId={selectedNodeId}
          onSelectNode={onSelectNode}
        />
      </div>
    );
  }

  return (
    <div className="relative min-h-[420px] overflow-hidden rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
      <GraphChrome
        displayFocusLabel={displayFocusLabel}
        depth={depth}
        citationCount={totalCitationCount(aggregatedEdges)}
        linkedCount={activeFocusId ? neighborCount(activeFocusId, aggregatedEdges) : graphNodes.length}
      />

      <svg
        ref={svgRef}
        viewBox={`0 0 ${GRAPH_VIEW.width} ${GRAPH_VIEW.height}`}
        className="pointer-events-none h-[420px] w-full"
        role="img"
        aria-label="Mapped Act-to-Act relationship graph"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 48% 48% at 50% 50%, rgba(20,38,60,0.07) 0%, rgba(20,38,60,0) 72%)"
        }}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#626b78" />
          </marker>
        </defs>
        <g
          className="pointer-events-auto"
          transform={`translate(${392 * (1 - zoom)} ${280 * (1 - zoom)}) scale(${zoom})`}
        >
          {aggregatedEdges.slice(0, 24).map((edge) => (
            <GraphEdgeLink
              key={edge.key}
              edge={edge}
              source={positionOf(edge.source)}
              target={positionOf(edge.target)}
              sourceLabel={labelById.get(edge.source) ?? edge.source}
              targetLabel={labelById.get(edge.target) ?? edge.target}
              selected={edge.key === selectedEdgeKey}
              onSelect={onSelectEdge}
            />
          ))}
          {paintOrder(graphNodes, draggingId).map((node) => {
            const position = positionOf(node.id);
            const isFocus = node.id === activeFocusId;
            const isSelected = isNodeSelected(node.id, selectedNodeId, selectedLink);
            const pending = aggregatedEdges.some(
              (edge) => (edge.source === node.id || edge.target === node.id) && edge.pending
            );
            const neighbors = neighborCount(node.id, aggregatedEdges);
            const citations = incidentCitationCount(node.id, aggregatedEdges);
            const detail = isFocus
              ? `${neighbors} linked Act${neighbors === 1 ? "" : "s"}`
              : `${citations} citation${citations === 1 ? "" : "s"}`;
            return (
              <GraphNodeCard
                key={node.id}
                node={node}
                position={position}
                isFocus={isFocus}
                isSelected={isSelected}
                pending={pending}
                detail={detail}
                dragging={draggingId === node.id}
                onPointerDown={(event) => beginNodeDrag(node.id, event)}
                onSelect={() => onSelectNode?.(node.id)}
                onDoubleClick={() => onRefocusNode?.(node.id)}
              />
            );
          })}
        </g>
      </svg>

      <GraphControls setZoom={setZoom} onResetView={resetView} />

      <div className="absolute right-4 bottom-5 flex flex-wrap gap-3 rounded-full border border-[#e4ddcd] bg-card/90 px-4 py-2 text-[11px] text-muted-foreground shadow-[0_4px_12px_rgba(11,22,38,0.08)] backdrop-blur-sm">
        <LegendSwatch color="#8c2433" label="Amends" />
        <LegendSwatch color="#22684a" label="Inserts" />
        <LegendSwatch color="#1e3a5f" label="Refers to" />
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1 w-5 rounded-sm bg-[#1e3a5f]" aria-hidden />
          More citations
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-3.5 border-t-2 border-dashed border-[#92681f]" aria-hidden />
          Pending
        </span>
      </div>

      <p className="sr-only">
        Mapped Act-to-Act graph edges only. Unresolved relationships: {unresolvedCount}.{" "}
        {aggregatedEdges
          .map(
            (edge) =>
              `${labelById.get(edge.source) ?? edge.source} ${displayEdgeLabel(edge.label, edge.count)} ${labelById.get(edge.target) ?? edge.target}.`
          )
          .join(" ")}
      </p>
    </div>
  );
}

function GraphEdgeLink({
  edge,
  source,
  target,
  sourceLabel,
  targetLabel,
  selected,
  onSelect
}: Readonly<{
  edge: AggregatedGraphEdge & { pairOffset: number };
  source: { x: number; y: number };
  target: { x: number; y: number };
  sourceLabel: string;
  targetLabel: string;
  selected: boolean;
  onSelect?: (edge: GraphEdgeSelection) => void;
}>) {
  const geometry = linkGeometry(source, target, edge.pairOffset);
  const width = edgeStrokeWidth(edge.count);
  const caption = displayEdgeLabel(edge.label, edge.count);

  function selectEdge() {
    onSelect?.({ source: edge.source, target: edge.target, label: edge.label, count: edge.count });
  }

  return (
    <g
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`${readableActLabel(sourceLabel)} ${caption} ${readableActLabel(targetLabel)}`}
      className="cursor-pointer outline-none"
      onClick={selectEdge}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectEdge();
        }
      }}
    >
      <path d={geometry.d} fill="none" stroke="transparent" strokeWidth="14" />
      <path
        d={geometry.d}
        fill="none"
        stroke={relationshipColor(edge.label)}
        strokeWidth={selected ? width + 1.5 : width}
        strokeDasharray={edge.pending ? "6 5" : undefined}
        markerEnd="url(#arrow)"
      />
      <foreignObject x={geometry.label.x - 70} y={geometry.label.y - 16} width="140" height="32">
        <div
          className={cn(
            "mx-auto w-fit max-w-[136px] rounded-full border px-2.5 py-1 text-center text-[10px] font-semibold leading-tight tracking-wide shadow-sm",
            edge.pending
              ? "border-dashed border-[#e6d8b4] bg-[#fffdf8] text-[#92681f]"
              : edgeBadgeClass(edge.label),
            selected ? "ring-2 ring-[#b8955a]/50" : ""
          )}
          onClick={selectEdge}
        >
          {caption}
        </div>
      </foreignObject>
    </g>
  );
}

function linkGeometry(
  source: { x: number; y: number },
  target: { x: number; y: number },
  pairOffset: number
) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const len = Math.hypot(dx, dy) || 1;
  const magnitude = pairOffset * 36;
  const controlX = (source.x + target.x) / 2 + (-dy / len) * magnitude;
  const controlY = (source.y + target.y) / 2 + (dx / len) * magnitude;
  const d =
    pairOffset === 0
      ? `M ${source.x} ${source.y} L ${target.x} ${target.y}`
      : `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`;
  return { d, label: { x: controlX, y: controlY } };
}

function isNodeSelected(
  nodeId: string,
  selectedNodeId: string | null,
  selectedLink: AggregatedGraphEdge | null
) {
  if (selectedLink) return nodeId === selectedLink.source || nodeId === selectedLink.target;
  return nodeId === selectedNodeId;
}

function GraphNodeCard({
  node,
  position,
  isFocus,
  isSelected,
  pending,
  detail,
  dragging,
  onPointerDown,
  onSelect,
  onDoubleClick
}: Readonly<{
  node: Node;
  position: GraphPoint;
  isFocus: boolean;
  isSelected: boolean;
  pending: boolean;
  detail: string;
  dragging: boolean;
  onPointerDown: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onSelect: () => void;
  onDoubleClick: () => void;
}>) {
  return (
    <foreignObject x={position.x - 90} y={position.y - 42} width="180" height="88">
      <button
        type="button"
        aria-grabbed={dragging}
        className={cn(
          "flex w-full cursor-grab flex-col items-start rounded-lg border bg-card px-3.5 py-2.5 text-left shadow-sm select-none touch-none",
          isFocus
            ? "border-[#b8955a] bg-[#fffbf2] shadow-[0_8px_24px_rgba(15,32,51,0.07)]"
            : pending
              ? "border-dashed border-[#1e3a5f]/55 opacity-70"
              : "border-[#1e3a5f]",
          isSelected && !isFocus ? "ring-2 ring-[#b8955a]/40" : "",
          dragging ? "cursor-grabbing shadow-lg" : ""
        )}
        onPointerDown={onPointerDown}
        onClick={onSelect}
        onDoubleClick={onDoubleClick}
      >
        <span
          className={cn(
            "text-[9.5px] font-semibold tracking-[0.57px] uppercase",
            isFocus ? "text-[#92681f]" : "text-muted-foreground"
          )}
        >
          {isFocus ? "This Act" : "Linked Act"}
        </span>
        <span className="mt-1 line-clamp-2 font-serif text-[13px] font-semibold leading-snug text-[#14263c]">
          {readableActLabel(node.label)}
        </span>
        <span className="mt-1 text-[11px] text-muted-foreground">{detail}</span>
      </button>
    </foreignObject>
  );
}

function paintOrder(nodes: Node[], draggingId: string | null) {
  if (!draggingId) return nodes;
  const dragging = nodes.find((node) => node.id === draggingId);
  if (!dragging) return nodes;
  return [...nodes.filter((node) => node.id !== draggingId), dragging];
}

function GraphChrome({
  displayFocusLabel,
  depth,
  linkedCount,
  citationCount
}: Readonly<{
  displayFocusLabel: string;
  depth: number;
  citationCount: number;
  linkedCount: number;
}>) {
  return (
    <div className="absolute top-3.5 left-3.5 z-10 flex max-w-[calc(100%-2rem)] flex-col gap-1 rounded-[18px] border border-[#e4ddcd] bg-card/85 px-3 py-2 text-xs shadow-sm backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <span className="size-[7px] shrink-0 rounded-[3px] bg-[#b8955a]" aria-hidden />
        <span className="shrink-0 text-[#14263c]">Focus:</span>
        <strong className="truncate font-semibold text-[#14263c]">{shortLabel(displayFocusLabel, 34)}</strong>
        <span className="shrink-0 whitespace-nowrap text-[#14263c]">
          · {depth} hop{depth === 1 ? "" : "s"} · {linkedCount} linked Act{linkedCount === 1 ? "" : "s"}
          {citationCount ? ` · ${citationCount} citation${citationCount === 1 ? "" : "s"}` : ""}
        </span>
      </div>
      <p className="pl-[15px] text-[11px] text-muted-foreground">
        Overview map · click a node or line to open citations
      </p>
    </div>
  );
}

function GraphControls({
  setZoom,
  onResetView
}: Readonly<{
  setZoom: (value: number | ((current: number) => number)) => void;
  onResetView: () => void;
}>) {
  return (
    <div className="absolute bottom-5 left-4 flex flex-col overflow-hidden rounded-md border border-[#e4ddcd] bg-card shadow-[0_4px_12px_rgba(11,22,38,0.08)]">
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="rounded-none border-b border-[#e4ddcd]"
        aria-label="Zoom in"
        onClick={() => setZoom((value) => Math.min(1.35, value + 0.15))}
      >
        <Plus className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="rounded-none border-b border-[#e4ddcd]"
        aria-label="Zoom out"
        onClick={() => setZoom((value) => Math.max(0.7, value - 0.15))}
      >
        <Minus className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="rounded-none"
        aria-label="Reset view"
        onClick={onResetView}
      >
        <Maximize2 className="size-3.5" />
      </Button>
    </div>
  );
}

function SelfReferentialGraphState({
  focusNode,
  mappedCount,
  selfLoopCount,
  unresolvedCount,
  selectedNodeId,
  onSelectNode
}: Readonly<{
  focusNode?: Node;
  mappedCount: number;
  selfLoopCount: number;
  unresolvedCount: number;
  selectedNodeId?: string | null;
  onSelectNode?: (nodeId: string) => void;
}>) {
  if (!focusNode) return null;
  const isSelected = selectedNodeId === focusNode.id;
  return (
    <div className="flex h-[420px] flex-col items-center justify-center gap-5 px-8 py-10 text-center">
      <button
        type="button"
        className={cn(
          "flex w-full max-w-[190px] flex-col items-start rounded-lg border border-[#b8955a] bg-[#fffbf2] px-4 py-3 text-left shadow-[0_8px_24px_rgba(15,32,51,0.07)]",
          isSelected ? "ring-2 ring-[#b8955a]/40" : ""
        )}
        onClick={() => onSelectNode?.(focusNode.id)}
      >
        <div className="flex w-full items-center justify-between gap-2">
          <span className="text-[9.5px] font-semibold tracking-[0.57px] text-[#92681f] uppercase">
            Focus · {focusNode.type}
          </span>
          <span className="rounded-full border border-border bg-background px-1.5 text-[10px] font-semibold text-muted-foreground">
            {Math.min(mappedCount, 99)}
          </span>
        </div>
        <span className="mt-1 line-clamp-3 font-serif text-[13px] font-semibold leading-snug text-[#14263c]">
          {readableActLabel(focusNode.label)}
        </span>
        <span className="mt-1 text-[11px] text-muted-foreground">Pending references</span>
      </button>
      <div className="max-w-md space-y-2">
        <p className="text-sm text-[#14263c]">
          No external Act-to-Act network to draw yet. {mappedCount} mapped reference
          {mappedCount === 1 ? "" : "s"} stay within this Act
          {selfLoopCount ? ` (${selfLoopCount} self-link${selfLoopCount === 1 ? "" : "s"})` : ""}.
        </p>
        <p className="text-xs text-muted-foreground">
          Open <strong className="font-medium text-foreground">Table</strong> to inspect each reference.
          Unresolved relationships: {unresolvedCount}.
        </p>
      </div>
    </div>
  );
}

function EmptyGraphState({
  unresolvedCount,
  hasRendered,
  hasFocus,
  statusFilter,
  totalResults
}: Readonly<{
  unresolvedCount: number;
  hasRendered: boolean;
  hasFocus: boolean;
  statusFilter: string;
  totalResults: number;
}>) {
  let title = "Choose an Act to render its mapped relationships.";
  let subtitle = `Unresolved relationships: ${unresolvedCount}`;

  if (hasFocus && !hasRendered) {
    title = "Press Render to load the relationship graph.";
    subtitle = "Filters apply when you render. Unresolved relationships are listed after load.";
  } else if (hasRendered && totalResults === 0 && statusFilter === "VERIFIED") {
    title = "No verified relationships match these filters.";
    subtitle = "Try Verified + pending, or switch to Table view for the full reference list.";
  } else if (hasRendered && totalResults === 0) {
    title = "No relationships match these filters.";
    subtitle = `Unresolved relationships: ${unresolvedCount}. Try broadening Status or Relationship filters.`;
  } else if (hasRendered) {
    title = "No mapped Act-to-Act edges to draw for this focus.";
    subtitle = `Table view lists ${totalResults} reference${totalResults === 1 ? "" : "s"}. Unresolved: ${unresolvedCount}.`;
  }

  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 px-8 py-16 text-center">
      <p className="max-w-lg text-[15px] leading-6 text-[#14263c]">{title}</p>
      <p className="max-w-md text-xs leading-5 text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function readableActLabel(label: string | null | undefined) {
  return displayActTitle({
    title: label,
    act_number: null,
    year: null,
    source_file_name: null
  });
}

function visibleNodes(
  nodes: Node[],
  edges: { source: string; target: string }[],
  focusId: string | null
) {
  const ids = new Set<string>();
  if (focusId) ids.add(focusId);
  for (const edge of edges) {
    ids.add(edge.source);
    ids.add(edge.target);
  }
  return nodes.filter((node) => ids.has(node.id)).slice(0, 8);
}

function LegendSwatch({ color, label }: Readonly<{ color: string; label: string }>) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-0.5 w-3.5 rounded-sm" style={{ backgroundColor: color }} aria-hidden />
      {label}
    </span>
  );
}

function relationshipColor(label: string) {
  if (label.includes("AMEND") || label.includes("REPEAL")) return "#8c2433";
  if (label.includes("INSERT") || label.includes("ADD")) return "#22684a";
  return "#1e3a5f";
}

function edgeBadgeClass(label: string) {
  if (label.includes("AMEND") || label.includes("REPEAL")) {
    return "border-[#e3c3c8] bg-[#f4f1ea] text-[#8c2433]";
  }
  if (label.includes("INSERT") || label.includes("ADD")) {
    return "border-[#cfe0d4] bg-[#ebf3ee] text-[#22684a]";
  }
  return "border-[#c8d5e2] bg-[#fffefb] text-[#1e3a5f]";
}

function shortLabel(label: string, max = 28) {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}
