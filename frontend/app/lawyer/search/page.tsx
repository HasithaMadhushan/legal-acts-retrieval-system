"use client";

import { FormEvent, useEffect, useState } from "react";
import { createSavedItem, deleteSavedItem, listSavedItems, search } from "@/lib/api";
import { containsAdviceIntent } from "@/lib/auth";
import type { SavedItem, SavedItemCreatePayload, SearchResponse, SearchResult } from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { SearchResults } from "@/components/search-results";

export default function LawyerSearchPage() {
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [actNumber, setActNumber] = useState("");
  const [category, setCategory] = useState("");
  const [processingStatus, setProcessingStatus] = useState("");
  const [relationshipType, setRelationshipType] = useState("");
  const [verificationStatus, setVerificationStatus] = useState("");
  const [mappedStatus, setMappedStatus] = useState("");
  const [limit, setLimit] = useState("25");
  const [offset, setOffset] = useState(0);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [error, setError] = useState("");
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadSavedItems();
  }, []);

  async function loadSavedItems() {
    try {
      const data = await listSavedItems({ limit: "100", offset: "0" });
      setSavedItems(data.items);
    } catch {
      setSavedItems([]);
    }
  }

  async function runSearch(nextOffset = 0) {
    setError("");
    const trimmedQuery = query.trim();
    if (containsAdviceIntent(trimmedQuery)) {
      setError("No legal advice or legal opinions can be generated. Use retrieval terms only.");
      return;
    }
    setLoading(true);
    try {
      const data = await search(trimmedQuery, {
        ...(year ? { year } : {}),
        ...(actNumber ? { act_number: actNumber } : {}),
        ...(category ? { category } : {}),
        ...(processingStatus ? { processing_status: processingStatus } : {}),
        ...(relationshipType ? { relationship_type: relationshipType } : {}),
        ...(verificationStatus ? { verification_status: verificationStatus } : {}),
        ...(mappedStatus ? { mapped_status: mappedStatus } : {}),
        limit,
        offset: String(nextOffset)
      });
      setResponse(data);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function saveResult(result: SearchResult) {
    const payload = payloadForSearchResult(result);
    if (!payload) {
      setWorkspaceMessage("This result cannot be saved yet.");
      return;
    }
    setWorkspaceMessage("");
    try {
      await createSavedItem(payload);
      setWorkspaceMessage("Saved to workspace.");
      await loadSavedItems();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not save result.";
      setWorkspaceMessage(message.includes("already saved") ? "Already saved in workspace." : message);
      await loadSavedItems();
    }
  }

  async function unsaveResult(savedItemId: string) {
    setWorkspaceMessage("");
    try {
      await deleteSavedItem(savedItemId);
      setWorkspaceMessage("Removed from workspace.");
      await loadSavedItems();
    } catch (err) {
      setWorkspaceMessage(err instanceof Error ? err.message : "Could not remove saved item.");
    }
  }

  function getSavedItemId(result: SearchResult) {
    const payload = payloadForSearchResult(result);
    if (!payload) return null;
    return savedItems.find((item) => matchesSavedItem(item, payload))?.id ?? null;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await runSearch(0);
  }

  const canPageBack = offset > 0;
  const canPageForward = response ? offset + response.limit < response.total_results : false;

  return (
    <RoleGuard allowed={["ADMIN", "LAWYER"]} path="/lawyer/search">
      <div className="grid">
        <LegalDisclaimer />
        <form className="panel" onSubmit={submit}>
          <h1>Lawyer advanced search</h1>
          <div className="toolbar">
            <div className="field">
              <label htmlFor="query">Query</label>
              <input id="query" value={query} onChange={(event) => setQuery(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="year">Year</label>
              <input id="year" value={year} onChange={(event) => setYear(event.target.value)} inputMode="numeric" />
            </div>
            <div className="field">
              <label htmlFor="actNumber">Act number</label>
              <input id="actNumber" value={actNumber} onChange={(event) => setActNumber(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="category">Category</label>
              <input id="category" value={category} onChange={(event) => setCategory(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="processingStatus">Processing status</label>
              <select id="processingStatus" value={processingStatus} onChange={(event) => setProcessingStatus(event.target.value)}>
                <option value="">Any</option>
                <option value="UPLOADED">UPLOADED</option>
                <option value="PROCESSING">PROCESSING</option>
                <option value="PROCESSED">PROCESSED</option>
                <option value="FAILED">FAILED</option>
                <option value="VERIFIED">VERIFIED</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="relationship">Relationship</label>
              <select id="relationship" value={relationshipType} onChange={(event) => setRelationshipType(event.target.value)}>
                <option value="">Any</option>
                <option>AMENDS</option>
                <option>REPEALS</option>
                <option>INSERTS</option>
                <option>SUBSTITUTES</option>
                <option>ADDS</option>
                <option>CROSS_REFERENCE</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="status">Verification status</label>
              <select id="status" value={verificationStatus} onChange={(event) => setVerificationStatus(event.target.value)}>
                <option value="">Default</option>
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
                <option value="mapped">Mapped references</option>
                <option value="unresolved">Unresolved references</option>
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
            <button type="submit" disabled={loading}>{loading ? "Searching..." : "Search"}</button>
          </div>
          {error ? <p className="error">{error}</p> : null}
          {workspaceMessage ? <p className="muted">{workspaceMessage}</p> : null}
        </form>
        {loading ? <p>Loading search results...</p> : null}
        <SearchResults
          response={response}
          onSave={saveResult}
          onUnsave={unsaveResult}
          getSavedItemId={getSavedItemId}
        />
        {response ? (
          <div className="toolbar">
            <button type="button" disabled={!canPageBack || loading} onClick={() => runSearch(Math.max(0, offset - response.limit))}>
              Previous page
            </button>
            <button type="button" disabled={!canPageForward || loading} onClick={() => runSearch(offset + response.limit)}>
              Next page
            </button>
          </div>
        ) : null}
      </div>
    </RoleGuard>
  );
}

function payloadForSearchResult(result: SearchResult): SavedItemCreatePayload | null {
  if (result.result_type === "ACT" && result.act_id) {
    return { item_type: "ACT", act_id: result.act_id };
  }
  if (result.result_type === "SECTION" && result.section_id) {
    return { item_type: "SECTION", section_id: result.section_id };
  }
  if (result.result_type === "REFERENCE" && result.reference_id) {
    return { item_type: "REFERENCE", reference_id: result.reference_id };
  }
  return null;
}

function matchesSavedItem(item: SavedItem, payload: SavedItemCreatePayload) {
  if (item.item_type !== payload.item_type) return false;
  if (payload.item_type === "ACT") return item.act_id === payload.act_id;
  if (payload.item_type === "SECTION") return item.section_id === payload.section_id;
  return item.reference_id === payload.reference_id;
}
