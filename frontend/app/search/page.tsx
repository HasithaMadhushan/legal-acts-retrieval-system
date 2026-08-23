"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { SearchResults } from "@/components/search-results";
import { search } from "@/lib/api";
import { containsAdviceIntent } from "@/lib/auth";
import type { SearchResponse } from "@/lib/types";

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [actNumber, setActNumber] = useState("");
  const [relationshipType, setRelationshipType] = useState("ANY");
  const [searchMode, setSearchMode] = useState("all");
  const [verificationStatus, setVerificationStatus] = useState("VERIFIED");
  const [limit, setLimit] = useState("10");
  const [offset, setOffset] = useState(0);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialQuery = params.get("q");
    if (initialQuery) {
      setQuery(initialQuery);
      void runSearch(0, initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runSearch(nextOffset = 0, queryOverride?: string) {
    setError("");
    const trimmedQuery = (queryOverride ?? query).trim();
    if (containsAdviceIntent(trimmedQuery)) {
      setError("This system cannot provide legal advice. Search for Acts, sections, or legal terms instead.");
      return;
    }
    setLoading(true);
    try {
      const data = await search(trimmedQuery, {
        ...(year ? { year } : {}),
        ...(actNumber ? { act_number: actNumber } : {}),
        ...(relationshipType && relationshipType !== "ANY"
          ? { relationship_type: relationshipType }
          : {}),
        ...(verificationStatus && verificationStatus !== "ANY"
          ? { verification_status: verificationStatus }
          : {}),
        search_mode: searchMode,
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
    router.replace(query.trim() ? `/search?q=${encodeURIComponent(query.trim())}` : "/search");
    await runSearch(0);
  }

  const canPageBack = offset > 0;
  const canPageForward = response ? offset + response.limit < response.total_results : false;
  const rangeStart = response && response.total_results ? offset + 1 : 0;
  const rangeEnd = response ? Math.min(offset + response.limit, response.total_results) : 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-4xl font-semibold tracking-tight">Search</h1>
      </div>

      <form className="grid gap-4 rounded-sm border border-border bg-card p-4 md:grid-cols-6" onSubmit={submit}>
        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label htmlFor="query" className="text-xs tracking-[0.12em] uppercase">
            Query
          </Label>
          <Input
            id="query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="personal data protection amendment"
            className="h-10 rounded-sm"
          />
        </div>
        <FilterSelect label="Year" value={year} onChange={setYear} options={[{ value: "", label: "Any year" }]} freeform />
        <FilterSelect
          label="Act no."
          value={actNumber}
          onChange={setActNumber}
          options={[{ value: "", label: "Any number" }]}
          freeform
        />
        <FilterSelect
          label="Relation"
          value={relationshipType}
          onChange={setRelationshipType}
          options={[
            { value: "ANY", label: "Any type" },
            { value: "REFERS_TO", label: "REFERS_TO" },
            { value: "AMENDS", label: "AMENDS" },
            { value: "REPEALS", label: "REPEALS" },
            { value: "INSERTS", label: "INSERTS" },
            { value: "SUBSTITUTES", label: "SUBSTITUTES" },
            { value: "ADDS", label: "ADDS" },
            { value: "CROSS_REFERENCE", label: "CROSS_REFERENCE" }
          ]}
        />
        <FilterSelect
          label="Mode"
          value={searchMode}
          onChange={setSearchMode}
          options={[
            { value: "all", label: "All methods" },
            { value: "keyword", label: "Keyword" },
            { value: "semantic", label: "Semantic" }
          ]}
        />
        <FilterSelect
          label="Status"
          value={verificationStatus}
          onChange={setVerificationStatus}
          options={[
            { value: "VERIFIED", label: "Verified only" },
            { value: "ANY", label: "Any status" }
          ]}
        />
        <div className="flex items-end md:col-span-1">
          <Button type="submit" disabled={loading} className="h-10 w-full rounded-sm">
            {loading ? "Searching…" : "Search"}
          </Button>
        </div>
        {error ? <p className="text-sm text-destructive md:col-span-6">{error}</p> : null}
      </form>

      {response ? (
        <p className="text-sm text-muted-foreground">
          Showing {rangeStart}–{rangeEnd} of {response.total_results} · ranked by section match
        </p>
      ) : null}

      {loading ? <p className="text-sm text-muted-foreground">Loading search results…</p> : null}
      <SearchResults
        response={response}
        emptyMessage={
          response
            ? "No verified results are available for those filters."
            : "No results yet. Try an Act title, section keyword, or mapped reference phrase."
        }
      />

      {response ? (
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-sm"
            disabled={!canPageBack || loading}
            onClick={() => runSearch(Math.max(0, offset - response.limit))}
          >
            Previous page
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-sm"
            disabled={!canPageForward || loading}
            onClick={() => runSearch(offset + response.limit)}
          >
            Next page →
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  freeform = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  freeform?: boolean;
}) {
  if (freeform) {
    return (
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs tracking-[0.12em] uppercase">{label}</Label>
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={options[0]?.label}
          className="h-10 rounded-sm"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs tracking-[0.12em] uppercase">{label}</Label>
      <Select value={value} onValueChange={(next) => onChange(next ?? options[0]?.value ?? "ANY")}>
        <SelectTrigger className="h-10 w-full rounded-sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value || "any"} value={option.value || "ANY"}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
