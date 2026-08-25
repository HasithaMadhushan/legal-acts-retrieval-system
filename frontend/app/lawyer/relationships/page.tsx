"use client";

import Link from "next/link";
import { Download } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import {
  createSavedItem,
  deleteSavedItem,
  exportUrl,
  getAct,
  getActRelationships,
  getRelationshipGraph,
  getSectionRelationships,
  listActs,
  listSavedItems
} from "@/lib/api";
import { displayActTitle, displayActTitleWithMeta } from "@/lib/act-display";
import { getToken } from "@/lib/auth";
import type {
  LegalAct,
  RelationshipGraphResponse,
  RelationshipListResponse,
  RelationshipRow,
  RelationshipType,
  SavedItem,
  VerificationStatus
} from "@/lib/types";
import { RelationshipGraph } from "@/components/relationship-graph";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

type LookupMode = "act" | "section";
type StatusFilter = "verified_pending" | VerificationStatus | "ANY";

const RELATIONSHIP_TYPES: RelationshipType[] = [
  "REFERS_TO",
  "AMENDS",
  "REPEALS",
  "INSERTS",
  "SUBSTITUTES",
  "ADDS",
  "CROSS_REFERENCE"
];

export default function LawyerRelationshipsPage() {
  const [lookupMode, setLookupMode] = useState<LookupMode>("act");
  const [focusId, setFocusId] = useState("");
  const [acts, setActs] = useState<LegalAct[]>([]);
  const [focusAct, setFocusAct] = useState<LegalAct | null>(null);
  const [relationshipType, setRelationshipType] = useState("ANY");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("verified_pending");
  const [depth, setDepth] = useState<1 | 2>(2);
  const [relationships, setRelationships] = useState<RelationshipListResponse | null>(null);
  const [graph, setGraph] = useState<RelationshipGraphResponse | null>(null);
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"graph" | "table">("graph");
  const [offset, setOffset] = useState(0);
  const [limit] = useState("50");

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    void loadSavedItems();
    try {
      const actList = await listActs();
      setActs(actList);
    } catch {
      setActs([]);
    }
    const params = new URLSearchParams(window.location.search);
    const actId = params.get("actId");
    const sectionId = params.get("sectionId");
    if (sectionId) {
      setLookupMode("section");
      setFocusId(sectionId);
      void loadRelationships("section", sectionId, 0, depth);
    } else if (actId) {
      setLookupMode("act");
      setFocusId(actId);
      void loadRelationships("act", actId, 0, depth);
    }
  }

  async function loadSavedItems() {
    try {
      const data = await listSavedItems({ item_type: "REFERENCE", limit: "100", offset: "0" });
      setSavedItems(data.items);
    } catch {
      setSavedItems([]);
    }
  }

  function queryParams(nextOffset: number, nextDepth: number) {
    return {
      ...(relationshipType !== "ANY" ? { relationship_type: relationshipType } : {}),
      ...(statusFilter !== "verified_pending" && statusFilter !== "ANY"
        ? { verification_status: statusFilter }
        : {}),
      limit,
      offset: String(nextOffset),
      depth: String(nextDepth)
    };
  }

  async function loadRelationships(
    mode: LookupMode = lookupMode,
    id: string = focusId,
    nextOffset = 0,
    nextDepth: number = depth
  ) {
    if (!id.trim()) {
      setError("Choose a focus Act to render relationships.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const params = queryParams(nextOffset, nextDepth);
      const relationshipData =
        mode === "act"
          ? await getActRelationships(id.trim(), params)
          : await getSectionRelationships(id.trim(), params);
      const graphData = await getRelationshipGraph({
        ...params,
        ...(mode === "act" ? { act_id: id.trim() } : { section_id: id.trim() })
      });
      setRelationships(relationshipData);
      setGraph(graphData);
      setOffset(nextOffset);
      setSelectedNodeId(mode === "act" ? id.trim() : graphData.nodes[0]?.id ?? null);
      if (mode === "act") {
        try {
          setFocusAct(await getAct(id.trim()));
        } catch {
          setFocusAct(acts.find((act) => act.id === id) ?? null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Relationship lookup failed.");
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await loadRelationships(lookupMode, focusId, 0, depth);
  }

  function chooseFocus(actId: string) {
    setLookupMode("act");
    setFocusId(actId);
  }

  async function refocusOnNode(nodeId: string) {
    setLookupMode("act");
    setFocusId(nodeId);
    setDepth(1);
    await loadRelationships("act", nodeId, 0, 1);
  }

  async function expandOneHop() {
    setDepth(2);
    await loadRelationships(lookupMode, focusId, 0, 2);
  }

  async function saveRelationship(row: RelationshipRow) {
    setWorkspaceMessage("");
    try {
      await createSavedItem({ item_type: "REFERENCE", reference_id: row.id });
      setWorkspaceMessage("Reference saved to workspace.");
      await loadSavedItems();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not save reference.";
      setWorkspaceMessage(message.includes("already saved") ? "Already saved in workspace." : message);
      await loadSavedItems();
    }
  }

  async function unsaveRelationship(savedItemId: string) {
    setWorkspaceMessage("");
    try {
      await deleteSavedItem(savedItemId);
      setWorkspaceMessage("Reference removed from workspace.");
      await loadSavedItems();
    } catch (err) {
      setWorkspaceMessage(err instanceof Error ? err.message : "Could not remove reference.");
    }
  }

  function savedReferenceItemId(row: RelationshipRow) {
    return savedItems.find((item) => item.reference_id === row.id)?.id ?? null;
  }

  function exportReferences() {
    if (!focusId || lookupMode !== "act") {
      setError("Choose a focus Act before exporting.");
      return;
    }
    const token = getToken();
    if (!token) {
      setError("Login is required before exporting.");
      return;
    }
    fetch(exportUrl(`/exports/act/${focusId}/references.csv`), {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        if (!response.ok) throw new Error("Export failed.");
        return response.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "act-references.csv";
        link.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Export failed."));
  }

  const summary = relationships?.summary;
  const rows = relationships?.relationships ?? [];
  const canPageBack = offset > 0;
  const canPageForward = relationships
    ? offset + relationships.limit < relationships.total_results
    : false;
  const focusActRecord =
    focusAct ??
    (focusId ? acts.find((act) => act.id === focusId) ?? null : null);
  const focusLabel = focusActRecord
    ? displayActTitle(focusActRecord)
    : displayActTitle({
        title: graph?.nodes.find((node) => node.id === focusId)?.label,
        act_number: null,
        year: null,
        source_file_name: null
      });
  const focusSelectLabel = focusLabel || (focusId ? "Selected Act" : "");
  const focusSelectTitle = focusActRecord
    ? displayActTitleWithMeta(focusActRecord)
    : focusSelectLabel;
  const selectedConnections = rows.filter(
    (row) =>
      row.source_act_id === selectedNodeId ||
      row.target_act_id === selectedNodeId ||
      (!selectedNodeId && (row.source_act_id === focusId || row.target_act_id === focusId))
  );
  const panelNodeId = selectedNodeId ?? (lookupMode === "act" ? focusId : null);
  const panelAct =
    (panelNodeId && acts.find((act) => act.id === panelNodeId)) ||
    (panelNodeId === focusAct?.id ? focusAct : null) ||
    null;
  const panelLabel = panelAct
    ? displayActTitle(panelAct)
    : displayActTitle({
        title: graph?.nodes.find((node) => node.id === panelNodeId)?.label,
        act_number: null,
        year: null,
        source_file_name: null
      }) || focusLabel;
  const panelTitle = panelAct ? displayActTitleWithMeta(panelAct) : panelLabel;

  return (
    <RoleGuard allowed={["ADMIN", "LAWYER"]} path="/lawyer/relationships">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xl">
            <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">
              Relationship explorer
            </h1>
            <p className="mt-2 text-[14.5px] leading-[23px] text-muted-foreground">
              How Acts amend, repeal, insert into or refer to each other. Click a node to inspect it;
              double-click to refocus the graph.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex h-[34px] overflow-hidden rounded-md border border-border bg-card shadow-sm">
              <Button
                type="button"
                size="sm"
                variant={viewMode === "graph" ? "default" : "ghost"}
                className={cn("h-full rounded-none px-3 text-[12.5px]", viewMode === "graph" && "bg-primary")}
                onClick={() => setViewMode("graph")}
              >
                Graph
              </Button>
              <Button
                type="button"
                size="sm"
                variant={viewMode === "table" ? "default" : "ghost"}
                className={cn(
                  "h-full rounded-none border-l border-border px-3 text-[12.5px]",
                  viewMode === "table" && "bg-primary"
                )}
                onClick={() => setViewMode("table")}
              >
                Table
              </Button>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-[30px] gap-1.5 bg-card px-3 text-[12.5px]"
              onClick={exportReferences}
            >
              <Download className="size-3.5" />
              Export
            </Button>
          </div>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3 xl:flex-row xl:items-end">
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label className="text-xs font-semibold tracking-[0.12px] text-[#14263c]">Focus</Label>
            <Select
              value={lookupMode === "act" && focusId ? focusId : ""}
              onValueChange={(value) => {
                if (value) chooseFocus(value);
              }}
            >
              <SelectTrigger
                className="h-[34px] w-full min-w-0 rounded-md border-[#e4ddcd] bg-[#fffdf8]"
                title={focusSelectTitle || undefined}
              >
                <SelectValue
                  placeholder="Choose an Act to focus the graph"
                  className="min-w-0 truncate"
                >
                  {focusSelectLabel || undefined}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {acts.map((act) => (
                  <SelectItem key={act.id} value={act.id}>
                    {formatActOption(act)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full shrink-0 space-y-1.5 sm:w-[150px]">
            <Label className="text-xs font-semibold tracking-[0.12px] text-[#14263c]">Relationship</Label>
            <Select value={relationshipType} onValueChange={(value) => setRelationshipType(value ?? "ANY")}>
              <SelectTrigger className="h-[34px] w-full rounded-md border-[#e4ddcd] bg-[#fffdf8] *:data-[slot=select-value]:line-clamp-none *:data-[slot=select-value]:whitespace-nowrap">
                <SelectValue>{relationshipTypeLabel(relationshipType)}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ANY">All types</SelectItem>
                {RELATIONSHIP_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {formatType(type)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="w-full shrink-0 space-y-1.5 sm:w-[158px]">
            <Label className="text-xs font-semibold tracking-[0.12px] text-[#14263c]">Status</Label>
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter((value as StatusFilter) ?? "verified_pending")}
            >
              <SelectTrigger className="h-[34px] w-full rounded-md border-[#e4ddcd] bg-[#fffdf8] *:data-[slot=select-value]:line-clamp-none *:data-[slot=select-value]:whitespace-nowrap">
                <SelectValue>{statusFilterLabel(statusFilter)}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="verified_pending">Verified + pending</SelectItem>
                <SelectItem value="VERIFIED">Verified</SelectItem>
                <SelectItem value="PENDING">Pending</SelectItem>
                <SelectItem value="NEEDS_REVIEW">Needs review</SelectItem>
                <SelectItem value="REJECTED">Rejected</SelectItem>
                <SelectItem value="ANY">Any</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-full shrink-0 space-y-1.5 sm:w-[123px]">
            <Label className="text-xs font-semibold tracking-[0.12px] text-[#14263c]">Depth</Label>
            <div className="flex h-[34px] overflow-hidden rounded-md border border-[#e4ddcd] bg-card p-px shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
              <button
                type="button"
                data-slot="button"
                className={cn(
                  "flex h-full min-w-0 flex-1 items-center justify-center whitespace-nowrap px-2 text-[12.5px] font-medium leading-none",
                  depth === 1
                    ? "bg-primary text-primary-foreground"
                    : "bg-transparent text-muted-foreground hover:bg-muted/50"
                )}
                onClick={() => setDepth(1)}
              >
                1 hop
              </button>
              <button
                type="button"
                data-slot="button"
                className={cn(
                  "flex h-full min-w-0 flex-1 items-center justify-center whitespace-nowrap border-l border-[#e4ddcd] px-2 text-[12.5px] font-medium leading-none",
                  depth === 2
                    ? "bg-primary text-primary-foreground"
                    : "bg-transparent text-muted-foreground hover:bg-muted/50"
                )}
                onClick={() => setDepth(2)}
              >
                2 hops
              </button>
            </div>
          </div>
          <Button type="submit" disabled={loading} className="h-[34px] shrink-0 px-[15px] text-[13.5px]">
            {loading ? "Rendering…" : "Render"}
          </Button>
        </form>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {workspaceMessage ? <p className="text-sm text-muted-foreground">{workspaceMessage}</p> : null}

        {viewMode === "graph" ? (
          <div className="grid gap-[18px] xl:grid-cols-[minmax(0,1fr)_300px]">
            <RelationshipGraph
              nodes={graph?.nodes ?? []}
              edges={graph?.edges ?? []}
              focusId={lookupMode === "act" ? focusId : graph?.nodes[0]?.id}
              focusLabel={focusLabel}
              depth={graph?.depth ?? depth}
              unresolvedCount={graph?.summary.unresolved_count ?? summary?.unresolved_count ?? 0}
              hasRendered={Boolean(relationships)}
              statusFilter={statusFilter}
              totalResults={summary?.total_results ?? 0}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              onRefocusNode={(nodeId) => void refocusOnNode(nodeId)}
            />
            <SelectedNodePanel
              act={panelAct}
              label={panelLabel || "Select a node"}
              title={panelTitle}
              summary={summary}
              connections={selectedConnections.slice(0, 6)}
              hasFocus={Boolean(panelNodeId)}
              onOpenAct={panelNodeId ? `/acts/${panelNodeId}` : null}
              onExpand={() => void expandOneHop()}
              expandDisabled={depth === 2 || loading || !focusId}
            />
          </div>
        ) : null}

        {viewMode === "table" ? (
          <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <h2 className="font-serif text-lg font-semibold">Relationship table</h2>
            {loading ? <p className="mt-3 text-sm text-muted-foreground">Loading relationships...</p> : null}
            {!loading && relationships && !rows.length ? (
              <div className="mt-3 rounded-md border border-dashed border-border bg-background px-4 py-8 text-sm text-muted-foreground">
                No verified relationships are available yet.
              </div>
            ) : null}
            {rows.length ? (
              <RelationshipTable
                rows={rows}
                getSavedItemId={savedReferenceItemId}
                onSave={saveRelationship}
                onUnsave={unsaveRelationship}
              />
            ) : null}
            {relationships ? (
              <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
                <span>
                  Showing {relationships.offset + 1}-{relationships.offset + rows.length} of{" "}
                  {relationships.total_results}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!canPageBack || loading}
                  onClick={() =>
                    void loadRelationships(
                      lookupMode,
                      focusId,
                      Math.max(0, offset - relationships.limit),
                      depth
                    )
                  }
                >
                  Previous page
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!canPageForward || loading}
                  onClick={() => void loadRelationships(lookupMode, focusId, offset + relationships.limit, depth)}
                >
                  Next page
                </Button>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </RoleGuard>
  );
}

function SelectedNodePanel({
  act,
  label,
  title,
  summary,
  connections,
  hasFocus,
  onOpenAct,
  onExpand,
  expandDisabled
}: Readonly<{
  act: LegalAct | null;
  label: string;
  title: string;
  summary: RelationshipListResponse["summary"] | undefined;
  connections: RelationshipRow[];
  hasFocus: boolean;
  onOpenAct: string | null;
  onExpand: () => void;
  expandDisabled: boolean;
}>) {
  const verified = !connections.some((row) => row.verification_status !== "VERIFIED");
  return (
    <aside className="flex flex-col gap-4">
      <p className="text-[11px] font-semibold tracking-[1.1px] text-[#92681f] uppercase">Selected node</p>
      <div className="rounded-lg border border-border bg-card px-5 py-5 shadow-sm">
        {!hasFocus ? (
          <p className="text-sm text-muted-foreground">Choose an Act and render to inspect a node.</p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
                  verified
                    ? "border-[#cfe0d4] bg-[#ebf3ee] text-[#22684a]"
                    : "border-[#e6d8b4] bg-[#f6ebd4] text-[#92681f]"
                )}
              >
                <span
                  className={cn("size-1.5 rounded-[3px]", verified ? "bg-[#22684a]" : "bg-[#92681f]")}
                  aria-hidden
                />
                {verified ? "Verified" : "Pending"}
              </span>
              <span className="rounded-[5px] bg-[#e2e9f0] px-2 py-0.5 text-[11px] font-semibold tracking-wide text-[#1e3a5f]">
                Act
              </span>
            </div>
            <h2
              className="mt-2 line-clamp-3 font-serif text-[15.5px] font-bold leading-snug text-[#14263c]"
              title={title}
            >
              {label}
            </h2>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {actMetaLine(act)}
            </p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <StatChip value={summary?.total_results ?? 0} label="References" />
              <StatChip value={summary?.outgoing_count ?? 0} label="Outgoing" />
              <StatChip value={summary?.incoming_count ?? 0} label="Incoming" />
            </div>
            <div className="mt-3 flex gap-2">
              {onOpenAct ? (
                <Button
                  size="sm"
                  className="h-[30px] flex-1 text-[12.5px]"
                  render={<Link href={onOpenAct} />}
                  nativeButton={false}
                >
                  Open Act
                </Button>
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-[30px] flex-1 bg-card text-[12.5px]"
                disabled={expandDisabled}
                onClick={onExpand}
              >
                ＋ Expand 1 hop
              </Button>
            </div>
          </>
        )}
      </div>

      <p className="text-[11px] font-semibold tracking-[1.1px] text-[#92681f] uppercase">Connections</p>
      <div className="rounded-lg border border-border bg-card px-4 py-2 shadow-sm">
        {!connections.length ? (
          <p className="px-1 py-3 text-sm text-muted-foreground">No connections for this node yet.</p>
        ) : (
          connections.map((row) => <ConnectionRow key={row.id} row={row} />)
        )}
      </div>

      <div className="rounded-lg border border-[#ede8db] bg-[#f4ead6] px-4 py-3 text-[13px] leading-5 text-[#5c4a22]">
        Dashed nodes and edges are <strong>pending</strong> — machine-extracted, awaiting admin
        verification. Double-click any node to refocus the graph on it.
      </div>
    </aside>
  );
}

function StatChip({ value, label }: Readonly<{ value: number; label: string }>) {
  return (
    <div className="rounded-md border border-[#ede8db] bg-[#fffdf8] px-2.5 py-2 text-center">
      <p className="text-base font-semibold text-[#0b1626]">{value}</p>
      <p className="text-[10.5px] text-muted-foreground">{label}</p>
    </div>
  );
}

function ConnectionRow({ row }: Readonly<{ row: RelationshipRow }>) {
  const outgoing = row.direction === "outgoing";
  const targetLabel = connectionLabel(row, outgoing);
  return (
    <div className="flex items-center gap-2 border-b border-[#ede8db] px-1 py-2.5 last:border-b-0">
      <span
        className={cn(
          "rounded px-1.5 text-[10px] font-semibold tracking-wide",
          outgoing ? "bg-[#f3e4e6] text-[#8c2433]" : "bg-[#e4ede7] text-[#22684a]"
        )}
      >
        {outgoing ? "OUT" : "IN"}
      </span>
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11.5px] font-semibold",
          typePillClass(row.relationship_type)
        )}
      >
        <span aria-hidden>◆</span>
        {formatType(row.relationship_type)}
      </span>
      <span className="min-w-0 flex-1 truncate text-[12.5px] text-[#14263c]" title={targetLabel}>
        {targetLabel}
      </span>
      <span className="text-[11.5px] text-muted-foreground">{row.confidence_score.toFixed(2)}</span>
    </div>
  );
}

function RelationshipTable({
  rows,
  getSavedItemId,
  onSave,
  onUnsave
}: Readonly<{
  rows: RelationshipRow[];
  getSavedItemId: (row: RelationshipRow) => string | null;
  onSave: (row: RelationshipRow) => void | Promise<void>;
  onUnsave: (savedItemId: string) => void | Promise<void>;
}>) {
  return (
    <div className="table-wrap mt-3">
      <table>
        <thead>
          <tr>
            <th>Direction</th>
            <th>Source</th>
            <th>Relationship</th>
            <th>Target</th>
            <th>Evidence</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Workspace</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const savedItemId = getSavedItemId(row);
            return (
              <tr key={row.id}>
                <td>
                  <StatusBadge value={row.direction} />
                </td>
                <td>
                  <Link
                    href={
                      row.source_section_id
                        ? `/sections/${row.source_section_id}`
                        : `/acts/${row.source_act_id}`
                    }
                  >
                    {row.source_act_title ?? row.source_act_id}
                  </Link>
                  {row.source_section_number ? (
                    <div className="muted">
                      Section {row.source_section_number}: {row.source_section_heading ?? "Untitled"}
                    </div>
                  ) : null}
                </td>
                <td>
                  <StatusBadge value={row.relationship_type} />
                </td>
                <td>
                  {row.target_section_id ? (
                    <Link href={`/sections/${row.target_section_id}`}>
                      {row.target_act_title ?? "Mapped target"} section {row.target_section_number ?? "-"}
                    </Link>
                  ) : row.target_act_id ? (
                    <Link href={`/acts/${row.target_act_id}`}>
                      {row.target_act_title ?? row.target_act_id}
                    </Link>
                  ) : (
                    <span>{row.target_act_title_raw ?? "Target unresolved"}</span>
                  )}
                  {row.target_act_number || row.target_act_year ? (
                    <div className="muted">
                      Act No. {row.target_act_number ?? "-"}{" "}
                      {row.target_act_year ? `of ${row.target_act_year}` : ""}
                    </div>
                  ) : null}
                  {row.target_section_path ? (
                    <div className="muted">Target path: {row.target_section_path}</div>
                  ) : null}
                  <StatusBadge value={row.mapped ? "MAPPED" : "UNRESOLVED"} />
                </td>
                <td>
                  <strong>{row.raw_reference_text}</strong>
                  <p className="muted">{row.context_snippet}</p>
                </td>
                <td>{Math.round(row.confidence_score * 100)}%</td>
                <td>
                  <StatusBadge value={row.verification_status} />
                </td>
                <td>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      if (savedItemId) {
                        void onUnsave(savedItemId);
                      } else {
                        void onSave(row);
                      }
                    }}
                  >
                    {savedItemId ? "Unsave from workspace" : "Save reference"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function formatActOption(act: LegalAct) {
  return displayActTitleWithMeta(act);
}

function relationshipTypeLabel(value: string) {
  if (value === "ANY") return "All types";
  return formatType(value);
}

function statusFilterLabel(value: StatusFilter) {
  if (value === "verified_pending") return "Verified + pending";
  if (value === "VERIFIED") return "Verified";
  if (value === "PENDING") return "Pending";
  if (value === "NEEDS_REVIEW") return "Needs review";
  if (value === "REJECTED") return "Rejected";
  return "Any";
}

function formatType(type: string) {
  return type
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^\w/, (char) => char.toUpperCase());
}

function actMetaLine(act: LegalAct | null) {
  if (!act) return "Mapped focus node";
  const parts = [
    act.certification_date ? `Certified ${formatDate(act.certification_date)}` : null,
    act.parser_used || null,
    act.page_count ? `${act.page_count} pages` : null
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Mapped focus node";
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function connectionLabel(row: RelationshipRow, outgoing: boolean) {
  if (outgoing) {
    if (row.target_section_number) {
      return `${shortTitle(row.target_act_title)} s.${row.target_section_number}`;
    }
    return row.target_act_title ?? row.target_act_title_raw ?? "Unresolved target";
  }
  if (row.source_section_number) {
    return `${shortTitle(row.source_act_title)} s.${row.source_section_number}`;
  }
  return row.source_act_title ?? row.source_act_id;
}

function shortTitle(title: string | null) {
  const readable = displayActTitle({ title, act_number: null, year: null, source_file_name: null });
  return readable.length > 22 ? `${readable.slice(0, 20)}…` : readable;
}

function typePillClass(type: string) {
  if (type.includes("AMEND") || type.includes("REPEAL")) {
    return "border-[#e3c3c8] bg-[#fbf3f4] text-[#8c2433]";
  }
  if (type.includes("INSERT") || type.includes("ADD")) {
    return "border-[#cfe0d4] bg-[#ebf3ee] text-[#22684a]";
  }
  return "border-[#c8d5e2] bg-[#f0f4f8] text-[#1e3a5f]";
}
