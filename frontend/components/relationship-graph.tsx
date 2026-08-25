"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { displayActTitle } from "@/lib/act-display";
import { cn } from "@/lib/utils";

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

type RelationshipGraphProps = Readonly<{
  nodes: Node[];
  edges: Edge[];
  focusId?: string | null;
  focusLabel?: string;
  depth?: number;
  unresolvedCount?: number;
  selectedNodeId?: string | null;
  hasRendered?: boolean;
  statusFilter?: string;
  totalResults?: number;
  onSelectNode?: (nodeId: string) => void;
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
  hasRendered = false,
  statusFilter = "verified_pending",
  totalResults = 0,
  onSelectNode,
  onRefocusNode
}: RelationshipGraphProps) {
  const [zoom, setZoom] = useState(1);
  const labelById = new Map(nodes.map((node) => [node.id, node.label]));
  const activeFocusId = focusId ?? nodes[0]?.id ?? null;
  const displayFocusLabel = readableActLabel(
    focusLabel ?? (activeFocusId ? labelById.get(activeFocusId) : undefined) ?? "Focus act"
  );

  const externalEdges = useMemo(
    () => edges.filter((edge) => edge.source !== edge.target),
    [edges]
  );
  const selfLoopCount = edges.length - externalEdges.length;
  const graphNodes = useMemo(
    () => visibleNodes(nodes, externalEdges, activeFocusId),
    [nodes, externalEdges, activeFocusId]
  );
  const selfLoopOnly = edges.length > 0 && externalEdges.length === 0;

  if (!edges.length) {
    return (
      <div className="relative min-h-[560px] overflow-hidden rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
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
      <div className="relative min-h-[560px] overflow-hidden rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
        <GraphChrome
          displayFocusLabel={displayFocusLabel}
          depth={depth}
          nodeCount={1}
          edgeCount={edges.length}
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
    <div className="relative min-h-[560px] overflow-hidden rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
      <GraphChrome
        displayFocusLabel={displayFocusLabel}
        depth={depth}
        nodeCount={graphNodes.length}
        edgeCount={externalEdges.length}
      />

      <svg
        viewBox="0 0 784 560"
        className="h-[560px] w-full"
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
        <g transform={`translate(${392 * (1 - zoom)} ${280 * (1 - zoom)}) scale(${zoom})`}>
          {externalEdges.slice(0, 24).map((edge) => {
            const source = positionFor(edge.source, graphNodes, activeFocusId);
            const target = positionFor(edge.target, graphNodes, activeFocusId);
            const pending = edge.status !== "VERIFIED";
            return (
              <g key={edge.id}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={relationshipColor(edge.label)}
                  strokeWidth="1.5"
                  strokeDasharray={pending ? "5 5" : undefined}
                  markerEnd="url(#arrow)"
                />
                <foreignObject
                  x={(source.x + target.x) / 2 - 56}
                  y={(source.y + target.y) / 2 - 16}
                  width="112"
                  height="32"
                >
                  <div
                    className={cn(
                      "mx-auto w-fit max-w-[108px] rounded-full border px-2.5 py-1 text-center text-[10px] font-semibold leading-tight tracking-wide shadow-sm",
                      pending
                        ? "border-dashed border-[#e6d8b4] bg-[#fffdf8] text-[#92681f]"
                        : edgeBadgeClass(edge.label)
                    )}
                  >
                    {edgeLabel(edge.label, pending)}
                  </div>
                </foreignObject>
              </g>
            );
          })}
          {graphNodes.map((node) => {
            const position = positionFor(node.id, graphNodes, activeFocusId);
            const isFocus = node.id === activeFocusId;
            const isSelected = node.id === selectedNodeId;
            const pending = externalEdges.some(
              (edge) =>
                (edge.source === node.id || edge.target === node.id) && edge.status !== "VERIFIED"
            );
            const edgeCount = externalEdges.filter(
              (edge) => edge.source === node.id || edge.target === node.id
            ).length;
            return (
              <foreignObject key={node.id} x={position.x - 90} y={position.y - 42} width="180" height="96">
                <button
                  type="button"
                  className={cn(
                    "flex w-full flex-col items-start rounded-lg border bg-card px-3.5 py-2.5 text-left shadow-sm transition-shadow",
                    isFocus
                      ? "border-[#b8955a] bg-[#fffbf2] shadow-[0_8px_24px_rgba(15,32,51,0.07)]"
                      : pending
                        ? "border-dashed border-[#1e3a5f]/55 opacity-70"
                        : "border-[#1e3a5f]",
                    isSelected && !isFocus ? "ring-2 ring-[#b8955a]/40" : ""
                  )}
                  onClick={() => onSelectNode?.(node.id)}
                  onDoubleClick={() => onRefocusNode?.(node.id)}
                >
                  <div className="flex w-full items-center justify-between gap-2">
                    <span
                      className={cn(
                        "text-[9.5px] font-semibold tracking-[0.57px] uppercase",
                        isFocus ? "text-[#92681f]" : "text-muted-foreground"
                      )}
                    >
                      {isFocus ? `Focus · ${node.type}` : node.type}
                    </span>
                    {isFocus ? (
                      <span className="rounded-full border border-border bg-background px-1.5 text-[10px] font-semibold text-muted-foreground">
                        {Math.min(edgeCount, 99)}
                      </span>
                    ) : null}
                  </div>
                  <span className="mt-1 line-clamp-2 font-serif text-[13px] font-semibold leading-snug text-[#14263c]">
                    {readableActLabel(node.label)}
                  </span>
                  <span className="mt-1 text-[11px] text-muted-foreground">
                    {pending ? "Pending references" : "Verified"}
                  </span>
                </button>
              </foreignObject>
            );
          })}
        </g>
      </svg>

      <GraphControls zoom={zoom} setZoom={setZoom} />

      <div className="absolute right-4 bottom-5 flex flex-wrap gap-3 rounded-full border border-[#e4ddcd] bg-card/90 px-4 py-2 text-[11px] text-muted-foreground shadow-[0_4px_12px_rgba(11,22,38,0.08)] backdrop-blur-sm">
        <LegendSwatch color="#8c2433" label="Amends" />
        <LegendSwatch color="#22684a" label="Inserts" />
        <LegendSwatch color="#1e3a5f" label="Refers to" />
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-3.5 border-t-2 border-dashed border-[#92681f]" aria-hidden />
          Pending
        </span>
      </div>

      <p className="sr-only">
        Mapped Act-to-Act graph edges only. Unresolved relationships: {unresolvedCount}.{" "}
        {externalEdges
          .map(
            (edge) =>
              `${labelById.get(edge.source) ?? edge.source} ${edge.label} ${labelById.get(edge.target) ?? edge.target}.`
          )
          .join(" ")}
      </p>
    </div>
  );
}

function GraphChrome({
  displayFocusLabel,
  depth,
  nodeCount,
  edgeCount
}: Readonly<{
  displayFocusLabel: string;
  depth: number;
  nodeCount: number;
  edgeCount: number;
}>) {
  return (
    <div className="absolute top-3.5 left-3.5 z-10 flex max-w-[calc(100%-2rem)] items-center gap-2 rounded-full border border-[#e4ddcd] bg-card/80 px-3 py-1.5 text-xs shadow-sm backdrop-blur-sm">
      <span className="size-[7px] shrink-0 rounded-[3px] bg-[#b8955a]" aria-hidden />
      <span className="shrink-0 text-[#14263c]">Focus:</span>
      <strong className="truncate font-semibold text-[#14263c]">{shortLabel(displayFocusLabel, 34)}</strong>
      <span className="shrink-0 whitespace-nowrap text-[#14263c]">
        · {depth} hop{depth === 1 ? "" : "s"} · {nodeCount} node{nodeCount === 1 ? "" : "s"} · {edgeCount} edge
        {edgeCount === 1 ? "" : "s"}
      </span>
    </div>
  );
}

function GraphControls({
  zoom,
  setZoom
}: Readonly<{ zoom: number; setZoom: (value: number | ((current: number) => number)) => void }>) {
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
        aria-label="Reset zoom"
        onClick={() => setZoom(1)}
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
    <div className="flex h-[560px] flex-col items-center justify-center gap-5 px-8 py-10 text-center">
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
    <div className="flex h-full min-h-[560px] flex-col items-center justify-center gap-3 px-8 py-16 text-center">
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

function visibleNodes(nodes: Node[], edges: Edge[], focusId: string | null) {
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

const positions = [
  { x: 376, y: 252 },
  { x: 126, y: 236 },
  { x: 610, y: 212 },
  { x: 236, y: 436 },
  { x: 548, y: 436 },
  { x: 392, y: 96 },
  { x: 120, y: 360 },
  { x: 660, y: 360 }
];

function positionFor(id: string, nodes: Node[], focusId: string | null) {
  if (focusId && id === focusId) return positions[0]!;
  const others = nodes.filter((node) => node.id !== focusId);
  const index = Math.max(0, others.findIndex((node) => node.id === id));
  return positions[(index % (positions.length - 1)) + 1] ?? positions[1]!;
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

function edgeLabel(label: string, pending: boolean) {
  const base = label.replaceAll("_", " ").toLowerCase();
  return pending ? `${base} · pending` : base;
}

function shortLabel(label: string, max = 28) {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}
