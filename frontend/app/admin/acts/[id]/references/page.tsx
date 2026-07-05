"use client";

import { FormEvent, use, useEffect, useState } from "react";
import {
  createReference,
  linkReferenceTarget,
  listActReferences,
  listProcessingJobs,
  rejectReference,
  updateReference,
  verifyReference
} from "@/lib/api";
import type {
  LegalReference,
  ProcessingJob,
  ReferenceCreatePayload,
  RelationshipType,
  VerificationStatus
} from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { ReferenceTable } from "@/components/reference-table";
import { RoleGuard } from "@/components/role-guard";

export default function AdminReferencesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [references, setReferences] = useState<LegalReference[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [relationshipFilter, setRelationshipFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      setLoading(true);
      const [referenceData, jobData] = await Promise.all([
        listActReferences(id, true),
        listProcessingJobs(id)
      ]);
      setReferences(referenceData);
      setJobs(jobData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load references.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function verify(id: string) {
    setError("");
    setMessage("");
    try {
      await verifyReference(id);
      setMessage("Reference verified.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reference verification failed.");
    }
  }

  async function reject(id: string) {
    setError("");
    setMessage("");
    try {
      await rejectReference(id);
      setMessage("Reference rejected.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reference rejection failed.");
    }
  }

  async function saveCorrection(id: string, payload: Partial<LegalReference>) {
    setError("");
    setMessage("");
    try {
      await updateReference(id, payload);
      setMessage("Reference correction saved.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reference correction failed.");
    }
  }

  async function saveMapping(
    id: string,
    payload: { target_act_id: string | null; target_section_id: string | null; notes?: string | null }
  ) {
    setError("");
    setMessage("");
    try {
      await linkReferenceTarget(id, payload);
      setMessage(payload.target_act_id || payload.target_section_id ? "Mapping linked." : "Mapping cleared.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mapping correction failed.");
    }
  }

  async function createManualReference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const payload: ReferenceCreatePayload = {
      source_act_id: id,
      source_section_id: optionalString(formData.get("source_section_id")),
      raw_reference_text: String(formData.get("raw_reference_text") ?? ""),
      context_snippet: String(formData.get("context_snippet") ?? ""),
      relationship_type: String(formData.get("relationship_type")) as RelationshipType,
      target_act_title_raw: optionalString(formData.get("target_act_title_raw")),
      target_act_number: optionalString(formData.get("target_act_number")),
      target_act_year: optionalNumber(formData.get("target_act_year")),
      target_section_number: optionalString(formData.get("target_section_number")),
      target_section_path: optionalString(formData.get("target_section_path")),
      target_act_id: optionalString(formData.get("target_act_id")),
      target_section_id: optionalString(formData.get("target_section_id")),
      confidence_score: optionalNumber(formData.get("confidence_score")) ?? 0.5,
      verification_status: String(formData.get("verification_status")) as VerificationStatus,
      notes: optionalString(formData.get("notes"))
    };
    setError("");
    setMessage("");
    try {
      await createReference(payload);
      event.currentTarget.reset();
      setMessage("Manual reference created.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manual reference creation failed.");
    }
  }

  const latestReferenceSummary = jobs[0]?.summary_json?.references;
  const latestMappingSummary = jobs[0]?.summary_json?.mapping;
  const referenceWarnings = latestReferenceSummary?.warnings ?? [];
  const mappingWarnings = latestMappingSummary?.warnings ?? [];
  const filteredReferences = references.filter((reference) => {
    if (relationshipFilter && reference.relationship_type !== relationshipFilter) return false;
    if (statusFilter && reference.verification_status !== statusFilter) return false;
    if (targetFilter === "unresolved" && isMapped(reference)) return false;
    if (targetFilter === "resolved" && !isMapped(reference)) return false;
    if (confidenceFilter === "high" && reference.confidence_score < 0.85) return false;
    if (confidenceFilter === "medium" && (reference.confidence_score < 0.6 || reference.confidence_score >= 0.85)) return false;
    if (confidenceFilter === "low" && reference.confidence_score >= 0.6) return false;
    return true;
  });

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/acts">
      <div className="grid">
        <LegalDisclaimer />
        <section className="panel">
          <h1>Review detected references</h1>
          <p className="muted">References stay pending or need review until an Admin verifies or rejects them.</p>
          <div className="toolbar">
            <span>Detected: {latestReferenceSummary?.references_detected ?? references.length}</span>
            <span>Unresolved parsed targets: {latestReferenceSummary?.unresolved_target_count ?? references.filter((reference) => !hasStructuredTarget(reference)).length}</span>
            <span>Mapped Acts: {latestMappingSummary?.mapped_act_count ?? references.filter(isMapped).length}</span>
            <span>Mapped sections: {latestMappingSummary?.mapped_section_count ?? references.filter((reference) => Boolean(reference.target_section_id)).length}</span>
            <span>Unresolved mappings: {latestMappingSummary?.unresolved_count ?? references.filter((reference) => !isMapped(reference)).length}</span>
          </div>
          {latestReferenceSummary?.by_type ? (
            <p className="muted">
              By type: {Object.entries(latestReferenceSummary.by_type).map(([type, count]) => `${type}: ${count}`).join(", ")}
            </p>
          ) : null}
          {latestMappingSummary?.confidence_bands ? (
            <p className="muted">
              Mapping confidence: {Object.entries(latestMappingSummary.confidence_bands).map(([band, count]) => `${band}: ${count}`).join(", ")}
            </p>
          ) : null}
          {latestMappingSummary ? (
            <p className="muted">
              Principal enactment context used: {latestMappingSummary.principal_context_used_count ?? 0}
            </p>
          ) : null}
          {referenceWarnings.length > 0 ? (
            <div>
              <h2>Reference extraction warnings</h2>
              <ul>
                {referenceWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {mappingWarnings.length > 0 ? (
            <div>
              <h2>Mapping warnings</h2>
              <ul>
                {mappingWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="toolbar">
            <div className="field">
              <label htmlFor="relationshipFilter">Relationship type</label>
              <select id="relationshipFilter" value={relationshipFilter} onChange={(event) => setRelationshipFilter(event.target.value)}>
                <option value="">Any</option>
                {(["REFERS_TO", "AMENDS", "REPEALS", "INSERTS", "SUBSTITUTES", "ADDS", "CROSS_REFERENCE"] satisfies RelationshipType[]).map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="statusFilter">Verification status</label>
              <select id="statusFilter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">Any</option>
                {(["PENDING", "NEEDS_REVIEW", "VERIFIED", "REJECTED"] satisfies VerificationStatus[]).map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="targetFilter">Target status</label>
              <select id="targetFilter" value={targetFilter} onChange={(event) => setTargetFilter(event.target.value)}>
                <option value="">Any</option>
                <option value="resolved">Mapped target</option>
                <option value="unresolved">Unresolved mapping</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="confidenceFilter">Confidence range</label>
              <select id="confidenceFilter" value={confidenceFilter} onChange={(event) => setConfidenceFilter(event.target.value)}>
                <option value="">Any</option>
                <option value="high">High: 85%+</option>
                <option value="medium">Medium: 60-84%</option>
                <option value="low">Low: under 60%</option>
              </select>
            </div>
          </div>
          {message ? <p>{message}</p> : null}
          {error ? <p className="error">{error}</p> : null}
          {loading ? <p>Loading references...</p> : null}
          <ReferenceTable
            references={filteredReferences}
            admin
            onVerify={verify}
            onReject={reject}
            onUpdate={saveCorrection}
            onLinkTarget={saveMapping}
          />
        </section>
        <section className="panel">
          <h2>Manual reference creation</h2>
          <p className="muted">
            Create a manual reference only from verifiable Act text. This does not provide legal advice.
          </p>
          <form className="grid" onSubmit={createManualReference}>
            <div className="grid two">
              <div className="field">
                <label htmlFor="manualSourceAct">Source Act ID</label>
                <input id="manualSourceAct" value={id} readOnly />
              </div>
              <div className="field">
                <label htmlFor="manualSourceSection">Source section ID</label>
                <input id="manualSourceSection" name="source_section_id" />
              </div>
              <div className="field">
                <label htmlFor="manualRelationship">Relationship type</label>
                <select id="manualRelationship" name="relationship_type" defaultValue="REFERS_TO">
                  <option value="REFERS_TO">REFERS_TO</option>
                  <option value="AMENDS">AMENDS</option>
                  <option value="REPEALS">REPEALS</option>
                  <option value="INSERTS">INSERTS</option>
                  <option value="SUBSTITUTES">SUBSTITUTES</option>
                  <option value="ADDS">ADDS</option>
                  <option value="CROSS_REFERENCE">CROSS_REFERENCE</option>
                  <option value="UNKNOWN">UNKNOWN</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="manualStatus">Verification status</label>
                <select id="manualStatus" name="verification_status" defaultValue="NEEDS_REVIEW">
                  <option value="PENDING">PENDING</option>
                  <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
                  <option value="VERIFIED">VERIFIED</option>
                  <option value="REJECTED">REJECTED</option>
                </select>
              </div>
            </div>
            <div className="field">
              <label htmlFor="manualRaw">Raw matched text</label>
              <input id="manualRaw" name="raw_reference_text" required />
            </div>
            <div className="field">
              <label htmlFor="manualContext">Context snippet</label>
              <textarea id="manualContext" name="context_snippet" required />
            </div>
            <div className="grid two">
              <div className="field">
                <label htmlFor="manualTargetTitle">Target Act title</label>
                <input id="manualTargetTitle" name="target_act_title_raw" />
              </div>
              <div className="field">
                <label htmlFor="manualTargetNumber">Target Act number</label>
                <input id="manualTargetNumber" name="target_act_number" />
              </div>
              <div className="field">
                <label htmlFor="manualTargetYear">Target Act year</label>
                <input id="manualTargetYear" name="target_act_year" inputMode="numeric" />
              </div>
              <div className="field">
                <label htmlFor="manualTargetSection">Target section</label>
                <input id="manualTargetSection" name="target_section_number" />
              </div>
              <div className="field">
                <label htmlFor="manualTargetPath">Target path</label>
                <input id="manualTargetPath" name="target_section_path" />
              </div>
              <div className="field">
                <label htmlFor="manualConfidence">Confidence score</label>
                <input id="manualConfidence" name="confidence_score" type="number" min="0" max="1" step="0.01" defaultValue="0.5" />
              </div>
              <div className="field">
                <label htmlFor="manualTargetActId">Mapped target Act ID</label>
                <input id="manualTargetActId" name="target_act_id" />
              </div>
              <div className="field">
                <label htmlFor="manualTargetSectionId">Mapped target section ID</label>
                <input id="manualTargetSectionId" name="target_section_id" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="manualNotes">Review notes</label>
              <textarea id="manualNotes" name="notes" />
            </div>
            <button type="submit">Create manual reference</button>
          </form>
        </section>
      </div>
    </RoleGuard>
  );
}

function hasStructuredTarget(reference: LegalReference) {
  return Boolean(
    reference.target_act_title_raw ||
      reference.target_act_number ||
      reference.target_act_year ||
      reference.target_section_number ||
      reference.target_section_path
  );
}

function isMapped(reference: LegalReference) {
  return Boolean(reference.target_act_id || reference.target_section_id);
}

function optionalString(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text || null;
}

function optionalNumber(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text ? Number(text) : null;
}
