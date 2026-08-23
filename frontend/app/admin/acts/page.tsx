"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getEvaluationMetricsSummary, listActs, processAct } from "@/lib/api";
import type { EvaluationMetricsSummary, LegalAct } from "@/lib/types";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

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
    load();
  }, []);

  async function pollActUntilFinished(id: string) {
    for (let attempt = 0; attempt < PROCESSING_POLL_MAX_ATTEMPTS; attempt += 1) {
      const updated = await listActs();
      setActs(updated);
      const act = updated.find((item) => item.id === id);
      if (!act || act.processing_status !== "PROCESSING") return;
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
    return new Date(value).toLocaleString();
  }

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts">
      <div className="grid">
        <section className="panel">
          <div className="toolbar">
            <h1 className="page-title">Admin Acts</h1>
            <Link className="button" href="/admin/acts/upload">Upload Act PDF</Link>
          </div>
          {metrics ? (
            <div className="grid two">
              <RegistryStatCard title="Acts" value={metrics.document_counts.total ?? acts.length} />
              <RegistryStatCard title="Verified sections" value={metrics.section_counts.verified ?? 0} />
              <RegistryStatCard title="Verified refs" value={metrics.reference_counts.verified ?? 0} />
              <RegistryStatCard
                title="Needs review"
                value={(metrics.section_counts.needs_review ?? 0) + (metrics.reference_counts.needs_review ?? 0)}
              />
            </div>
          ) : null}
          {error ? <p className="error">{error}</p> : null}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Source file</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>Number/Year</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {acts.map((act) => (
                  <tr key={act.id}>
                    <td><Link href={`/admin/acts/${act.id}`}>{act.title}</Link></td>
                    <td>{act.source_file_name}</td>
                    <td>{formatFileSize(act.file_size)}</td>
                    <td>{formatDate(act.uploaded_at)}</td>
                    <td>{act.act_number ?? "-"} {act.year ?? ""}</td>
                    <td><StatusBadge value={act.processing_status} /></td>
                    <td>
                      <div className="toolbar">
                        <button onClick={() => runProcess(act.id)} disabled={processingIds.has(act.id)}>
                          {processingIds.has(act.id) ? "Processing..." : "Process"}
                        </button>
                        <Link className="button secondary" href={`/admin/acts/${act.id}/references`}>References</Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </RoleGuard>
  );
}

function RegistryStatCard({ title, value }: { title: string; value: number }) {
  return (
    <article className="panel">
      <p className="text-xs font-semibold tracking-[0.12em] text-muted-foreground uppercase">{title}</p>
      <p className="mt-2 font-serif text-3xl font-semibold text-foreground">{value}</p>
    </article>
  );
}
