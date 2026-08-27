"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, use, useEffect, useRef, useState } from "react";
import {
  deleteAct,
  getAct,
  getVerificationSummary,
  listProcessingJobs,
  processAct,
  updateAct
} from "@/lib/api";
import type { LegalAct, ProcessingJob, VerificationSummary } from "@/lib/types";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "@/components/confirm-dialog";

interface MetadataForm {
  title: string;
  act_number: string;
  year: string;
  category: string;
  source_name: string;
  source_url: string;
  certification_date: string;
  publication_date: string;
}

const PROCESSING_POLL_INTERVAL_MS = 1500;
const PROCESSING_POLL_MAX_ATTEMPTS = 80; // ~2 minutes

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function physicalPagesChip(hasPhysicalPages: boolean | null): string {
  if (hasPhysicalPages === true) {
    return " · physical pages";
  }
  if (hasPhysicalPages === false) {
    return " · no physical page map";
  }
  return " · page map unknown";
}

function metadataFormFromAct(act: LegalAct): MetadataForm {
  return {
    title: act.title,
    act_number: act.act_number ?? "",
    year: act.year?.toString() ?? "",
    category: act.category ?? "",
    source_name: act.source_name ?? "",
    source_url: act.source_url ?? "",
    certification_date: act.certification_date ?? "",
    publication_date: act.publication_date ?? ""
  };
}

