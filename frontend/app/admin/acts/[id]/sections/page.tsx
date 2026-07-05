"use client";

import { FormEvent, use, useEffect, useState } from "react";
import {
  listProcessingJobs,
  listSections,
  rejectSection,
  updateSection,
  verifySection
} from "@/lib/api";
import type { ProcessingJob, Section } from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { SectionViewer } from "@/components/section-viewer";

export default function AdminSectionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [sections, setSections] = useState<Section[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setLoading(true);
      const [sectionData, jobData] = await Promise.all([listSections(id), listProcessingJobs(id)]);
      setSections(sectionData);
      setJobs(jobData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load sections.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function setStatus(id: string, status: "verify" | "reject") {
    setError("");
    setMessage("");
    try {
      if (status === "verify") await verifySection(id);
      else await rejectSection(id);
      setMessage(status === "verify" ? "Section verified." : "Section rejected.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Section update failed.");
    }
  }

  async function saveSection(sectionId: string, payload: Partial<Section>) {
    setError("");
    setMessage("");
    try {
      await updateSection(sectionId, payload);
      setMessage("Section correction saved.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Section edit failed.");
    }
  }

  const latestSummary = jobs[0]?.summary_json?.segmentation;
  const sectionCount =
    latestSummary?.sections_detected ?? sections.filter((section) => section.section_type === "SECTION").length;
  const scheduleCount =
    latestSummary?.schedules_detected ?? sections.filter((section) => section.section_type === "SCHEDULE").length;
  const warnings = latestSummary?.warnings ?? [];
  const filteredSections = sections.filter((section) => {
    if (!statusFilter) return true;
    return section.verification_status === statusFilter;
  });

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts">
      <div className="grid">
        <LegalDisclaimer />
        <section className="panel">
          <h1>Review extracted sections</h1>
          <p className="muted">
            Rule-based segmentation should be checked before sections are treated as reliable.
          </p>
          <div className="toolbar">
            <span>Extracted sections: {sectionCount}</span>
            <span>Schedules: {scheduleCount}</span>
            <span>Total records: {sections.length}</span>
            <span>Pending: {sections.filter((section) => section.verification_status === "PENDING").length}</span>
            <span>Verified: {sections.filter((section) => section.verification_status === "VERIFIED").length}</span>
            <span>Rejected: {sections.filter((section) => section.verification_status === "REJECTED").length}</span>
          </div>
          {latestSummary?.fallback_used ? (
            <p className="error">Fallback segmentation was used for this Act.</p>
          ) : null}
          {latestSummary?.possible_cover_text_removed ? (
            <p className="muted">Possible cover or publication text was removed before section review.</p>
          ) : null}
          {warnings.length > 0 ? (
            <div>
              <h2>Segmentation warnings</h2>
              <ul>
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="field">
            <label htmlFor="sectionStatusFilter">Section status</label>
            <select id="sectionStatusFilter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">Any</option>
              <option value="PENDING">PENDING</option>
              <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
              <option value="VERIFIED">VERIFIED</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>
        </section>
        {message ? <p>{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {loading ? <p>Loading sections...</p> : null}
        {filteredSections.map((section) => (
          <div className="grid" key={section.id}>
            <SectionViewer section={section} />
            <SectionCorrectionForm section={section} onSave={saveSection} onStatus={setStatus} />
          </div>
        ))}
      </div>
    </RoleGuard>
  );
}

function SectionCorrectionForm({
  section,
  onSave,
  onStatus
}: {
  section: Section;
  onSave: (sectionId: string, payload: Partial<Section>) => Promise<void>;
  onStatus: (sectionId: string, status: "verify" | "reject") => Promise<void>;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    await onSave(section.id, {
      section_number: String(formData.get("section_number") ?? ""),
      section_path: optionalString(formData.get("section_path")),
      heading: optionalString(formData.get("heading")),
      section_type: String(formData.get("section_type") ?? section.section_type) as Section["section_type"],
      text: String(formData.get("text") ?? "")
    });
  }

  return (
    <form className="panel grid" onSubmit={submit}>
      <h2>Section correction</h2>
      <p className="muted">
        Preview: {section.text.length > 220 ? `${section.text.slice(0, 220)}...` : section.text}
      </p>
      <div className="grid two">
        <div className="field">
          <label htmlFor={`section-number-${section.id}`}>Section number</label>
          <input id={`section-number-${section.id}`} name="section_number" defaultValue={section.section_number} required />
        </div>
        <div className="field">
          <label htmlFor={`section-path-${section.id}`}>Section path</label>
          <input id={`section-path-${section.id}`} name="section_path" defaultValue={section.section_path ?? ""} />
        </div>
        <div className="field">
          <label htmlFor={`heading-${section.id}`}>Heading</label>
          <input id={`heading-${section.id}`} name="heading" defaultValue={section.heading ?? ""} />
        </div>
        <div className="field">
          <label htmlFor={`section-type-${section.id}`}>Section type</label>
          <select id={`section-type-${section.id}`} name="section_type" defaultValue={section.section_type}>
            <option value="SECTION">SECTION</option>
            <option value="SUBSECTION">SUBSECTION</option>
            <option value="PARAGRAPH">PARAGRAPH</option>
            <option value="SCHEDULE">SCHEDULE</option>
            <option value="PART">PART</option>
            <option value="PREAMBLE">PREAMBLE</option>
            <option value="OTHER">OTHER</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor={`section-text-${section.id}`}>Section text</label>
        <textarea id={`section-text-${section.id}`} name="text" defaultValue={section.text} required />
      </div>
      <div className="toolbar">
        <button type="submit">Save section correction</button>
        <button type="button" onClick={() => onStatus(section.id, "verify")}>Verify</button>
        <button type="button" className="danger" onClick={() => onStatus(section.id, "reject")}>Reject</button>
      </div>
    </form>
  );
}

function optionalString(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text || null;
}
