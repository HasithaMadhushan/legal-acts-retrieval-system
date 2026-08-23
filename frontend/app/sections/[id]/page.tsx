"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { OfficialSourceBlock, ResearchNotice } from "@/components/lexatlas/research-notice";
import { VerifiedBadge } from "@/components/lexatlas/verified-badge";
import { getAct, getSection, listSectionReferences } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { LegalAct, LegalReference, Role, Section } from "@/lib/types";
import { useRecordReading } from "@/hooks/use-record-reading";
import { SaveItemButton } from "@/components/save-item-button";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function SectionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [section, setSection] = useState<Section | null>(null);
  const [act, setAct] = useState<LegalAct | null>(null);
  const [references, setReferences] = useState<LegalReference[]>([]);
  const [role, setRole] = useState<Role | null>(null);
  const [error, setError] = useState("");

  useRecordReading({
    item_type: "SECTION",
    act_id: section?.act_id ?? "",
    section_id: id
  });

  useEffect(() => {
    setRole(getStoredRole());
    getSection(id)
      .then((data) => {
        setSection(data);
        return Promise.all([getAct(data.act_id), listSectionReferences(data.id)]);
      })
      .then(([actData, referenceData]) => {
        setAct(actData);
        setReferences(referenceData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load section."));
  }, [id]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!section || !act) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const verifiedReferences = references.filter(
    (reference) => reference.verification_status === "VERIFIED"
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_332px]">
      <div className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          <Link href={`/acts/${act.id}`} className="text-primary no-underline hover:underline">
            {act.title}
          </Link>{" "}
          / Section {section.section_number}
        </p>
        <h1 className="font-serif text-3xl font-semibold tracking-tight">
          Section {section.section_number}
          {section.heading ? ` — ${section.heading}` : ""}
        </h1>
        {section.verification_status === "VERIFIED" ? <VerifiedBadge className="w-fit" /> : null}
        <ResearchNotice />
        <OfficialSourceBlock act={act} />
        <section className="rounded-sm border border-border bg-card p-4">
          <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
            Statute text
          </p>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-foreground">{section.text}</p>
        </section>
        {role === "ADMIN" || role === "LAWYER" ? (
          <div className="flex flex-wrap gap-2">
            <SaveItemButton payload={{ item_type: "SECTION", section_id: section.id }} label="Save Section to workspace" />
            <Link
              href={`/lawyer/relationships?sectionId=${section.id}`}
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              Open relationship explorer
            </Link>
          </div>
        ) : null}
      </div>

      <aside className="flex flex-col gap-4">
        <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          Mapped references
        </p>
        {verifiedReferences.map((reference) => (
          <article key={reference.id} className="rounded-sm border border-border bg-card p-3.5">
            <p className="text-sm font-medium text-foreground">
              Section {section.section_number} → {reference.relationship_type.replaceAll("_", " ")}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              {reference.target_act_title_raw ?? "Mapped target"}
              {reference.target_section_number ? ` · Section ${reference.target_section_number}` : ""}
            </p>
            <div className="mt-3 rounded-sm border border-border bg-muted/30 p-2.5">
              <p className="text-[10px] font-semibold tracking-[0.12em] text-muted-foreground uppercase">
                Reference evidence
              </p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                Detected phrase: “{reference.raw_reference_text.slice(0, 120)}
                {reference.raw_reference_text.length > 120 ? "…" : ""}” · Target provision:{" "}
                {reference.target_section_number ?? "Act-level"} · Confidence:{" "}
                {reference.confidence_score >= 0.75 ? "high" : reference.confidence_score >= 0.5 ? "medium" : "low"}
              </p>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Verified by Admin</p>
          </article>
        ))}
        {!verifiedReferences.length ? (
          <p className="text-sm text-muted-foreground">No verified references from this section yet.</p>
        ) : null}
        <p className={cn("text-xs text-muted-foreground")}>
          Saving Acts and sections is available in the Lawyer workspace.
        </p>
      </aside>
    </div>
  );
}
