"use client";

import Link from "next/link";
import type { SearchResponse, SearchResult } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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
    return <div className="rounded-lg border border-dashed border-border px-4 py-8 text-sm text-muted-foreground">{emptyMessage}</div>;
  }
  return (
    <div className="flex flex-col gap-3">
      {response ? (
        <p className="sr-only">Search result summary: {response.total_results} total results; {response.act_results} Acts, {response.section_results} Sections, {response.reference_results} References. Showing {response.offset + 1}-{response.offset + results.length}.</p>
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
    <Card className={cn("rounded-lg border-border bg-card", result.verification_status === "VERIFIED" && "border-l-2 border-l-[#22684a]", result.verification_status === "NEEDS_REVIEW" && "border-l-2 border-l-[#b17a1e]")}>
      <CardContent className="px-4 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge value={result.verification_status} />
            <StatusBadge value={result.result_type} />
            {result.mapped !== null ? <StatusBadge value={result.mapped ? "MAPPED" : "UNRESOLVED"} /> : null}
          </div>
          <div className="flex shrink-0 gap-2">
            <Link className={buttonVariants({ variant: "outline", size: "sm" })} href={result.section_id ? `/sections/${result.section_id}` : result.act_id ? `/acts/${result.act_id}` : "/search"}>Open {result.section_id ? "section" : "Act"}</Link>
            {onSave ? (
              <Button type="button" size="sm" variant={savedItemId ? "outline" : "secondary"} onClick={() => { if (savedItemId && onUnsave) void onUnsave(savedItemId); else void onSave(result); }}>
                {savedItemId ? "Unsave from workspace" : "Save to workspace"}
              </Button>
            ) : null}
          </div>
        </div>
        <h3 className="mt-3 font-serif text-base font-semibold">
          {result.section_number ? `Section ${result.section_number}${result.section_heading ? ` — ${result.section_heading}` : ""}` : result.title}
        </h3>
        {result.relationship_type ? (
          <p className="mt-2 text-sm"><StatusBadge value={result.relationship_type} /> <span className="mx-1">→</span> {result.target_act_title ?? "Target Act unresolved"}{result.target_section ? ` · ${result.target_section}` : ""}</p>
        ) : null}
        <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{result.snippet}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {result.act_number ? `No. ${result.act_number}${result.year ? ` of ${result.year}` : ""}` : result.title}
          {result.confidence_score !== null ? ` · Confidence ${result.confidence_score.toFixed(2)}` : ""}
          {result.processing_status ? ` · ${result.processing_status}` : ""}
        </p>
      </CardContent>
    </Card>
  );
}
