"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  createSavedItem,
  deleteSavedItem,
  exportUrl,
  listSavedItems,
  updateSavedItem
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { SavedItem, SavedItemType } from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

type ItemFilter = "ALL" | SavedItemType;

const ITEM_TYPES: SavedItemType[] = ["ACT", "SECTION", "REFERENCE"];

export default function LawyerWorkspacePage() {
  const [items, setItems] = useState<SavedItem[]>([]);
  const [counts, setCounts] = useState<Record<SavedItemType, number>>({
    ACT: 0,
    SECTION: 0,
    REFERENCE: 0
  });
  const [totalResults, setTotalResults] = useState(0);
  const [itemType, setItemType] = useState<ItemFilter>("ALL");
  const [actId, setActId] = useState("");
  const [relationshipType, setRelationshipType] = useState("");
  const [verificationStatus, setVerificationStatus] = useState("");
  const [mappedStatus, setMappedStatus] = useState("");
  const [limit, setLimit] = useState("25");
  const [offset, setOffset] = useState(0);
  const [manualType, setManualType] = useState<SavedItemType>("SECTION");
  const [manualId, setManualId] = useState("");
  const [manualNote, setManualNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void load(0);
  }, []);

  async function load(nextOffset = offset) {
    setLoading(true);
    setError("");
    try {
      const response = await listSavedItems({
        ...(itemType !== "ALL" ? { item_type: itemType } : {}),
        ...(actId.trim() ? { act_id: actId.trim() } : {}),
        ...(relationshipType ? { relationship_type: relationshipType } : {}),
        ...(verificationStatus ? { verification_status: verificationStatus } : {}),
        ...(mappedStatus ? { mapped_status: mappedStatus } : {}),
        limit,
        offset: String(nextOffset)
      });
      setItems(response.items);
      setCounts(response.counts_by_type);
      setTotalResults(response.total_results);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function applyFilters(event: FormEvent) {
    event.preventDefault();
    await load(0);
  }

  async function submitManualSave(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    const payload = {
      item_type: manualType,
      act_id: manualType === "ACT" ? manualId.trim() : null,
      section_id: manualType === "SECTION" ? manualId.trim() : null,
      reference_id: manualType === "REFERENCE" ? manualId.trim() : null,
      note: manualNote.trim() || null
    };
    try {
      await createSavedItem(payload);
      setManualId("");
      setManualNote("");
      setMessage("Saved item added to workspace.");
      await load(0);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Could not save item.";
      setError(text.includes("already saved") ? "Already saved in workspace." : text);
    }
  }

  async function saveNote(itemId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");
    const formData = new FormData(event.currentTarget);
    try {
      await updateSavedItem(itemId, {
        note: String(formData.get("note") ?? "").trim() || null
      });
      setMessage("Workspace note updated.");
      await load(offset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update note.");
    }
  }

  async function unsave(itemId: string) {
    setMessage("");
    setError("");
    try {
      await deleteSavedItem(itemId);
      setMessage("Saved item removed.");
      await load(Math.max(0, items.length === 1 ? offset - Number(limit) : offset));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove saved item.");
    }
  }

  function exportWithToken(path: string) {
    const token = getToken();
    if (!token) {
      setError("Login is required before exporting workspace data.");
      return;
    }
    fetch(exportUrl(path), { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (!response.ok) throw new Error("Export failed.");
        return response.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = path.endsWith(".csv") ? "saved-items.csv" : "saved-items.md";
        link.click();
        URL.revokeObjectURL(url);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Export failed."));
  }

  const canPageBack = offset > 0;
  const canPageForward = offset + Number(limit) < totalResults;

  return (
    <RoleGuard allowed={["ADMIN", "LAWYER"]} path="/lawyer/workspace">
      <div className="grid">
        <LegalDisclaimer />
        <section className="panel">
          <h1>Lawyer workspace</h1>
          <p className="muted">
            Organize saved research results only. This workspace does not provide legal advice or legal opinions.
          </p>
          <div className="toolbar">
            <span>Saved Acts: {counts.ACT}</span>
            <span>Saved Sections: {counts.SECTION}</span>
            <span>Saved References: {counts.REFERENCE}</span>
            <span>Total shown: {totalResults}</span>
          </div>
          <div className="toolbar">
            <button type="button" className="secondary" onClick={() => exportWithToken("/exports/saved-items.csv")}>
              Export CSV
            </button>
            <button type="button" className="secondary" onClick={() => exportWithToken("/exports/saved-items.md")}>
              Export Markdown
            </button>
          </div>
        </section>

        <form className="panel" onSubmit={applyFilters}>
          <h2>Workspace filters</h2>
          <div className="toolbar">
            <div className="field">
              <label htmlFor="itemType">Type</label>
              <select id="itemType" value={itemType} onChange={(event) => setItemType(event.target.value as ItemFilter)}>
                <option value="ALL">All</option>
                {ITEM_TYPES.map((type) => <option key={type}>{type}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="actId">Act ID</label>
              <input id="actId" value={actId} onChange={(event) => setActId(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="relationship">Relationship type</label>
              <select id="relationship" value={relationshipType} onChange={(event) => setRelationshipType(event.target.value)}>
                <option value="">Any</option>
                <option>REFERS_TO</option>
                <option>AMENDS</option>
                <option>REPEALS</option>
                <option>INSERTS</option>
                <option>SUBSTITUTES</option>
                <option>ADDS</option>
                <option>CROSS_REFERENCE</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="verification">Verification status</label>
              <select id="verification" value={verificationStatus} onChange={(event) => setVerificationStatus(event.target.value)}>
                <option value="">Any</option>
                <option>VERIFIED</option>
                <option>PENDING</option>
                <option>NEEDS_REVIEW</option>
                <option>REJECTED</option>
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
            <button type="submit" disabled={loading}>{loading ? "Loading..." : "Apply filters"}</button>
          </div>
        </form>

        <form className="panel" onSubmit={submitManualSave}>
          <h2>Manual save</h2>
          <div className="toolbar">
            <div className="field">
              <label htmlFor="manualType">Item type</label>
              <select id="manualType" value={manualType} onChange={(event) => setManualType(event.target.value as SavedItemType)}>
                {ITEM_TYPES.map((type) => <option key={type}>{type}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="manualId">{manualType === "ACT" ? "Act ID" : manualType === "SECTION" ? "Section ID" : "Reference ID"}</label>
              <input id="manualId" value={manualId} onChange={(event) => setManualId(event.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="manualNote">Private note</label>
              <input id="manualNote" value={manualNote} onChange={(event) => setManualNote(event.target.value)} />
            </div>
            <button type="submit">Save item</button>
          </div>
        </form>

        {message ? <p className="muted">{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {loading ? <p>Loading workspace...</p> : null}
        {!loading && !items.length ? <div className="empty">No saved research items match these filters.</div> : null}

        {ITEM_TYPES.map((type) => (
          <SavedItemGroup
            key={type}
            type={type}
            items={items.filter((item) => item.item_type === type)}
            onSaveNote={saveNote}
            onUnsave={unsave}
          />
        ))}

        {totalResults ? (
          <div className="toolbar">
            <span>Showing {offset + 1}-{offset + items.length} of {totalResults}</span>
            <button type="button" disabled={!canPageBack || loading} onClick={() => load(Math.max(0, offset - Number(limit)))}>
              Previous page
            </button>
            <button type="button" disabled={!canPageForward || loading} onClick={() => load(offset + Number(limit))}>
              Next page
            </button>
          </div>
        ) : null}
      </div>
    </RoleGuard>
  );
}

function SavedItemGroup({
  type,
  items,
  onSaveNote,
  onUnsave
}: {
  type: SavedItemType;
  items: SavedItem[];
  onSaveNote: (itemId: string, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUnsave: (itemId: string) => Promise<void>;
}) {
  if (!items.length) return null;
  return (
    <section className="panel">
      <h2>Saved {type.toLowerCase()}s</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Act / Section</th>
              <th>Relationship</th>
              <th>Status</th>
              <th>Private note</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link href={itemLink(item)}>{item.item_title ?? item.id}</Link>
                  <div className="muted">{item.created_at ? `Saved ${new Date(item.created_at).toLocaleDateString()}` : ""}</div>
                </td>
                <td>
                  <div>{item.act_title ?? "Act unavailable"}</div>
                  {item.act_number || item.year ? (
                    <div className="muted">Act No. {item.act_number ?? "-"} {item.year ? `of ${item.year}` : ""}</div>
                  ) : null}
                  {item.section_number ? (
                    <div className="muted">Section {item.section_number}: {item.section_heading ?? "Untitled"}</div>
                  ) : null}
                </td>
                <td>
                  {item.relationship_type ? <StatusBadge value={item.relationship_type} /> : <span className="muted">Not a reference</span>}
                  {item.target_act_title ? <div className="muted">Target: {item.target_act_title}</div> : null}
                  {item.mapped !== null ? <StatusBadge value={item.mapped ? "MAPPED" : "UNRESOLVED"} /> : null}
                </td>
                <td>
                  {item.verification_status ? <StatusBadge value={item.verification_status} /> : null}
                  {item.processing_status ? <StatusBadge value={item.processing_status} /> : null}
                </td>
                <td>
                  <form className="toolbar" onSubmit={(event) => onSaveNote(item.id, event)}>
                    <input name="note" defaultValue={item.note ?? ""} aria-label={`Note for ${item.item_title ?? item.id}`} />
                    <button type="submit" className="secondary">Save note</button>
                  </form>
                </td>
                <td>
                  <div className="toolbar">
                    {item.reference_id ? (
                      <Link className="button secondary" href={`/lawyer/relationships?actId=${item.act_id ?? ""}`}>
                        Open relationships
                      </Link>
                    ) : null}
                    <button type="button" className="danger" onClick={() => void onUnsave(item.id)}>
                      Unsave
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function itemLink(item: SavedItem) {
  if (item.item_type === "SECTION" && item.section_id) return `/sections/${item.section_id}`;
  if (item.item_type === "ACT" && item.act_id) return `/acts/${item.act_id}`;
  if (item.reference_id && item.act_id) return `/lawyer/relationships?actId=${item.act_id}`;
  return "/lawyer/workspace";
}
