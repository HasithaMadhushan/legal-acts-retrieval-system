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
import { ReferenceTable } from "@/components/reference-table";
import { RoleGuard } from "@/components/role-guard";
import { Button } from "@/components/ui/button";
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
    const form = event.currentTarget;
    const formData = new FormData(form);
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
      form.reset();
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
      <div className="flex flex-col gap-5">
        <section>
          <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">
            Reference verification
          </h1>
          <p className="mt-2 max-w-3xl text-[14.5px] text-muted-foreground">
            Verify, correct or reject extracted statutory references. Verified references become visible to
            Lawyers and General Users.
          </p>
          <div className="mt-3 flex flex-wrap gap-3 text-sm text-muted-foreground">
            <span>Detected: {latestReferenceSummary?.references_detected ?? references.length}</span>
            <span>
              Unresolved parsed targets:{" "}
              {latestReferenceSummary?.unresolved_target_count ??
                references.filter((reference) => !hasStructuredTarget(reference)).length}
            </span>
            <span>
              Mapped Acts: {latestMappingSummary?.mapped_act_count ?? references.filter(isMapped).length}
            </span>
            <span>
              Unresolved mappings:{" "}
              {latestMappingSummary?.unresolved_count ?? references.filter((reference) => !isMapped(reference)).length}
            </span>
          </div>
          {referenceWarnings.length > 0 ? (
            <div className="mt-4 rounded-lg border border-border bg-card p-4">
              <h2 className="font-serif text-lg font-semibold">Reference extraction warnings</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {referenceWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {mappingWarnings.length > 0 ? (
            <div className="mt-4 rounded-lg border border-border bg-card p-4">
              <h2 className="font-serif text-lg font-semibold">Mapping warnings</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {mappingWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <Card className="rounded-lg">
          <CardContent className="space-y-4 p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Relationship type</Label>
                <Select
                  value={relationshipFilter || "ANY"}
                  onValueChange={(value) => setRelationshipFilter(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ANY">Any</SelectItem>
                    {(
                      ["REFERS_TO", "AMENDS", "REPEALS", "INSERTS", "SUBSTITUTES", "ADDS", "CROSS_REFERENCE"] satisfies RelationshipType[]
                    ).map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Verification status</Label>
                <Select
                  value={statusFilter || "ANY"}
                  onValueChange={(value) => setStatusFilter(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ANY">Any</SelectItem>
                    {(["PENDING", "NEEDS_REVIEW", "VERIFIED", "REJECTED"] satisfies VerificationStatus[]).map(
                      (status) => (
                        <SelectItem key={status} value={status}>
                          {status}
                        </SelectItem>
                      )
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Target status</Label>
                <Select
                  value={targetFilter || "ANY"}
                  onValueChange={(value) => setTargetFilter(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ANY">Any</SelectItem>
                    <SelectItem value="resolved">Mapped target</SelectItem>
                    <SelectItem value="unresolved">Unresolved mapping</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Confidence range</Label>
                <Select
                  value={confidenceFilter || "ANY"}
                  onValueChange={(value) => setConfidenceFilter(value === "ANY" ? "" : (value ?? ""))}
                >
                  <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ANY">Any</SelectItem>
                    <SelectItem value="high">High: 85%+</SelectItem>
                    <SelectItem value="medium">Medium: 60-84%</SelectItem>
                    <SelectItem value="low">Low: under 60%</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            {loading ? <p className="text-sm text-muted-foreground">Loading references...</p> : null}
            <ReferenceTable
              references={filteredReferences}
              admin
              onVerify={verify}
              onReject={reject}
              onUpdate={saveCorrection}
              onLinkTarget={saveMapping}
            />
          </CardContent>
        </Card>

        <details className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <summary className="cursor-pointer font-serif text-xl font-semibold">Manual reference creation</summary>
          <p className="mt-1 text-sm text-muted-foreground">
            Create a manual reference only from verifiable Act text. This does not provide legal advice.
          </p>
          <form className="mt-4 grid gap-3" onSubmit={createManualReference}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="manualSourceAct">Source Act ID</Label>
                <Input id="manualSourceAct" value={id} readOnly className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualSourceSection">Source section ID</Label>
                <Input id="manualSourceSection" name="source_section_id" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualRelationship">Relationship type</Label>
                <select
                  id="manualRelationship"
                  name="relationship_type"
                  defaultValue="REFERS_TO"
                  className="h-9 w-full rounded-md border border-input bg-[#fffdf8] px-3 text-sm"
                >
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
              <div className="space-y-1.5">
                <Label htmlFor="manualStatus">Verification status</Label>
                <select
                  id="manualStatus"
                  name="verification_status"
                  defaultValue="NEEDS_REVIEW"
                  className="h-9 w-full rounded-md border border-input bg-[#fffdf8] px-3 text-sm"
                >
                  <option value="PENDING">PENDING</option>
                  <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
                  <option value="VERIFIED">VERIFIED</option>
                  <option value="REJECTED">REJECTED</option>
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="manualRaw">Raw matched text</Label>
              <Input id="manualRaw" name="raw_reference_text" required className="bg-[#fffdf8]" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="manualContext">Context snippet</Label>
              <textarea
                id="manualContext"
                name="context_snippet"
                required
                className="min-h-20 w-full rounded-md border border-input bg-[#fffdf8] px-3 py-2 text-sm"
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetTitle">Target Act title</Label>
                <Input id="manualTargetTitle" name="target_act_title_raw" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetNumber">Target Act number</Label>
                <Input id="manualTargetNumber" name="target_act_number" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetYear">Target Act year</Label>
                <Input id="manualTargetYear" name="target_act_year" inputMode="numeric" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetSection">Target section</Label>
                <Input id="manualTargetSection" name="target_section_number" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetPath">Target path</Label>
                <Input id="manualTargetPath" name="target_section_path" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualConfidence">Confidence score</Label>
                <Input
                  id="manualConfidence"
                  name="confidence_score"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  defaultValue={0.5}
                  className="bg-[#fffdf8]"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetActId">Mapped target Act ID</Label>
                <Input id="manualTargetActId" name="target_act_id" className="bg-[#fffdf8]" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="manualTargetSectionId">Mapped target section ID</Label>
                <Input id="manualTargetSectionId" name="target_section_id" className="bg-[#fffdf8]" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="manualNotes">Review notes</Label>
              <textarea
                id="manualNotes"
                name="notes"
                className="min-h-20 w-full rounded-md border border-input bg-[#fffdf8] px-3 py-2 text-sm"
              />
            </div>
            <Button type="submit">Create manual reference</Button>
          </form>
        </details>
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
