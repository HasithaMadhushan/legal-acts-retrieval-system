"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listActs, processAct } from "@/lib/api";
import type { LegalAct } from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

export default function AdminActsPage() {
  const [acts, setActs] = useState<LegalAct[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setActs(await listActs());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load Acts.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runProcess(id: string) {
    setError("");
    try {
      await processAct(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed.");
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
        <LegalDisclaimer />
        <section className="panel">
          <div className="toolbar">
            <h1 className="page-title">Admin Acts</h1>
            <Link className="button" href="/admin/acts/upload">Upload Act PDF</Link>
          </div>
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
                        <button onClick={() => runProcess(act.id)}>Process</button>
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
