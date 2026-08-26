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
import { RelationshipDossier } from "@/components/relationship-dossier";
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
import { graphEdgeKey, type GraphEdgeSelection } from "@/lib/graph-edges";
import { otherActId } from "@/lib/linked-acts";
import {
  buildRelationshipDossier,
  dossierGroupKeyFromEdge,
  dossierKeyForAct
} from "@/lib/relationship-dossier";
import { fetchAllRelationshipRows } from "@/lib/relationship-pages";
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
  const [dossierRows, setDossierRows] = useState<RelationshipRow[]>([]);
  const [graph, setGraph] = useState<RelationshipGraphResponse | null>(null);
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdgeSelection | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
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

  function filterParams() {
    return {
      ...(relationshipType !== "ANY" ? { relationship_type: relationshipType } : {}),
      ...(statusFilter !== "verified_pending" && statusFilter !== "ANY"
        ? { verification_status: statusFilter }
        : {})
    };
  }

  function queryParams(nextOffset: number, nextDepth: number) {
    return {
      ...filterParams(),
      limit,
      offset: String(nextOffset),
      depth: String(nextDepth)
    };
  }

  async function loadListPage(mode: LookupMode, id: string, offset: number, pageLimit: number) {
    const params = { ...filterParams(), limit: String(pageLimit), offset: String(offset) };
    return mode === "act"
      ? getActRelationships(id, params)
      : getSectionRelationships(id, params);
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
      const trimmedId = id.trim();
      const params = queryParams(nextOffset, nextDepth);
      const [graphData, catalog] = await Promise.all([
        getRelationshipGraph({
          ...params,
          ...(mode === "act" ? { act_id: trimmedId } : { section_id: trimmedId })
        }),
        fetchAllRelationshipRows((pageOffset, pageLimit) =>
          loadListPage(mode, trimmedId, pageOffset, pageLimit)
        )
      ]);
      const tableLimit = Number(limit);
      setRelationships({
        ...catalog.list,
        relationships: catalog.rows.slice(nextOffset, nextOffset + tableLimit),
        limit: tableLimit,
        offset: nextOffset
      });
      setDossierRows(catalog.rows);
      setGraph(graphData);
      setOffset(nextOffset);
      setSelectedNodeId(mode === "act" ? trimmedId : graphData.nodes[0]?.id ?? null);
      setSelectedEdge(null);
      setExpandedKey(null);
      if (mode === "act") {
        try {
          setFocusAct(await getAct(trimmedId));
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
  const tableLimit = Number(limit);
  const rows = dossierRows.slice(offset, offset + tableLimit);
  const canPageBack = offset > 0;
  const canPageForward = offset + tableLimit < dossierRows.length;
  const focusActRecord =
    focusAct ??
    (focusId ? acts.find((act) => act.id === focusId) ?? null : null);
  const focusLabel = !focusId
    ? ""
    : focusActRecord
      ? displayActTitle(focusActRecord)
      : displayActTitle({
          title: graph?.nodes.find((node) => node.id === focusId)?.label,
          act_number: null,
          year: null,
          source_file_name: null
        });
  const focusSelectLabel = focusId ? focusLabel || "Selected Act" : "";
  const focusSelectTitle = focusActRecord
    ? displayActTitleWithMeta(focusActRecord)
    : focusSelectLabel;
  const dossierFocusId = lookupMode === "act" ? focusId : graph?.nodes[0]?.id ?? "";
  const dossierSections = buildRelationshipDossier(dossierRows, dossierFocusId);

  return (
    <RoleGuard allowed={["ADMIN", "LAWYER"]} path="/lawyer/relationships">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xl">
            <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">
              Relationship explorer
            </h1>
            <p className="mt-2 text-[14.5px] leading-[23px] text-muted-foreground">
              The map is an overview. Citations are grouped on the right by type, then by Act. Click a linked Act or a line to open that group; double-click a node to make it the focus.
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
          <div className="grid items-start gap-[18px] xl:grid-cols-[minmax(0,1fr)_minmax(380px,1fr)]">
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
              selectedEdgeKey={selectedEdge ? graphEdgeKey(selectedEdge) : null}
              onSelectNode={(nodeId) => {
                setSelectedEdge(null);
                setSelectedNodeId(nodeId);
                setExpandedKey(
                  nodeId === dossierFocusId ? null : dossierKeyForAct(dossierSections, nodeId)
                );
              }}
              onSelectEdge={(edge) => {
                setSelectedEdge(edge);
                setSelectedNodeId(otherActId(edge, dossierFocusId) ?? edge.target);
                setExpandedKey(dossierGroupKeyFromEdge(dossierFocusId, edge));
              }}
              onRefocusNode={(nodeId) => void refocusOnNode(nodeId)}
            />
            <RelationshipDossier
              focusLabel={focusLabel}
              focusTitle={focusSelectTitle}
              focusAct={focusActRecord}
              summary={summary}
              sections={dossierSections}
              hasRendered={Boolean(relationships)}
              loading={loading}
              expandedKey={expandedKey}
              onToggleGroup={(key) => {
                setExpandedKey((current) => (current === key ? null : key));
                const group = dossierSections
                  .flatMap((section) => section.groups)
                  .find((entry) => entry.key === key);
                if (group?.counterpartId) {
                  setSelectedEdge(null);
                  setSelectedNodeId(group.counterpartId);
                }
              }}
              onOpenTable={() => setViewMode("table")}
              onRefocusAct={(actId) => void refocusOnNode(actId)}
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
                  Showing {offset + 1}-{offset + rows.length} of {dossierRows.length}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!canPageBack || loading}
                  onClick={() => setOffset(Math.max(0, offset - tableLimit))}
                >
                  Previous page
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!canPageForward || loading}
                  onClick={() => setOffset(offset + tableLimit)}
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

