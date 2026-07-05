"use client";

import Link from "next/link";
import type { SearchResponse, SearchResult } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export function SearchResults({
  response,
  emptyMessage = "No results yet. Try an Act title, Act number, year, or section keyword.",
  onSave,
  onUnsave,
  getSavedItemId
}: {
  response: SearchResponse | null;
  emptyMessage?: string;
  onSave?: (result: SearchResult) => void | Promise<void>;
  onUnsave?: (savedItemId: string) => void | Promise<void>;
  getSavedItemId?: (result: SearchResult) => string | null;
}) {
  const results = response?.results ?? [];
  if (!results.length) {
    return <div className="empty">{emptyMessage}</div>;
  }
  return (
    <div className="grid">
      {response ? (
        <section className="panel">
          <h2>Search result summary</h2>
          <div className="toolbar">
            <span>Total results: {response.total_results}</span>
            <span>Acts: {response.act_results}</span>
            <span>Sections: {response.section_results}</span>
            <span>References: {response.reference_results}</span>
            <span>Showing {response.offset + 1}-{response.offset + results.length}</span>
          </div>
        </section>
      ) : null}
      {results.map((result) => (
        <SearchResultCard
          key={`${result.result_type}-${result.id}`}
          result={result}
          savedItemId={getSavedItemId?.(result) ?? null}
          onSave={onSave}
          onUnsave={onUnsave}
        />
      ))}
    </div>
  );
}

function SearchResultCard({
  result,
  savedItemId,
  onSave,
  onUnsave
}: {
  result: SearchResult;
  savedItemId: string | null;
  onSave?: (result: SearchResult) => void | Promise<void>;
  onUnsave?: (savedItemId: string) => void | Promise<void>;
}) {
  return (
    <article className="panel result">
      <div>
        <StatusBadge value={result.result_type} />{" "}
        {result.relationship_type ? <StatusBadge value={result.relationship_type} /> : null}{" "}
        <StatusBadge value={result.verification_status} />
        {result.mapped !== null ? (
          <StatusBadge value={result.mapped ? "MAPPED" : "UNRESOLVED"} />
        ) : null}
      </div>
      <h3>
        {result.title} {result.act_number ? `No. ${result.act_number}` : ""}{" "}
        {result.year ? `of ${result.year}` : ""}
      </h3>
      <p className="muted">
        {result.category ? `Category: ${result.category}` : "Category unavailable"}{" "}
        {result.processing_status ? `| Processing: ${result.processing_status}` : ""}
      </p>
      {result.section_number ? (
        <p className="muted">
          Section {result.section_number}
          {result.section_heading ? `: ${result.section_heading}` : ""}
        </p>
      ) : null}
      {result.target_act_title || result.target_section ? (
        <p className="muted">
          Target: {result.target_act_title ?? "Target Act unresolved"}
          {result.target_section ? ` section/path ${result.target_section}` : ""}
        </p>
      ) : null}
      {result.confidence_score !== null ? (
        <p className="muted">Confidence: {Math.round(result.confidence_score * 100)}%</p>
      ) : null}
      <p>{result.snippet}</p>
      <Link
        className="button secondary"
        href={
          result.section_id
            ? `/sections/${result.section_id}`
            : result.act_id
              ? `/acts/${result.act_id}`
              : "/search"
        }
      >
        Open
      </Link>
      {onSave ? (
        <button
          type="button"
          className="secondary"
          onClick={() => {
            if (savedItemId && onUnsave) {
              void onUnsave(savedItemId);
            } else {
              void onSave(result);
            }
          }}
        >
          {savedItemId ? "Unsave from workspace" : "Save to workspace"}
        </button>
      ) : null}
    </article>
  );
}