export default function AdminActDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [act, setAct] = useState<(LegalAct & { raw_text?: string | null }) | null>(null);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [verificationSummary, setVerificationSummary] = useState<VerificationSummary | null>(null);
  const [metadataForm, setMetadataForm] = useState<MetadataForm | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function load() {
    try {
      const [actData, jobData, summaryData] = await Promise.all([
        getAct(id),
        listProcessingJobs(id),
        getVerificationSummary(id)
      ]);
      setAct(actData);
      setJobs(jobData);
      setVerificationSummary(summaryData);
      setMetadataForm(metadataFormFromAct(actData));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Act.");
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function pollUntilFinished(jobId: string): Promise<ProcessingJob | null> {
    for (let attempt = 0; attempt < PROCESSING_POLL_MAX_ATTEMPTS; attempt += 1) {
      const jobList = await listProcessingJobs(id);
      if (!isMountedRef.current) return null;
      setJobs(jobList);
      const job = jobList.find((item) => item.id === jobId) ?? null;
      if (job && (job.status === "COMPLETED" || job.status === "FAILED")) {
        return job;
      }
      await sleep(PROCESSING_POLL_INTERVAL_MS);
      if (!isMountedRef.current) return null;
    }
    return null;
  }

  async function runProcess() {
    setError("");
    setMessage("");
    setIsProcessing(true);
    try {
      // Processing runs in the background; the initial response is QUEUED, so
      // poll for the job's final COMPLETED/FAILED state instead of trusting it.
      const queuedJob = await processAct(id);
      const finalJob = await pollUntilFinished(queuedJob.id);
      if (!isMountedRef.current) return;
      await load();
      if (!finalJob) {
        setError("Processing is taking longer than expected. Refresh this page to check its status.");
      } else if (finalJob.status === "FAILED") {
        setError(finalJob.error_message ?? finalJob.summary_json?.errors?.[0] ?? "Processing failed.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed.");
      await load();
    } finally {
      if (isMountedRef.current) setIsProcessing(false);
    }
  }

  async function saveMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!metadataForm) return;
    setError("");
    setMessage("");
    setIsSaving(true);
    try {
      const updated = await updateAct(id, {
        title: metadataForm.title,
        act_number: metadataForm.act_number || null,
        year: metadataForm.year ? Number(metadataForm.year) : null,
        category: metadataForm.category || null,
        source_name: metadataForm.source_name || null,
        source_url: metadataForm.source_url || null,
        certification_date: metadataForm.certification_date || null,
        publication_date: metadataForm.publication_date || null
      });
      setAct((current) => ({ ...(current ?? updated), ...updated }));
      setMetadataForm(metadataFormFromAct(updated));
      setMessage("Metadata saved for Admin review.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Metadata could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  async function removeAct() {
    setError("");
    setMessage("");
    setIsDeleting(true);
    try {
      await deleteAct(id);
      router.replace("/admin/acts");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Act could not be deleted.");
      setIsDeleting(false);
    }
  }

  const latestJob = jobs[0] ?? null;
  const summary = latestJob?.summary_json ?? null;
  const metadataSummary = summary?.metadata ?? null;
  const warnings = summary?.warnings ?? [];
  const metadataWarnings = metadataSummary?.warnings ?? [];
  const errors = summary?.errors ?? [];
  const extractedCharacters =
    summary?.extracted_character_count ?? (act?.raw_text ? act.raw_text.length : null);
  const pageCount = summary?.page_count ?? act?.page_count ?? null;

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts">
      <div className="flex flex-col gap-5">
        {message ? <p className="rounded-md border border-[#22684a] bg-card px-4 py-3 text-sm text-[#22684a]">{message}</p> : null}
        {error ? <p className="rounded-md border border-destructive bg-card px-4 py-3 text-sm text-destructive">{error}</p> : null}
        {act ? (
          <section>
            <p className="mb-3 text-xs text-muted-foreground"><Link href="/admin/acts" className="hover:underline">Acts</Link> / {act.title}</p>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h1 className="font-serif text-3xl font-semibold tracking-tight">{act.title}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <StatusBadge value={act.processing_status} />
                  <span>Uploaded {new Date(act.uploaded_at).toLocaleString()}</span>
                  <span>· {act.source_file_name}</span>
                  <span>· {pageCount ?? "—"} pages</span>
                  <span>· Extracted characters: {extractedCharacters?.toLocaleString() ?? "—"}</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void runProcess()} disabled={isProcessing}>
                  {isProcessing ? "Processing…" : "Reprocess ↻"}
                </Button>
                <Link
                  href={`/admin/acts/${act.id}/sections`}
                  className={cn(buttonVariants({ variant: "outline", size: "default" }), "bg-card")}
                >
                  Review sections
                </Link>
                <Link
                  href={`/admin/acts/${act.id}/references`}
                  className={cn(buttonVariants({ variant: "outline", size: "default" }), "bg-card")}
                >
                  Review references
                </Link>
                <ConfirmDialog
                  title="Delete this Act?"
                  description="This permanently removes the uploaded PDF, extracted sections, references and processing history. This cannot be undone."
                  triggerLabel="Delete Act"
                  confirmLabel="Delete Act"
                  pendingLabel="Deleting..."
                  pending={isDeleting}
                  triggerClassName="border-destructive text-destructive hover:bg-destructive/10"
                  onConfirm={removeAct}
                />
              </div>
            </div>
            {act.processing_error ? <p className="error">{act.processing_error}</p> : null}
          </section>
        ) : <p>Loading...</p>}
        {latestJob ? (
          <section className="rounded-lg border border-border bg-card px-5 py-4 shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
            <div className="flex items-center justify-between gap-3 text-sm"><strong>Processing pipeline</strong><span className="text-xs text-muted-foreground">{latestJob.current_step} · {latestJob.progress_percent}%</span></div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-[color:var(--gold)] transition-[width]" style={{ width: `${latestJob.progress_percent}%` }} /></div>
            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground"><span>✓ Upload validated</span><span>✓ Text extracted</span><span>✓ Cleaned</span><span>● Metadata + sections</span><span>○ References</span><span>○ Mapping</span></div>
          </section>
        ) : null}
        {act && metadataForm ? (
          <form className="rounded-lg border border-border bg-card p-5 shadow-sm" onSubmit={saveMetadata}>
            <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">Metadata editor</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Review rule-based metadata before relying on it for search or reference mapping. Edited values are
              preserved on reprocess.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="title">Act title</Label>
                <Input
                  id="title"
                  className="bg-[#fffdf8]"
                  value={metadataForm.title}
                  onChange={(event) => setMetadataForm({ ...metadataForm, title: event.target.value })}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="actNumber">Act number</Label>
                <Input
                  id="actNumber"
                  className="bg-[#fffdf8]"
                  value={metadataForm.act_number}
                  onChange={(event) => setMetadataForm({ ...metadataForm, act_number: event.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="year">Year</Label>
                <Input
                  id="year"
                  max={2100}
                  min={1800}
                  type="number"
                  className="bg-[#fffdf8]"
                  value={metadataForm.year}
                  onChange={(event) => setMetadataForm({ ...metadataForm, year: event.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="category">Category / subject area</Label>
                <Input
                  id="category"
                  className="bg-[#fffdf8]"
                  value={metadataForm.category}
                  onChange={(event) => setMetadataForm({ ...metadataForm, category: event.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="certificationDate">Certification date</Label>
                <Input
                  id="certificationDate"
                  type="date"
                  className="bg-[#fffdf8]"
                  value={metadataForm.certification_date}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, certification_date: event.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="publicationDate">Publication date</Label>
                <Input
                  id="publicationDate"
                  type="date"
                  className="bg-[#fffdf8]"
                  value={metadataForm.publication_date}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, publication_date: event.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sourceName">Source name</Label>
                <Input
                  id="sourceName"
                  className="bg-[#fffdf8]"
                  value={metadataForm.source_name}
                  onChange={(event) => setMetadataForm({ ...metadataForm, source_name: event.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sourceUrl">Source URL</Label>
                <Input
                  id="sourceUrl"
                  className="bg-[#fffdf8]"
                  value={metadataForm.source_url}
                  onChange={(event) => setMetadataForm({ ...metadataForm, source_url: event.target.value })}
                />
              </div>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">Source filename: {act.source_file_name}</p>
            <p className="mt-1 text-sm">
              Processing status: <StatusBadge value={act.processing_status} />
            </p>
            {metadataSummary ? (
              <div className="mt-2 text-sm text-muted-foreground">
                <p>Metadata confidence: {metadataSummary.confidence_score ?? "Unavailable"}</p>
                {metadataSummary.preserved_fields?.length ? (
                  <p>Preserved on reprocessing: {metadataSummary.preserved_fields.join(", ")}</p>
                ) : null}
              </div>
            ) : null}
            {metadataWarnings.length > 0 ? (
              <div className="mt-3">
                <h3 className="text-sm font-semibold">Metadata warnings</h3>
                <ul className="mt-1 list-disc pl-5 text-sm">
                  {metadataWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="mt-4 flex justify-end">
              <Button type="submit" disabled={isSaving}>
                {isSaving ? "Saving..." : "Save metadata"}
              </Button>
            </div>
          </form>
        ) : null}
        {verificationSummary ? (
          <section className="space-y-3">
            <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">
              Review queue for this Act
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="rounded-lg border-[#c9a882]">
                <CardContent className="p-4">
                  <h2 className="font-serif text-base font-semibold">
                    References — {verificationSummary.pending_references} pending,{" "}
                    {verificationSummary.needs_review_references} needs review
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Verify or correct before they appear to lawyers & users →
                  </p>
                  <Link
                    href={`/admin/acts/${id}/references`}
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3 inline-flex bg-card")}
                  >
                    Open references
                  </Link>
                </CardContent>
              </Card>
              <Card className="rounded-lg border-[#cfe0d4]">
                <CardContent className="p-4">
                  <h2 className="font-serif text-base font-semibold">
                    Sections — {verificationSummary.verified_sections} verified,{" "}
                    {verificationSummary.pending_sections} pending
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Spot-check headings and text segmentation →
                  </p>
                  <Link
                    href={`/admin/acts/${id}/sections`}
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3 inline-flex bg-card")}
                  >
                    Open sections
                  </Link>
                </CardContent>
              </Card>
            </div>
            <Card className="rounded-lg">
              <CardContent className="space-y-2 p-4 text-sm">
                <h2 className="font-serif text-lg font-semibold">Verification summary</h2>
                <p className="text-muted-foreground">
                  Admin review status for extracted sections, references, and mapping corrections.
                </p>
                <div className="flex flex-wrap gap-3">
                  <span>Pending sections: {verificationSummary.pending_sections}</span>
                  <span>Needs review sections: {verificationSummary.needs_review_sections}</span>
                  <span>Verified sections: {verificationSummary.verified_sections}</span>
                  <span>Rejected sections: {verificationSummary.rejected_sections}</span>
                </div>
                <div className="flex flex-wrap gap-3">
                  <span>Pending references: {verificationSummary.pending_references}</span>
                  <span>Needs review references: {verificationSummary.needs_review_references}</span>
                  <span>Verified references: {verificationSummary.verified_references}</span>
                  <span>Rejected references: {verificationSummary.rejected_references}</span>
                </div>
                <div className="flex flex-wrap gap-3">
                  <span>Mapped references: {verificationSummary.mapped_references}</span>
                  <span>Unresolved references: {verificationSummary.unresolved_references}</span>
                </div>
              </CardContent>
            </Card>
          </section>
        ) : null}
        {latestJob ? (
          <Card className="rounded-lg">
            <CardContent className="space-y-2 p-5 text-sm">
              <h2 className="font-serif text-lg font-semibold">Processing job summary</h2>
              <p>
                Latest job: <StatusBadge value={latestJob.status} /> {latestJob.current_step}
              </p>
              <p>Progress: {latestJob.progress_percent}%</p>
              <p>Requested parser: {summary?.parser_requested ?? "Unavailable"}</p>
              <p>Latest job parser: {summary?.parser_used ?? "Unavailable"}</p>
              {act?.extraction_artifact?.present ? (
                <p>
                  Extraction artifact: schema {act.extraction_artifact.schema_version ?? "unknown"}
                  {act.extraction_artifact.parser_name
                    ? ` · ${act.extraction_artifact.parser_name}`
                    : ""}
                  {act.extraction_artifact.sha256_prefix
                    ? ` · ${act.extraction_artifact.sha256_prefix}`
                    : ""}
                  {physicalPagesChip(act.extraction_artifact.has_physical_pages)}
                  {act.extraction_artifact.created_at
                    ? ` · ${new Date(act.extraction_artifact.created_at).toLocaleString()}`
                    : ""}
                  {act.extraction_artifact.integrity_warning ? " · integrity warning" : ""}
                </p>
              ) : (
                <p>Extraction artifact: not stored</p>
              )}
              <p>Sections created: {summary?.sections_created ?? 0}</p>
              <p>References created: {summary?.references_created ?? 0}</p>
              {latestJob.completed_at ? (
                <p>Completed: {new Date(latestJob.completed_at).toLocaleString()}</p>
              ) : null}
              {warnings.length > 0 ? (
                <div>
                  <h3 className="font-semibold">Warnings</h3>
                  <ul className="list-disc pl-5">
                    {warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {errors.length > 0 ? (
                <div>
                  <h3 className="font-semibold">Errors</h3>
                  <ul className="list-disc pl-5 text-destructive">
                    {errors.map((jobError) => (
                      <li key={jobError}>{jobError}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </CardContent>
          </Card>
        ) : (
          <Card className="rounded-lg">
            <CardContent className="p-5">
              <h2 className="font-serif text-lg font-semibold">Processing job summary</h2>
              <p className="mt-2 text-sm text-muted-foreground">No processing job has run for this Act yet.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </RoleGuard>
  );
}
