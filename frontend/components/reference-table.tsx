"use client";

import type { FormEvent, MouseEvent } from "react";
import type { LegalReference } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

type LinkTargetPayload = {
  target_act_id: string | null;
  target_section_id: string | null;
  notes?: string | null;
};

export function ReferenceTable({
  references,
  onVerify,
  onReject,
  onUpdate,
  onLinkTarget,
  admin = false
}: {
  references: LegalReference[];
  onVerify?: (id: string) => void;
  onReject?: (id: string) => void;
  onUpdate?: (id: string, payload: Partial<LegalReference>) => void | Promise<void>;
  onLinkTarget?: (id: string, payload: LinkTargetPayload) => void | Promise<void>;
  admin?: boolean;
}) {
  if (!references.length) return <div className="empty">No references found.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Source section</th>
            <th>Raw reference</th>
            <th>Relationship</th>
            <th>Target</th>
            <th>Confidence</th>
            <th>Status</th>
            {admin ? <th>Actions</th> : null}
          </tr>
        </thead>
        <tbody>
          {references.map((reference) => (
            <tr key={reference.id}>
              <td>{reference.source_section_id ?? "Act-level"}</td>
              <td>
                <strong>{reference.raw_reference_text}</strong>
                <p className="muted">{reference.context_snippet}</p>
              </td>
              <td><StatusBadge value={reference.relationship_type} /></td>
              <td>
                <div>{reference.target_act_title_raw ?? "No target title detected"}</div>
                {reference.target_act_number || reference.target_act_year ? (
                  <div className="muted">
                    Act No. {reference.target_act_number ?? "-"} {reference.target_act_year ? `of ${reference.target_act_year}` : ""}
                  </div>
                ) : null}
                {reference.target_section_number ? (
                  <div className="muted">Section/subsection/paragraph: {reference.target_section_number}</div>
                ) : null}
                {reference.target_section_path ? (
                  <div className="muted">Target path: {reference.target_section_path}</div>
                ) : null}
                {reference.target_act_id ? (
                  <div className="muted">Mapped target Act ID: {reference.target_act_id}</div>
                ) : null}
                {reference.target_section_id ? (
                  <div className="muted">Mapped target section ID: {reference.target_section_id}</div>
                ) : null}
                {!reference.target_act_id ? (
                  <div className="status warning">Unresolved mapping</div>
                ) : (
                  <div className="status success">Mapped target</div>
                )}
              </td>
              <td>{Math.round(reference.confidence_score * 100)}%</td>
              <td><StatusBadge value={reference.verification_status} /></td>
              {admin ? (
                <td>
                  <div className="toolbar">
                    <button onClick={() => onVerify?.(reference.id)}>Verify</button>
                    <button className="danger" onClick={() => onReject?.(reference.id)}>Reject</button>
                  </div>
                  {onUpdate ? (
                    <ReferenceCorrectionForm
                      reference={reference}
                      onUpdate={onUpdate}
                      onLinkTarget={onLinkTarget}
                    />
                  ) : null}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReferenceCorrectionForm({
  reference,
  onUpdate,
  onLinkTarget
}: {
  reference: LegalReference;
  onUpdate: (id: string, payload: Partial<LegalReference>) => void | Promise<void>;
  onLinkTarget?: (id: string, payload: LinkTargetPayload) => void | Promise<void>;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    await onUpdate(reference.id, referencePayload(formData));
  }

  async function linkMapping(event: MouseEvent<HTMLButtonElement>) {
    const form = event.currentTarget.form;
    if (!form || !onLinkTarget) return;
    const formData = new FormData(form);
    await onLinkTarget(reference.id, {
      target_act_id: optionalString(formData.get("target_act_id")),
      target_section_id: optionalString(formData.get("target_section_id")),
      notes: optionalString(formData.get("notes"))
    });
  }

  return (
    <details>
      <summary>Correct reference</summary>
      <form className="grid" onSubmit={submit}>
        <div className="field">
          <label htmlFor={`raw-${reference.id}`}>Raw matched text</label>
          <input id={`raw-${reference.id}`} name="raw_reference_text" defaultValue={reference.raw_reference_text} required />
        </div>
        <div className="field">
          <label htmlFor={`context-${reference.id}`}>Context snippet</label>
          <textarea id={`context-${reference.id}`} name="context_snippet" defaultValue={reference.context_snippet} required />
        </div>
        <div className="grid two">
          <div className="field">
            <label htmlFor={`relationship-${reference.id}`}>Relationship type</label>
            <select id={`relationship-${reference.id}`} name="relationship_type" defaultValue={reference.relationship_type}>
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
            <label htmlFor={`status-${reference.id}`}>Verification status</label>
            <select id={`status-${reference.id}`} name="verification_status" defaultValue={reference.verification_status}>
              <option value="PENDING">PENDING</option>
              <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
              <option value="VERIFIED">VERIFIED</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>
        </div>
        <div className="grid two">
          <div className="field">
            <label htmlFor={`target-title-${reference.id}`}>Target Act title</label>
            <input id={`target-title-${reference.id}`} name="target_act_title_raw" defaultValue={reference.target_act_title_raw ?? ""} />
          </div>
          <div className="field">
            <label htmlFor={`target-number-${reference.id}`}>Target Act number</label>
            <input id={`target-number-${reference.id}`} name="target_act_number" defaultValue={reference.target_act_number ?? ""} />
          </div>
          <div className="field">
            <label htmlFor={`target-year-${reference.id}`}>Target Act year</label>
            <input id={`target-year-${reference.id}`} name="target_act_year" defaultValue={reference.target_act_year ?? ""} inputMode="numeric" />
          </div>
          <div className="field">
            <label htmlFor={`target-section-${reference.id}`}>Target section/path</label>
            <input id={`target-section-${reference.id}`} name="target_section_number" defaultValue={reference.target_section_number ?? ""} />
          </div>
          <div className="field">
            <label htmlFor={`target-path-${reference.id}`}>Target path</label>
            <input id={`target-path-${reference.id}`} name="target_section_path" defaultValue={reference.target_section_path ?? ""} />
          </div>
          <div className="field">
            <label htmlFor={`confidence-${reference.id}`}>Confidence score</label>
            <input id={`confidence-${reference.id}`} name="confidence_score" type="number" min="0" max="1" step="0.01" defaultValue={reference.confidence_score} />
          </div>
          <div className="field">
            <label htmlFor={`target-act-id-${reference.id}`}>Mapped target Act ID</label>
            <input id={`target-act-id-${reference.id}`} name="target_act_id" defaultValue={reference.target_act_id ?? ""} />
          </div>
          <div className="field">
            <label htmlFor={`target-section-id-${reference.id}`}>Mapped target section ID</label>
            <input id={`target-section-id-${reference.id}`} name="target_section_id" defaultValue={reference.target_section_id ?? ""} />
          </div>
        </div>
        <div className="field">
          <label htmlFor={`notes-${reference.id}`}>Review notes</label>
          <textarea id={`notes-${reference.id}`} name="notes" defaultValue={reference.notes ?? ""} />
        </div>
        <div className="toolbar">
          <button type="submit">Save correction</button>
          <button type="button" onClick={linkMapping}>Link mapping</button>
          <button type="button" className="danger" onClick={() => onLinkTarget?.(reference.id, {
            target_act_id: null,
            target_section_id: null,
            notes: "Mapping cleared during Admin review."
          })}>Clear mapping</button>
        </div>
      </form>
    </details>
  );
}

function referencePayload(formData: FormData): Partial<LegalReference> {
  return {
    raw_reference_text: String(formData.get("raw_reference_text") ?? ""),
    context_snippet: String(formData.get("context_snippet") ?? ""),
    relationship_type: String(formData.get("relationship_type")) as LegalReference["relationship_type"],
    target_act_title_raw: optionalString(formData.get("target_act_title_raw")),
    target_act_number: optionalString(formData.get("target_act_number")),
    target_act_year: optionalNumber(formData.get("target_act_year")),
    target_section_number: optionalString(formData.get("target_section_number")),
    target_section_path: optionalString(formData.get("target_section_path")),
    target_act_id: optionalString(formData.get("target_act_id")),
    target_section_id: optionalString(formData.get("target_section_id")),
    confidence_score: optionalNumber(formData.get("confidence_score")) ?? 0,
    verification_status: String(formData.get("verification_status")) as LegalReference["verification_status"],
    notes: optionalString(formData.get("notes"))
  };
}

function optionalString(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text || null;
}

function optionalNumber(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text ? Number(text) : null;
}
