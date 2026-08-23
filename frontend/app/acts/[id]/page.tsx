"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import { OfficialSourceBlock, ResearchNotice } from "@/components/lexatlas/research-notice";
import { VerifiedBadge } from "@/components/lexatlas/verified-badge";
import { buttonVariants } from "@/components/ui/button";
import { getAct, listActReferences, listSections } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { LegalAct, LegalReference, Role, Section } from "@/lib/types";
import { useRecordReading } from "@/hooks/use-record-reading";
import { cn } from "@/lib/utils";
import { SaveItemButton } from "@/components/save-item-button";

type ActTab = "overview" | "sections" | "references";

export default function ActDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [act, setAct] = useState<(LegalAct & { raw_text?: string | null }) | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [references, setReferences] = useState<LegalReference[]>([]);
  const [role, setRole] = useState<Role | null>(null);
  const [tab, setTab] = useState<ActTab>("overview");
  const [error, setError] = useState("");

  useRecordReading({ item_type: "ACT", act_id: id });

  useEffect(() => {
    setRole(getStoredRole());
    Promise.all([getAct(id), listSections(id), listActReferences(id)])
      .then(([actData, sectionData, referenceData]) => {
        setAct(actData);
        setSections(sectionData);
        setReferences(referenceData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load Act."));
  }, [id]);

  const verifiedReferences = useMemo(
    () => references.filter((reference) => reference.verification_status === "VERIFIED"),
    [references]
  );

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!act) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const meta = [
    act.act_number && act.year ? `No. ${act.act_number} of ${act.year}` : null,
    sections.length ? `${sections.length} sections` : null,
    verifiedReferences.length ? `${verifiedReferences.length} references` : null
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-muted-foreground">
        <Link href="/browse" className="text-primary no-underline hover:underline">
          Browse Acts
        </Link>{" "}
        / {act.title}
      </p>

      <div className="flex flex-col gap-3">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">{act.title}</h1>
        <div className="flex flex-wrap items-center gap-3">
          {act.processing_status === "VERIFIED" ? <VerifiedBadge /> : null}
          {meta ? <span className="text-sm text-muted-foreground">{meta}</span> : null}
        </div>
      </div>

      <ResearchNotice />
      <OfficialSourceBlock act={act} />

      <div className="flex flex-wrap gap-1 border-b border-border">
        {(
          [
            ["overview", "Overview"],
            ["sections", "Sections"],
            ["references", "References"]
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={cn(
              "rounded-t-sm px-3.5 py-2 text-sm font-medium",
              tab === value
                ? "border border-b-0 border-border bg-card text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <section className="rounded-sm border border-border bg-card p-4 text-sm leading-relaxed text-foreground">
          {act.raw_text?.trim() ? (
            <p className="whitespace-pre-wrap">{act.raw_text.slice(0, 1800)}{act.raw_text.length > 1800 ? "…" : ""}</p>
          ) : (
            <p className="text-muted-foreground">
              Overview text is not available yet. Open the Sections tab for verified section records.
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            {role === "ADMIN" || role === "LAWYER" ? (
              <>
                <SaveItemButton payload={{ item_type: "ACT", act_id: act.id }} label="Save Act to workspace" />
                <Link
                  href={`/lawyer/relationships?actId=${act.id}`}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Open relationship explorer
                </Link>
              </>
            ) : null}
          </div>
        </section>
      ) : null}

      {tab === "sections" ? (
        <section className="overflow-hidden rounded-sm border border-border">
          {sections.map((section) => (
            <Link
              key={section.id}
              href={`/sections/${section.id}`}
              className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 text-sm no-underline first:border-t hover:bg-muted/40"
            >
              <span>
                Section {section.section_number}: {section.heading ?? "Untitled"}
              </span>
              <span className="text-primary">Open →</span>
            </Link>
          ))}
          {!sections.length ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">No verified sections are available yet.</p>
          ) : null}
        </section>
      ) : null}

      {tab === "references" ? (
        <section className="flex flex-col gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
              Mapped references
            </p>
            <p className="text-sm text-muted-foreground">
              Outgoing and incoming statutory relationships verified for this Act.
            </p>
          </div>
          <div className="overflow-hidden rounded-sm border border-border">
            {verifiedReferences.map((reference) => (
              <article key={reference.id} className="flex items-center gap-3 border-b border-border px-4 py-3 first:border-t">
                <span className="rounded-sm border border-border px-2 py-0.5 text-[10px] font-semibold uppercase">
                  {reference.target_act_id === act.id ? "IN" : "OUT"}
                </span>
                <p className="min-w-0 flex-1 text-sm">
                  {reference.source_section_id ? `Section ${reference.target_section_number ?? "?"}` : reference.raw_reference_text}{" "}
                  {reference.relationship_type.replaceAll("_", " ").toLowerCase()} →{" "}
                  {reference.target_act_title_raw ?? "Mapped target"}
                </p>
                {reference.target_section_id ? (
                  <Link href={`/sections/${reference.target_section_id}`} className="text-sm text-primary no-underline hover:underline">
                    Open →
                  </Link>
                ) : reference.target_act_id ? (
                  <Link href={`/acts/${reference.target_act_id}`} className="text-sm text-primary no-underline hover:underline">
                    Open →
                  </Link>
                ) : null}
              </article>
            ))}
            {!verifiedReferences.length ? (
              <p className="px-4 py-6 text-sm text-muted-foreground">No verified relationships are available yet.</p>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
