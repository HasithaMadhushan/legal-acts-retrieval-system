"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ResearchNotice } from "@/components/lexatlas/research-notice";
import { VerifiedBadge } from "@/components/lexatlas/verified-badge";
import { getAct, getSection, listSectionReferences, listSections } from "@/lib/api";
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
  const [relatedSections, setRelatedSections] = useState<Section[]>([]);
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
        return Promise.all([getAct(data.act_id), listSectionReferences(data.id), listSections(data.act_id)]);
      })
      .then(([actData, referenceData, sectionData]) => {
        setAct(actData);
        setReferences(referenceData);
        const currentIndex = sectionData.findIndex((item) => item.id === id);
        setRelatedSections(sectionData.filter((item, index) => item.id !== id && Math.abs(index - currentIndex) <= 1).slice(0, 2));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load section."));
  }, [id]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!section || !act) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const verifiedReferences = references.filter(
    (reference) => reference.verification_status === "VERIFIED"
  );

  return (
    <div className="mx-auto flex w-full max-w-[900px] flex-col gap-6">
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          <Link href="/browse" className="text-primary hover:underline">Browse Acts</Link>{"  /  "}
          <Link href={`/acts/${act.id}`} className="text-primary hover:underline">{act.title}</Link>
        </p>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">
              Section {section.section_number}{section.heading ? ` — ${section.heading}` : ""}
            </h1>
            <p className="mt-1 text-xs text-muted-foreground">{act.title}</p>
          </div>
          {section.verification_status === "VERIFIED" ? <VerifiedBadge className="mt-1 w-fit" /> : null}
        </div>
        <section className="rounded-lg border border-border bg-card px-7 py-7 shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
          <p className="whitespace-pre-wrap font-serif text-base leading-[1.7] text-foreground">{section.text}</p>
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

      <section className="flex flex-col gap-3">
        <p className="text-xs font-semibold tracking-[0.14em] text-[#92681f] uppercase">References involving this section</p>
        {verifiedReferences.map((reference) => (
          <article key={reference.id} className="rounded-lg border border-[#22684a] bg-card px-4 py-3.5">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-md bg-[#faf0f1] px-2 py-1 font-semibold text-[#8c2433]">↔ {reference.relationship_type.replaceAll("_", " ")}</span>
              <span className="text-muted-foreground">confidence {reference.confidence_score.toFixed(2)} · verified by Admin</span>
            </div>
            <p className="mt-2 text-sm">
              This section {reference.relationship_type.replaceAll("_", " ").toLowerCase()} → <strong>{reference.target_act_title_raw ?? "Mapped target"}</strong>
              {reference.target_section_number ? `, section ${reference.target_section_number}` : ""}
            </p>
            <p className="sr-only">Reference evidence: {reference.raw_reference_text}</p>
          </article>
        ))}
        {!verifiedReferences.length ? (
          <p className="text-sm text-muted-foreground">No verified references from this section yet.</p>
        ) : null}
      </section>

      {relatedSections.length ? (
        <section className="flex flex-col gap-2">
          <p className="text-xs font-semibold tracking-[0.14em] text-[#92681f] uppercase">Related sections in this Act</p>
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            {relatedSections.map((item) => (
              <Link key={item.id} href={`/sections/${item.id}`} className="flex items-center justify-between border-b border-border px-4 py-3 last:border-0 hover:bg-muted/30">
                <span className="font-serif text-sm font-semibold">Section {item.section_number}{item.heading ? ` — ${item.heading}` : ""}</span>
                <span className="text-sm text-primary">Open →</span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <ResearchNotice>
        Reading history is recorded automatically while you are signed in. Saving Acts and sections is available in the Lawyer workspace.
      </ResearchNotice>
    </div>
  );
}
