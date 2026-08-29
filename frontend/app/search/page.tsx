"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
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
import { search, searchErrorMessage } from "@/lib/api";
import { containsAdviceIntent } from "@/lib/auth";
import { describeSearchMode, type SearchResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading search...</p>}>
      <SearchForm />
    </Suspense>
  );
}

function SearchForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
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
    const initialQuery = searchParams.get("q") ?? "";
    const initialYear = searchParams.get("year") ?? "";
    const initialActNumber = searchParams.get("act_number") ?? "";
    const initialMode = searchParams.get("search_mode") ?? "all";
    const initialStatus = searchParams.get("verification_status") ?? "VERIFIED";
    const initialOffset = Number(searchParams.get("offset") ?? "0") || 0;
    setQuery(initialQuery);
    setYear(initialYear);
    setActNumber(initialActNumber);
    setSearchMode(initialMode);
    setVerificationStatus(initialStatus);
    if (initialQuery) {
      void runSearch(initialOffset, initialQuery, {
        year: initialYear,
        actNumber: initialActNumber,
        searchMode: initialMode,
        verificationStatus: initialStatus
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function syncUrl(nextOffset: number, values: {
    query: string;
    year: string;
    actNumber: string;
    searchMode: string;
    verificationStatus: string;
  }) {
    const params = new URLSearchParams();
    if (values.query) params.set("q", values.query);
    if (values.year) params.set("year", values.year);
    if (values.actNumber) params.set("act_number", values.actNumber);
    if (values.searchMode && values.searchMode !== "all") params.set("search_mode", values.searchMode);
    if (values.verificationStatus && values.verificationStatus !== "VERIFIED") {
      params.set("verification_status", values.verificationStatus);
    }
    if (nextOffset) params.set("offset", String(nextOffset));
    const qs = params.toString();
    router.replace(qs ? `/search?${qs}` : "/search");
  }

  function buildSearchParams(values: {
    year: string;
    actNumber: string;
    searchMode: string;
    verificationStatus: string;
    offset: number;
  }) {
    return {
      ...(values.year ? { year: values.year } : {}),
      ...(values.actNumber ? { act_number: values.actNumber } : {}),
      ...(relationshipType && relationshipType !== "ANY"
        ? { relationship_type: relationshipType }
        : {}),
      ...(values.verificationStatus && values.verificationStatus !== "ANY"
        ? { verification_status: values.verificationStatus }
        : {}),
      search_mode: values.searchMode,
      limit,
      offset: String(values.offset)
    };
  }

  async function runSearch(
    nextOffset = 0,
    queryOverride?: string,
    overrides?: {
      year?: string;
      actNumber?: string;
      searchMode?: string;
      verificationStatus?: string;
    }
  ) {
    setError("");
    const trimmedQuery = (queryOverride ?? query).trim();
    const nextYear = overrides?.year ?? year;
    const nextActNumber = overrides?.actNumber ?? actNumber;
    const nextMode = overrides?.searchMode ?? searchMode;
    const nextStatus = overrides?.verificationStatus ?? verificationStatus;
    if (containsAdviceIntent(trimmedQuery)) {
      setError("This system cannot provide legal advice. Search for Acts, sections, or legal terms instead.");
      return;
    }
    setLoading(true);
    try {
      const data = await search(
        trimmedQuery,
        buildSearchParams({
          year: nextYear,
          actNumber: nextActNumber,
          searchMode: nextMode,
          verificationStatus: nextStatus,
          offset: nextOffset
        })
      );
      setResponse(data);
      setOffset(nextOffset);
      syncUrl(nextOffset, {
        query: trimmedQuery,
        year: nextYear,
        actNumber: nextActNumber,
        searchMode: nextMode,
        verificationStatus: nextStatus
      });
    } catch (err) {
      setError(searchErrorMessage(err));
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
  const rangeStart = response && response.total_results ? offset + 1 : 0;
  const rangeEnd = response ? Math.min(offset + response.limit, response.total_results) : 0;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Search</h1>
        <p className="max-w-xl text-[14.5px] text-muted-foreground">
          Keyword and metadata search across verified Acts, sections, and statutory references.
        </p>
      </div>

      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="flex flex-col gap-2 xl:flex-row xl:items-end">
          <div className="min-w-0 flex-[1.4] space-y-1.5">
            <Label htmlFor="query" className="text-xs font-semibold tracking-wide">
              Query
            </Label>
            <Input
              id="query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="personal data protection amendment"
              className="h-[34px] rounded-md bg-[#fffdf8]"
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
              { value: "all", label: "Hybrid" },
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
          <Button type="submit" disabled={loading} className="h-[34px] px-4">
            {loading ? "Searching…" : "Search"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {searchMode === "keyword"
            ? "Matches exact words, Act identifiers, and filters."
            : searchMode === "semantic"
              ? "Finds sections by meaning. Availability depends on the current embedding backfill."
              : "Combines exact keyword matches with meaning-based section retrieval when semantic search is ready."}
        </p>
        {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      </form>

      {response ? (
        <p className="text-sm text-muted-foreground">
          Showing {rangeStart}–{rangeEnd} of {response.total_results} · {describeSearchMode(response)}
          {response.semantic_ready && response.embedding_model
            ? ` · ${response.embedding_model}`
            : ""}
        </p>
      ) : null}

      {loading ? <div className="space-y-2">{[0, 1, 2].map((item) => <Skeleton key={item} className="h-24 w-full" />)}</div> : null}
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
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  freeform?: boolean;
}>) {
  if (freeform) {
    return (
      <div className="w-full space-y-1.5 xl:w-28">
        <Label className="text-xs font-semibold tracking-wide">{label}</Label>
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={options[0]?.label}
          className="h-[34px] rounded-md bg-[#fffdf8]"
        />
      </div>
    );
  }

  return (
    <div className="w-full space-y-1.5 xl:w-36">
      <Label className="text-xs font-semibold tracking-wide">{label}</Label>
      <Select value={value} onValueChange={(next) => onChange(next ?? options[0]?.value ?? "ANY")}>
        <SelectTrigger className="h-[34px] w-full rounded-md bg-[#fffdf8]">
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
