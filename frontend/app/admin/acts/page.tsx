"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { getAct, getEvaluationMetricsSummary, listActs, processAct } from "@/lib/api";
import type { EvaluationMetricsSummary, LegalAct } from "@/lib/types";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

const PROCESSING_POLL_INTERVAL_MS = 1500;
const PROCESSING_POLL_MAX_ATTEMPTS = 80; // ~2 minutes

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function AdminActsPage() {
  const [acts, setActs] = useState<LegalAct[]>([]);
  const [metrics, setMetrics] = useState<EvaluationMetricsSummary | null>(null);
  const [error, setError] = useState("");
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [year, setYear] = useState("ALL");
  const cancelledRef = useRef(false);

  async function load() {
    try {
      const [actsData, metricsData] = await Promise.all([listActs(), getEvaluationMetricsSummary()]);
      setActs(actsData);
      setMetrics(metricsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Acts.");
    }
  }

  useEffect(() => {
    cancelledRef.current = false;
    void load();
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  async function pollActUntilFinished(id: string) {
    for (let attempt = 0; attempt < PROCESSING_POLL_MAX_ATTEMPTS; attempt += 1) {
      if (cancelledRef.current) return;
      const updated = await getAct(id);
      if (cancelledRef.current) return;
      setActs((current) => current.map((item) => (item.id === id ? { ...item, ...updated } : item)));
      if (updated.processing_status !== "PROCESSING") return;
      await sleep(PROCESSING_POLL_INTERVAL_MS);
    }
  }

  async function runProcess(id: string) {
    setError("");
    setProcessingIds((prev) => new Set(prev).add(id));
    try {
      // Processing runs in the background, so poll until the Act leaves the
      // PROCESSING state instead of assuming it finished by the time the
      // POST resolves.
      await processAct(id);
      await pollActUntilFinished(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed.");
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      await load();
    }
  }

  function formatFileSize(bytes: number | null) {
    if (bytes === null) return "-";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(value: string) {
    return new Date(value).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
  }

  const years = useMemo(
    () => [...new Set(acts.map((act) => act.year).filter((value): value is number => value !== null))].sort((a, b) => b - a),
    [acts]
  );
  const filteredActs = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return acts.filter((act) => {
      if (status !== "ALL" && act.processing_status !== status) return false;
      if (year !== "ALL" && String(act.year) !== year) return false;
      return !needle || act.title.toLowerCase().includes(needle) || act.source_file_name.toLowerCase().includes(needle) || (act.act_number ?? "").includes(needle);
    });
  }, [acts, query, status, year]);

  const counts = {
    total: metrics?.document_counts.total ?? acts.length,
    processing: acts.filter((act) => act.processing_status === "PROCESSING").length,
    failed: acts.filter((act) => act.processing_status === "FAILED").length,
    verified: acts.filter((act) => act.processing_status === "VERIFIED").length,
  };

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts">
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Acts</h1>
            <p className="mt-2 max-w-xl text-[14.5px] text-muted-foreground">
              Uploaded corpus with processing state. Trigger reprocessing from an Act&apos;s detail page.
            </p>
          </div>
          <Link href="/admin/acts/upload" className={cn(buttonVariants({ size: "sm" }), "h-[30px] rounded-md")}>
            + Upload Act PDF
          </Link>
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>
            <strong className="text-foreground">{counts.total}</strong> total
          </span>
          <span>
            <strong className="text-[#92681f]">{counts.processing}</strong> processing
          </span>
          <span>
            <strong className="text-[#8c2433]">{counts.failed}</strong> failed
          </span>
          <span>
            <strong className="text-[#22684a]">{counts.verified}</strong> verified
          </span>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search title, act number…"
            className="h-[34px] flex-1 rounded-md bg-[#fffdf8]"
          />
          <Select value={status} onValueChange={(value) => setStatus(value ?? "ALL")}>
            <SelectTrigger className="h-[34px] w-full rounded-md bg-[#fffdf8] sm:w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All statuses</SelectItem>
              <SelectItem value="PROCESSING">Processing</SelectItem>
              <SelectItem value="FAILED">Failed</SelectItem>
              <SelectItem value="PROCESSED">Needs review</SelectItem>
              <SelectItem value="VERIFIED">Verified</SelectItem>
            </SelectContent>
          </Select>
          <Select value={year} onValueChange={(value) => setYear(value ?? "ALL")}>
            <SelectTrigger className="h-[34px] w-full rounded-md bg-[#fffdf8] sm:w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All years</SelectItem>
              {years.map((item) => (
                <SelectItem key={item} value={String(item)}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-[34px] bg-card"
            onClick={() => {
              setQuery("");
              setStatus("ALL");
              setYear("ALL");
            }}
          >
            Clear
          </Button>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!acts.length && !error ? <ActsSkeleton /> : null}
        {acts.length ? (
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <Table>
              <TableHeader><TableRow><TableHead>Act</TableHead><TableHead>No. / Year</TableHead><TableHead>Status</TableHead><TableHead>File</TableHead><TableHead>Uploaded</TableHead><TableHead><span className="sr-only">Action</span></TableHead></TableRow></TableHeader>
              <TableBody>
                {filteredActs.map((act) => (
                  <TableRow key={act.id}>
                    <TableCell><Link href={`/admin/acts/${act.id}`} className="font-serif font-semibold hover:underline">{act.title}</Link></TableCell>
                    <TableCell>No. {act.act_number ?? "—"}{act.year ? ` of ${act.year}` : ""}</TableCell>
                    <TableCell><StatusBadge value={act.processing_status} /></TableCell>
                    <TableCell><span className="block max-w-[220px] truncate text-xs text-muted-foreground" title={act.source_file_name}>{act.source_file_name} · {formatFileSize(act.file_size)}</span></TableCell>
                    <TableCell>{formatDate(act.uploaded_at)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        {act.processing_status !== "VERIFIED" ? <Button size="sm" variant="outline" onClick={() => runProcess(act.id)} disabled={processingIds.has(act.id)}>{processingIds.has(act.id) ? "Processing…" : "Process"}</Button> : null}
                        <Link className={buttonVariants({ variant: "outline", size: "sm" })} href={`/admin/acts/${act.id}`}>Manage →</Link>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!filteredActs.length ? <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted-foreground">No Acts match these filters.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </div>
    </RoleGuard>
  );
}

function ActsSkeleton() {
  return (
    <div className="space-y-2 rounded-lg border border-border bg-card p-4">
      {[0, 1, 2, 3].map((item) => (
        <Skeleton key={item} className="h-11 w-full" />
      ))}
    </div>
  );
}
