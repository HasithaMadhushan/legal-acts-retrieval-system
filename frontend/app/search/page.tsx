"use client";

import { FormEvent, useState } from "react";
import { search } from "@/lib/api";
import { containsAdviceIntent } from "@/lib/auth";
import type { SearchResponse } from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { SearchResults } from "@/components/search-results";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [actNumber, setActNumber] = useState("");
  const [category, setCategory] = useState("");
  const [relationshipType, setRelationshipType] = useState("");
  const [limit, setLimit] = useState("10");
  const [offset, setOffset] = useState(0);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function runSearch(nextOffset = 0) {
    setError("");
    const trimmedQuery = query.trim();
    if (containsAdviceIntent(trimmedQuery)) {
      setError("This system cannot provide legal advice. Search for Acts, sections, or legal terms instead.");
      return;
    }
    setLoading(true);
    try {
      const data = await search(trimmedQuery, {
        ...(year ? { year } : {}),
        ...(actNumber ? { act_number: actNumber } : {}),
        ...(category ? { category } : {}),
        ...(relationshipType ? { relationship_type: relationshipType } : {}),
        limit,
        offset: String(nextOffset)
      });
      setResponse(data);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed. Login may be required.");
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    await runSearch(0);
  }

  const canPageBack = offset > 0;
  const canPageForward = response ? offset + response.limit < response.total_results : false;

  return (
    <div className="grid">
      <LegalDisclaimer />
      <form className="panel" onSubmit={submit}>
        <h1>Search verified legal information</h1>
        <p className="muted">
          Results show verified Acts, sections, and reviewed mapped relationships available to General Users.
        </p>
        <div className="toolbar">
          <div className="field">
            <label htmlFor="query">Keyword or plain-language search</label>
            <input id="query" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Example: amendment of section 5" />
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
            <label htmlFor="relationship">Relationship type</label>
            <select id="relationship" value={relationshipType} onChange={(event) => setRelationshipType(event.target.value)}>
              <option value="">Any</option>
              <option value="REFERS_TO">REFERS_TO</option>
              <option value="AMENDS">AMENDS</option>
              <option value="REPEALS">REPEALS</option>
              <option value="INSERTS">INSERTS</option>
              <option value="SUBSTITUTES">SUBSTITUTES</option>
              <option value="ADDS">ADDS</option>
              <option value="CROSS_REFERENCE">CROSS_REFERENCE</option>
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
      </form>
      {loading ? <p>Loading search results...</p> : null}
      <SearchResults
        response={response}
        emptyMessage={
          response
            ? "No verified results are available for those filters."
            : "No results yet. Try an Act title, Act number, year, category, or section keyword."
        }
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
  );
}
