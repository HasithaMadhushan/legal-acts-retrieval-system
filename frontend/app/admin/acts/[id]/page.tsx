"use client";

import Link from "next/link";
import { FormEvent, use, useEffect, useRef, useState } from "react";
import {
  getAct,
  getVerificationSummary,
  listProcessingJobs,
  processAct,
  updateAct
} from "@/lib/api";
import type { LegalAct, ProcessingJob, VerificationSummary } from "@/lib/types";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

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
  const [act, setAct] = useState<(LegalAct & { raw_text?: string | null }) | null>(null);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [verificationSummary, setVerificationSummary] = useState<VerificationSummary | null>(null);
  const [metadataForm, setMetadataForm] = useState<MetadataForm | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
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
      <div className="grid">
        {message ? <p>{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {act ? (
          <section className="panel">
            <StatusBadge value={act.processing_status} />
            <h1>{act.title}</h1>
            <p>File: {act.source_file_name}</p>
            <p>Uploaded: {new Date(act.uploaded_at).toLocaleString()}</p>
            <p>Parser: {act.parser_used}</p>
            <p>Pages: {pageCount ?? "Unavailable"}</p>
            <p>Extracted characters: {extractedCharacters ?? "Unavailable"}</p>
            {act.processing_error ? <p className="error">{act.processing_error}</p> : null}
            <div className="toolbar">
              <button onClick={runProcess} disabled={isProcessing}>
                {isProcessing ? "Processing..." : "Process/Reprocess"}
              </button>
              <Link className="button secondary" href={`/admin/acts/${act.id}/sections`}>Review sections</Link>
              <Link className="button secondary" href={`/admin/acts/${act.id}/references`}>Review references</Link>
            </div>
          </section>
        ) : <p>Loading...</p>}
        {act && metadataForm ? (
          <form className="panel grid" onSubmit={saveMetadata}>
            <div>
              <h2>Metadata review</h2>
              <p className="muted">
                Review rule-based metadata before relying on it for search or reference mapping.
              </p>
            </div>
            <div className="grid two">
              <div className="field">
                <label htmlFor="title">Act title</label>
                <input
                  id="title"
                  value={metadataForm.title}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, title: event.target.value })
                  }
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="actNumber">Act number</label>
                <input
                  id="actNumber"
                  value={metadataForm.act_number}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, act_number: event.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="year">Year</label>
                <input
                  id="year"
                  max="2100"
                  min="1800"
                  type="number"
                  value={metadataForm.year}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, year: event.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="category">Category / subject area</label>
                <input
                  id="category"
                  value={metadataForm.category}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, category: event.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="certificationDate">Certification date</label>
                <input
                  id="certificationDate"
                  type="date"
                  value={metadataForm.certification_date}
                  onChange={(event) =>
                    setMetadataForm({
                      ...metadataForm,
                      certification_date: event.target.value
                    })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="publicationDate">Publication date</label>
                <input
                  id="publicationDate"
                  type="date"
                  value={metadataForm.publication_date}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, publication_date: event.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="sourceName">Source name</label>
                <input
                  id="sourceName"
                  value={metadataForm.source_name}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, source_name: event.target.value })
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="sourceUrl">Source URL</label>
                <input
                  id="sourceUrl"
                  value={metadataForm.source_url}
                  onChange={(event) =>
                    setMetadataForm({ ...metadataForm, source_url: event.target.value })
                  }
                />
              </div>
            </div>
            <p>Source filename: {act.source_file_name}</p>
            <p>Processing status: <StatusBadge value={act.processing_status} /></p>
            {metadataSummary ? (
              <div>
                <p>Metadata confidence: {metadataSummary.confidence_score ?? "Unavailable"}</p>
                {metadataSummary.preserved_fields?.length ? (
                  <p>Preserved on reprocessing: {metadataSummary.preserved_fields.join(", ")}</p>
                ) : null}
              </div>
            ) : null}
            {metadataWarnings.length > 0 ? (
              <div>
                <h3>Metadata warnings</h3>
                <ul>
                  {metadataWarnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="toolbar">
              <button type="submit" disabled={isSaving}>
                {isSaving ? "Saving..." : "Save metadata"}
              </button>
            </div>
          </form>
        ) : null}
        {verificationSummary ? (
          <section className="panel">
            <h2>Verification summary</h2>
            <p className="muted">
              Admin review status for extracted sections, references, and mapping corrections.
            </p>
            <div className="toolbar">
              <span>Pending sections: {verificationSummary.pending_sections}</span>
              <span>Needs review sections: {verificationSummary.needs_review_sections}</span>
              <span>Verified sections: {verificationSummary.verified_sections}</span>
              <span>Rejected sections: {verificationSummary.rejected_sections}</span>
            </div>
            <div className="toolbar">
              <span>Pending references: {verificationSummary.pending_references}</span>
              <span>Needs review references: {verificationSummary.needs_review_references}</span>
              <span>Verified references: {verificationSummary.verified_references}</span>
              <span>Rejected references: {verificationSummary.rejected_references}</span>
            </div>
            <div className="toolbar">
              <span>Mapped references: {verificationSummary.mapped_references}</span>
              <span>Unresolved references: {verificationSummary.unresolved_references}</span>
            </div>
          </section>
        ) : null}
        {latestJob ? (
          <section className="panel">
            <h2>Processing job summary</h2>
            <p>
              Latest job: <StatusBadge value={latestJob.status} /> {latestJob.current_step}
            </p>
            <p>Progress: {latestJob.progress_percent}%</p>
            <p>Requested parser: {summary?.parser_requested ?? "Unavailable"}</p>
            <p>Parser used: {summary?.parser_used ?? act?.parser_used ?? "Unavailable"}</p>
            <p>Sections created: {summary?.sections_created ?? 0}</p>
            <p>References created: {summary?.references_created ?? 0}</p>
            {latestJob.completed_at ? (
              <p>Completed: {new Date(latestJob.completed_at).toLocaleString()}</p>
            ) : null}
            {warnings.length > 0 ? (
              <div>
                <h3>Warnings</h3>
                <ul>
                  {warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {errors.length > 0 ? (
              <div>
                <h3>Errors</h3>
                <ul>
                  {errors.map((jobError) => (
                    <li className="error" key={jobError}>{jobError}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : (
          <section className="panel">
            <h2>Processing job summary</h2>
            <p>No processing job has run for this Act yet.</p>
          </section>
        )}
      </div>
    </RoleGuard>
  );
}
