"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { VerifiedBadge } from "@/components/lexatlas/verified-badge";
import { listActsBrowse } from "@/lib/api";
import type { LegalActBrowse } from "@/lib/types";

const PAGE_SIZE = 5;

export default function BrowseActsPage() {
  const [acts, setActs] = useState<LegalActBrowse[]>([]);
  const [page, setPage] = useState(1);
  const [year, setYear] = useState("ALL");
  const [category, setCategory] = useState("ALL");
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listActsBrowse()
      .then(setActs)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load Acts. Login may be required."))
      .finally(() => setLoading(false));
  }, []);

  const years = useMemo(
    () => [...new Set(acts.map((act) => act.year).filter((value): value is number => value !== null))].sort((a, b) => b - a),
    [acts]
  );
  const categories = useMemo(
    () => [...new Set(acts.map((act) => act.category).filter((value): value is string => Boolean(value)))].sort(),
    [acts]
  );
  const filteredActs = useMemo(() => {
    const needle = title.trim().toLowerCase();
    return acts.filter((act) => {
      if (year !== "ALL" && String(act.year) !== year) return false;
      if (category !== "ALL" && act.category !== category) return false;
      if (needle && !act.title.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [acts, category, title, year]);
  const pageCount = Math.max(1, Math.ceil(filteredActs.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleActs = filteredActs.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  function resetPage() {
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Browse Acts</h1>
        <p className="text-base text-muted-foreground">
          All verified Acts in the corpus, newest first.
        </p>
      </div>

      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <Select value={year} onValueChange={(value) => { setYear(value ?? "ALL"); resetPage(); }}>
          <SelectTrigger className="h-9 w-full rounded-md bg-card md:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All years</SelectItem>
            {years.map((item) => <SelectItem key={item} value={String(item)}>{item}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={category} onValueChange={(value) => { setCategory(value ?? "ALL"); resetPage(); }}>
          <SelectTrigger className="h-9 w-full rounded-md bg-card md:w-52"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All categories</SelectItem>
            {categories.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input
          value={title}
          onChange={(event) => { setTitle(event.target.value); resetPage(); }}
          placeholder="Filter by title…"
          className="h-9 rounded-md bg-card md:max-w-[260px]"
        />
        <span className="md:ml-auto text-xs text-muted-foreground">{filteredActs.length} verified Acts</span>
      </div>

      {loading ? <BrowseSkeleton /> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {!loading && !error ? (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Act</TableHead>
                <TableHead>No. / Year</TableHead>
                <TableHead>Sections</TableHead>
                <TableHead>References</TableHead>
                <TableHead>Verified</TableHead>
                <TableHead><span className="sr-only">Open</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleActs.map((act) => (
                <TableRow key={act.id}>
                  <TableCell className="font-serif font-semibold">{act.title}</TableCell>
                  <TableCell>No. {act.act_number ?? "—"}{act.year ? ` of ${act.year}` : ""}</TableCell>
                  <TableCell>{act.verified_section_count}</TableCell>
                  <TableCell>{act.verified_reference_count}</TableCell>
                  <TableCell><VerifiedBadge /></TableCell>
                  <TableCell className="text-right">
                    <Link href={`/acts/${act.id}`} className="font-medium text-primary hover:underline">Open →</Link>
                  </TableCell>
                </TableRow>
              ))}
              {!visibleActs.length ? (
                <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-foreground">No verified Acts match these filters.</TableCell></TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      ) : null}

      {!loading && !error && filteredActs.length ? (
        <div className="flex items-center gap-2">
          {Array.from({ length: Math.min(pageCount, 3) }, (_, index) => index + 1).map((pageNumber) => (
            <Button key={pageNumber} type="button" variant={pageNumber === currentPage ? "default" : "outline"} size="sm" onClick={() => setPage(pageNumber)}>
              {pageNumber}
            </Button>
          ))}
          {pageCount > 4 ? <span className="px-1 text-muted-foreground">…</span> : null}
          {pageCount > 3 ? <Button type="button" variant="outline" size="sm" onClick={() => setPage(pageCount)}>{pageCount}</Button> : null}
          <Button type="button" variant="outline" size="sm" disabled={currentPage >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next →</Button>
        </div>
      ) : null}
    </div>
  );
}

function BrowseSkeleton() {
  return (
    <div className="space-y-px overflow-hidden rounded-lg border border-border bg-card p-3">
      {[0, 1, 2, 3, 4].map((item) => <Skeleton key={item} className="h-11 w-full rounded-md" />)}
    </div>
  );
}
