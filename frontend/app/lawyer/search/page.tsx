"use client";

import { FormEvent, useEffect, useState } from "react";
import { createSavedItem, deleteSavedItem, listSavedItems, search } from "@/lib/api";
import { containsAdviceIntent } from "@/lib/auth";
import type { SavedItem, SavedItemCreatePayload, SearchResponse, SearchResult } from "@/lib/types";
import { RoleGuard } from "@/components/role-guard";
import { SearchResults } from "@/components/search-results";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

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
      <div className="flex flex-col gap-5">
        <div>
          <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">
            Relationship search
          </h1>
          <p className="mt-2 max-w-xl text-[14.5px] text-muted-foreground">
            Filter mapped edges by relationship type and verification status. Save useful citations to your
            workspace.
          </p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-end">
            <SearchField label="Query">
              <Input
                id="query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="repeal · bribery"
                className="h-[34px] bg-[#fffdf8]"
              />
            </SearchField>
            <SelectField
              label="Relationship"
              value={relationshipType || "ANY"}
              onChange={(value) => setRelationshipType(value === "ANY" ? "" : value)}
              options={["ANY", "AMENDS", "REPEALS", "INSERTS", "SUBSTITUTES", "ADDS", "CROSS_REFERENCE"]}
            />
            <SelectField
              label="Status"
              value={verificationStatus || "DEFAULT"}
              onChange={(value) => setVerificationStatus(value === "DEFAULT" ? "" : value)}
              options={["DEFAULT", "VERIFIED", "PENDING", "NEEDS_REVIEW", "REJECTED"]}
            />
            <Button type="submit" disabled={loading} className="h-[34px] px-4">
              {loading ? "Searching…" : "Search"}
            </Button>
          </div>
          <details className="text-sm text-muted-foreground">
            <summary className="cursor-pointer font-medium text-foreground">Advanced filters</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
              <SearchField label="Year">
                <Input
                  id="year"
                  value={year}
                  onChange={(event) => setYear(event.target.value)}
                  inputMode="numeric"
                  className="h-9 bg-[#fffdf8]"
                />
              </SearchField>
              <SearchField label="Act number">
                <Input
                  id="actNumber"
                  value={actNumber}
                  onChange={(event) => setActNumber(event.target.value)}
                  className="h-9 bg-[#fffdf8]"
                />
              </SearchField>
              <SearchField label="Category">
                <Input
                  id="category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="h-9 bg-[#fffdf8]"
                />
              </SearchField>
              <SelectField
                label="Processing status"
                value={processingStatus || "ANY"}
                onChange={(value) => setProcessingStatus(value === "ANY" ? "" : value)}
                options={["ANY", "UPLOADED", "PROCESSING", "PROCESSED", "FAILED", "VERIFIED"]}
              />
              <SelectField
                label="Mapped status"
                value={mappedStatus || "ANY"}
                onChange={(value) => setMappedStatus(value === "ANY" ? "" : value)}
                options={["ANY", "mapped", "unresolved"]}
              />
              <SelectField label="Page size" value={limit} onChange={setLimit} options={["10", "25", "50"]} />
            </div>
          </details>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {workspaceMessage ? <p className="text-sm text-muted-foreground">{workspaceMessage}</p> : null}
        </form>
        {response ? <p className="text-sm"><strong>{response.total_results} mapped edges</strong><span className="text-muted-foreground"> · pending items are marked for review</span></p> : null}
        {loading ? <div className="space-y-2">{[0, 1, 2].map((item) => <Skeleton key={item} className="h-28 w-full" />)}</div> : null}
        <SearchResults
          response={response}
          onSave={saveResult}
          onUnsave={unsaveResult}
          getSavedItemId={getSavedItemId}
        />
        {response ? (
          <div className="flex gap-2">
            <Button variant="outline" type="button" disabled={!canPageBack || loading} onClick={() => runSearch(Math.max(0, offset - response.limit))}>
              Previous page
            </Button>
            <Button variant="outline" type="button" disabled={!canPageForward || loading} onClick={() => runSearch(offset + response.limit)}>
              Next page
            </Button>
          </div>
        ) : null}
      </div>
    </RoleGuard>
  );
}

function SearchField({ label, children }: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <div className="min-w-0 flex-1 space-y-1.5">
      <Label className="text-xs font-semibold tracking-wide">{label}</Label>
      {children}
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}>) {
  return (
    <div className="w-full space-y-1.5 lg:w-40">
      <Label className="text-xs font-semibold tracking-wide">{label}</Label>
      <Select value={value} onValueChange={(next) => onChange(next ?? options[0] ?? "ANY")}>
        <SelectTrigger className="h-[34px] w-full bg-[#fffdf8]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {formatOption(option)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function formatOption(value: string) {
  if (value === "ANY") return "Any";
  if (value === "DEFAULT") return "Verified + pending";
  return value.replaceAll("_", " ").toLowerCase().replace(/^./, (character) => character.toUpperCase());
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
