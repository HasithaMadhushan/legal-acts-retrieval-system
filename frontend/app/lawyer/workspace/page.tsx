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
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { cn } from "@/lib/utils";

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
  const [filterQuery, setFilterQuery] = useState("");
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
  const filteredItems = filterQuery.trim()
    ? items.filter((item) => {
        const haystack = [
          item.item_title,
          item.act_title,
          item.section_heading,
          item.section_number,
          item.note,
          item.relationship_type,
          item.target_act_title
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(filterQuery.trim().toLowerCase());
      })
    : items;

  return (
    <RoleGuard allowed={["ADMIN", "LAWYER"]} path="/lawyer/workspace">
      <div className="flex flex-col gap-5">
        <section className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Workspace</h1>
            <p className="mt-2 text-[14.5px] text-muted-foreground">
              Organize saved research results only. This workspace does not provide legal advice or legal opinions.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-[30px] bg-card"
              onClick={() => exportWithToken("/exports/saved-items.csv")}
            >
              Export CSV ↓
            </Button>
            <Button type="button" size="sm" className="h-[30px]" onClick={() => exportWithToken("/exports/saved-items.md")}>
              Export Markdown ↓
            </Button>
          </div>
        </section>

        <form onSubmit={applyFilters} className="flex flex-col gap-3">
          <p className="sr-only">Workspace filters</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={filterQuery}
              onChange={(event) => setFilterQuery(event.target.value)}
              placeholder="Filter saved items..."
              className="h-[34px] flex-1 bg-[#fffdf8]"
              aria-label="Filter saved items"
            />
            <Select value={itemType} onValueChange={(value) => setItemType((value as ItemFilter) ?? "ALL")}>
              <SelectTrigger className="h-[34px] w-full bg-[#fffdf8] sm:w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All types</SelectItem>
                {ITEM_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" variant="outline" disabled={loading} className="h-[34px] bg-card">
              {loading ? "Loading…" : "Apply"}
            </Button>
          </div>
          <details className="text-sm text-muted-foreground">
            <summary className="cursor-pointer font-medium text-foreground">Advanced filters</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <div className="space-y-1.5">
                <Label className="text-xs">Act ID</Label>
                <Input value={actId} onChange={(event) => setActId(event.target.value)} className="h-9 bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Relationship</Label>
                <Select
                  value={relationshipType || "ANY"}
                  onValueChange={(value) => setRelationshipType(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["ANY", "REFERS_TO", "AMENDS", "REPEALS", "INSERTS", "SUBSTITUTES", "ADDS", "CROSS_REFERENCE"].map(
                      (type) => (
                        <SelectItem key={type} value={type}>
                          {type === "ANY" ? "Any" : type}
                        </SelectItem>
                      )
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Verification</Label>
                <Select
                  value={verificationStatus || "ANY"}
                  onValueChange={(value) => setVerificationStatus(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["ANY", "VERIFIED", "PENDING", "NEEDS_REVIEW", "REJECTED"].map((status) => (
                      <SelectItem key={status} value={status}>
                        {status === "ANY" ? "Any" : status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Mapped</Label>
                <Select
                  value={mappedStatus || "ANY"}
                  onValueChange={(value) => setMappedStatus(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ANY">Any</SelectItem>
                    <SelectItem value="mapped">Mapped</SelectItem>
                    <SelectItem value="unresolved">Unresolved</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Page size</Label>
                <Select value={limit} onValueChange={(value) => setLimit(value ?? "25")}>
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["10", "25", "50"].map((size) => (
                      <SelectItem key={size} value={size}>
                        {size}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </details>
        </form>

        <details className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <summary className="cursor-pointer font-serif text-lg font-semibold">Manual save</summary>
          <form className="mt-3 grid gap-3 sm:grid-cols-4" onSubmit={submitManualSave}>
            <div className="space-y-1.5">
              <Label className="text-xs">Item type</Label>
              <Select value={manualType} onValueChange={(value) => setManualType((value as SavedItemType) ?? "SECTION")}>
                <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ITEM_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="text-xs">
                {manualType === "ACT" ? "Act ID" : manualType === "SECTION" ? "Section ID" : "Reference ID"}
              </Label>
              <Input
                value={manualId}
                onChange={(event) => setManualId(event.target.value)}
                required
                className="h-9 bg-[#fffdf8]"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Private note</Label>
              <Input
                value={manualNote}
                onChange={(event) => setManualNote(event.target.value)}
                className="h-9 bg-[#fffdf8]"
              />
            </div>
            <div className="sm:col-span-4">
              <Button type="submit">Save item</Button>
            </div>
          </form>
        </details>

        {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {loading ? <p className="text-sm text-muted-foreground">Loading workspace...</p> : null}
        {!loading && !filteredItems.length ? (
          <div className="rounded-md border border-dashed border-border bg-background px-4 py-8 text-sm text-muted-foreground">
            No saved research items match these filters.
          </div>
        ) : null}

        {ITEM_TYPES.map((type) => (
          <SavedItemGroup
            key={type}
            type={type}
            items={filteredItems.filter((item) => item.item_type === type)}
            onSaveNote={saveNote}
            onUnsave={unsave}
          />
        ))}

        {totalResults ? (
          <div className="flex items-center gap-2 text-sm">
            <span>
              Showing {offset + 1}-{offset + items.length} of {totalResults}
            </span>
            <Button
              variant="outline"
              size="sm"
              type="button"
              disabled={!canPageBack || loading}
              onClick={() => void load(Math.max(0, offset - Number(limit)))}
            >
              Previous page
            </Button>
            <Button
              variant="outline"
              size="sm"
              type="button"
              disabled={!canPageForward || loading}
              onClick={() => void load(offset + Number(limit))}
            >
              Next page
            </Button>
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
}: Readonly<{
  type: SavedItemType;
  items: SavedItem[];
  onSaveNote: (itemId: string, event: FormEvent<HTMLFormElement>) => Promise<void>;
  onUnsave: (itemId: string) => Promise<void>;
}>) {
  if (!items.length) return null;
  return (
    <section className="space-y-3">
      <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">
        Saved {type.toLowerCase()}s · {items.length}
      </p>
      {items.map((item) => (
        <Card key={item.id} className="rounded-lg border-border bg-card shadow-sm">
          <CardContent className="px-4 py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-[#f6ebd4] px-2 py-0.5 text-[11px] font-semibold text-[#5c430e]">
                    {type === "SECTION" ? "Section" : type === "ACT" ? "Act" : "Reference"}
                  </span>
                  {item.verification_status ? <StatusBadge value={item.verification_status} /> : null}
                  {item.relationship_type ? <StatusBadge value={item.relationship_type} /> : null}
                </div>
                <Link
                  href={itemLink(item)}
                  className="mt-2 block font-serif text-[15px] font-semibold text-[#14263c] hover:underline"
                >
                  {item.item_title ?? item.act_title ?? item.id}
                </Link>
                <p className="mt-1 text-xs text-muted-foreground">
                  {item.created_at ? `Saved ${new Date(item.created_at).toLocaleDateString()}` : ""}
                  {item.section_number
                    ? ` · Section ${item.section_number}${item.section_heading ? ` — ${item.section_heading}` : ""}`
                    : ""}
                </p>
                {item.target_act_title ? (
                  <p className="mt-2 text-sm">
                    → <strong>{item.target_act_title}</strong>
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 gap-2">
                <Link
                  href={itemLink(item)}
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }), "bg-card")}
                >
                  Open
                </Link>
                <ConfirmDialog
                  title="Remove this saved item?"
                  description="The item and its private workspace note will be removed. The underlying Act, section, or reference is not changed."
                  confirmLabel="Remove item"
                  triggerLabel="Remove"
                  onConfirm={() => onUnsave(item.id)}
                />
              </div>
            </div>
            <form
              className="mt-3 flex gap-2 rounded-md border border-[#ede8db] bg-[#f6ebd4]/50 p-3"
              onSubmit={(event) => onSaveNote(item.id, event)}
            >
              <Input
                name="note"
                defaultValue={item.note ?? ""}
                aria-label={`Note for ${item.item_title ?? item.id}`}
                placeholder={item.note ? "Edit note…" : "Add a private note…"}
                className="h-8 bg-card"
              />
              <Button type="submit" variant="outline" size="sm" className="bg-card">
                Save note
              </Button>
            </form>
          </CardContent>
        </Card>
      ))}
    </section>
  );
}

function itemLink(item: SavedItem) {
  if (item.item_type === "SECTION" && item.section_id) return `/sections/${item.section_id}`;
  if (item.item_type === "ACT" && item.act_id) return `/acts/${item.act_id}`;
  if (item.reference_id && item.act_id) return `/lawyer/relationships?actId=${item.act_id}`;
  return "/lawyer/workspace";
}
