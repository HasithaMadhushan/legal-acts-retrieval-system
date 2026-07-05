"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  createSavedItem,
  deleteSavedItem,
  getActRelationships,
  getRelationshipGraph,
  getSectionRelationships,
  listSavedItems
} from "@/lib/api";
import type {
  RelationshipGraphResponse,
  RelationshipListResponse,
  RelationshipRow,
  RelationshipType,
  SavedItem,
  VerificationStatus
} from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RelationshipGraph } from "@/components/relationship-graph";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

type LookupMode = "act" | "section";

export default function LawyerRelationshipsPage() {
  const [lookupMode, setLookupMode] = useState<LookupMode>("act");
  const [lookupId, setLookupId] = useState("");
  const [direction, setDirection] = useState("all");
  const [relationshipType, setRelationshipType] = useState("");
  const [verificationStatus, setVerificationStatus] = useState("");
  const [mappedStatus, setMappedStatus] = useState("");
  const [limit, setLimit] = useState("25");
  const [offset, setOffset] = useState(0);
  const [relationships, setRelationships] = useState<RelationshipListResponse | null>(null);
  const [graph, setGraph] = useState<RelationshipGraphResponse | null>(null);
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadSavedItems();
    const params = new URLSearchParams(window.location.search);
    const actId = params.get("actId");
    const sectionId = params.get("sectionId");
    if (sectionId) {
      setLookupMode("section");
      setLookupId(sectionId);
      void loadRelationships("section", sectionId, 0);
    } else if (actId) {
      setLookupMode("act");
      setLookupId(actId);
      void loadRelationships("act", actId, 0);
    }
  }, []);

  async function loadSavedItems() {
    try {
      const data = await listSavedItems({ item_type: "REFERENCE", limit: "100", offset: "0" });
      setSavedItems(data.items);
    } catch {
      setSavedItems([]);
    }
  }

  function queryParams(nextOffset: number) {
    return {
      ...(direction ? { direction } : {}),
      ...(relationshipType ? { relationship_type: relationshipType } : {}),
      ...(verificationStatus ? { verification_status: verificationStatus } : {}),
      ...(mappedStatus ? { mapped_status: mappedStatus } : {}),
      limit,
      offset: String(nextOffset)
    };
  }

  async function loadRelationships(
    mode: LookupMode = lookupMode,
    id: string = lookupId,
    nextOffset = 0
  ) {
    if (!id.trim()) return;
    setError("");
    setLoading(true);
    try {
      const params = queryParams(nextOffset);
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Relationship lookup failed.");
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await loadRelationships(lookupMode, lookupId, 0);
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

  const summary = relationships?.summary;
  const rows = relationships?.relationships ?? [];
  const canPageBack = offset > 0;
  const canPageForward = relationships
    ? offset + relationships.limit < relationships.total_results
    : false;

  return (
    <RoleGuard allowed={["ADMIN", "LAWYER"]} path="/lawyer/relationships">
      <div className="grid">
        <LegalDisclaimer />
        <form className="panel" onSubmit={submit}>
          <h1>Relationship explorer</h1>
          <p className="muted">
            Relationship views are generated from extracted and mapped references only.
          </p>
          <div className="toolbar">
            <div className="field">
              <label htmlFor="lookupMode">Lookup mode</label>
              <select id="lookupMode" value={lookupMode} onChange={(event) => setLookupMode(event.target.value as LookupMode)}>
                <option value="act">Act relationships</option>
                <option value="section">Section relationships</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="lookupId">{lookupMode === "act" ? "Act ID" : "Section ID"}</label>
              <input id="lookupId" value={lookupId} onChange={(event) => setLookupId(event.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="direction">Direction</label>
              <select id="direction" value={direction} onChange={(event) => setDirection(event.target.value)}>
                <option value="all">All directions</option>
                <option value="outgoing">Outgoing</option>
                <option value="incoming">Incoming</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="relationship">Relationship type</label>
              <select id="relationship" value={relationshipType} onChange={(event) => setRelationshipType(event.target.value)}>
                <option value="">Any</option>
                {(["REFERS_TO", "AMENDS", "REPEALS", "INSERTS", "SUBSTITUTES", "ADDS", "CROSS_REFERENCE"] satisfies RelationshipType[]).map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="verification">Verification status</label>
              <select id="verification" value={verificationStatus} onChange={(event) => setVerificationStatus(event.target.value)}>
                <option value="">Any</option>
                {(["PENDING", "NEEDS_REVIEW", "VERIFIED", "REJECTED"] satisfies VerificationStatus[]).map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="mapped">Mapped status</label>
              <select id="mapped" value={mappedStatus} onChange={(event) => setMappedStatus(event.target.value)}>
                <option value="">Any</option>
                <option value="mapped">Mapped</option>
                <option value="unresolved">Unresolved</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="limit">Page size</label>
              <select id="limit" value={limit} onChange={(event) => setLimit(event.target.value)}>
                <option value="10">10</option>
                <option value="25">25</option>
                <option value="50">50</option>
              </select>
            </div>
            <button type="submit" disabled={loading}>{loading ? "Loading..." : "Load relationships"}</button>
          </div>
          {error ? <p className="error">{error}</p> : null}
          {workspaceMessage ? <p className="muted">{workspaceMessage}</p> : null}
        </form>

        {summary ? <RelationshipSummaryPanel summary={summary} /> : null}
        <RelationshipGraph
          nodes={graph?.nodes ?? []}
          edges={graph?.edges ?? []}
          unresolvedCount={graph?.summary.unresolved_count ?? summary?.unresolved_count ?? 0}
        />
        <section className="panel">
          <h2>Relationship table</h2>
          {loading ? <p>Loading relationships...</p> : null}
          {!loading && relationships && !rows.length ? (
            <div className="empty">No verified relationships are available yet.</div>
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
            <div className="toolbar">
              <span>
                Showing {relationships.offset + 1}-{relationships.offset + rows.length} of {relationships.total_results}
              </span>
              <button type="button" disabled={!canPageBack || loading} onClick={() => loadRelationships(lookupMode, lookupId, Math.max(0, offset - relationships.limit))}>
                Previous page
              </button>
              <button type="button" disabled={!canPageForward || loading} onClick={() => loadRelationships(lookupMode, lookupId, offset + relationships.limit)}>
                Next page
              </button>
            </div>
          ) : null}
        </section>
      </div>
    </RoleGuard>
  );
}

function RelationshipSummaryPanel({ summary }: { summary: RelationshipListResponse["summary"] }) {
  return (
    <section className="panel">
      <h2>Relationship summary</h2>
      <div className="toolbar">
        <span>Outgoing: {summary.outgoing_count}</span>
        <span>Incoming: {summary.incoming_count}</span>
        <span>Mapped: {summary.mapped_count}</span>
        <span>Unresolved: {summary.unresolved_count}</span>
      </div>
      <p className="muted">
        By type: {formatCounts(summary.by_relationship_type)}
      </p>
      <p className="muted">
        By verification status: {formatCounts(summary.by_verification_status)}
      </p>
    </section>
  );
}

function RelationshipTable({
  rows,
  getSavedItemId,
  onSave,
  onUnsave
}: {
  rows: RelationshipRow[];
  getSavedItemId: (row: RelationshipRow) => string | null;
  onSave: (row: RelationshipRow) => void | Promise<void>;
  onUnsave: (savedItemId: string) => void | Promise<void>;
}) {
  return (
    <div className="table-wrap">
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
              <td><StatusBadge value={row.direction} /></td>
              <td>
                <Link href={row.source_section_id ? `/sections/${row.source_section_id}` : `/acts/${row.source_act_id}`}>
                  {row.source_act_title ?? row.source_act_id}
                </Link>
                {row.source_section_number ? (
                  <div className="muted">Section {row.source_section_number}: {row.source_section_heading ?? "Untitled"}</div>
                ) : null}
              </td>
              <td><StatusBadge value={row.relationship_type} /></td>
              <td>
                {row.target_section_id ? (
                  <Link href={`/sections/${row.target_section_id}`}>
                    {row.target_act_title ?? "Mapped target"} section {row.target_section_number ?? "-"}
                  </Link>
                ) : row.target_act_id ? (
                  <Link href={`/acts/${row.target_act_id}`}>{row.target_act_title ?? row.target_act_id}</Link>
                ) : (
                  <span>{row.target_act_title_raw ?? "Target unresolved"}</span>
                )}
                {row.target_act_number || row.target_act_year ? (
                  <div className="muted">Act No. {row.target_act_number ?? "-"} {row.target_act_year ? `of ${row.target_act_year}` : ""}</div>
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
              <td><StatusBadge value={row.verification_status} /></td>
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

function formatCounts(values: Record<string, number>) {
  const entries = Object.entries(values);
  if (!entries.length) return "None";
  return entries.map(([key, value]) => `${key}: ${value}`).join(", ");
}
