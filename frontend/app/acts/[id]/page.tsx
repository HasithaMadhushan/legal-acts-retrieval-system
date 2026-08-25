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
  const [tab, setTab] = useState<ActTab>("references");
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

      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">{act.title}</h1>
        <div className="flex flex-wrap items-center gap-3">
          {act.processing_status === "VERIFIED" ? <VerifiedBadge /> : null}
          {meta ? <span className="text-sm text-muted-foreground">{meta}</span> : null}
        </div>
        {role === "ADMIN" || role === "LAWYER" ? (
          <div className="mt-1">
            <Link
              href={`/lawyer/relationships?actId=${act.id}`}
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              Open relationship explorer
            </Link>
          </div>
        ) : null}
      </div>

      <OfficialSourceBlock act={act} className="rounded-lg px-5 py-5 shadow-[0_1px_2px_rgba(15,32,51,0.04)]" />

      <div className="flex flex-wrap gap-5 border-b border-border">
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
              "relative px-3 py-2.5 text-sm font-medium",
              tab === value
                ? "text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-[color:var(--gold)]"
                : "text-muted-foreground hover:text-foreground"
            )}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <section className="rounded-lg border border-border bg-card p-5 text-sm leading-relaxed text-foreground">
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
        <section className="overflow-hidden rounded-lg border border-border bg-card">
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
          {verifiedReferences.length ? (
            <div className="flex flex-col gap-3">
              <div className="overflow-x-auto rounded-lg border border-border bg-card px-5 py-5">
                <div className="flex min-w-[620px] items-center justify-center gap-3">
                  <ReferenceNode label={verifiedReferences[0]?.target_act_title_raw ?? "Principal enactment"} muted />
                  <span className="text-xs font-medium text-[#92681f]">amended by →</span>
                  <ReferenceNode label={act.title} focus />
                  <span className="text-xs font-medium text-[#92681f]">refers to →</span>
                  <ReferenceNode label={verifiedReferences[1]?.target_act_title_raw ?? "Mapped target"} muted />
                </div>
              </div>
              {verifiedReferences.map((reference) => (
                <ReferenceCard key={reference.id} reference={reference} actId={act.id} />
              ))}
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">No verified relationships are available yet.</p>
          )}
          <ResearchNotice>
            Sign in as a Lawyer to save references to your workspace or export summaries. This system provides information retrieval support only.
          </ResearchNotice>
        </section>
      ) : null}
    </div>
  );
}

function ReferenceNode({ label, focus = false, muted = false }: { label: string; focus?: boolean; muted?: boolean }) {
  return (
    <div className={cn("max-w-[230px] rounded-md border bg-card px-4 py-3", focus ? "border-[#b8955a]" : "border-border", muted && "text-muted-foreground")}>
      <p className="line-clamp-2 font-serif text-sm font-semibold">{label}</p>
    </div>
  );
}

function ReferenceCard({ reference, actId }: { reference: LegalReference; actId: string }) {
  const incoming = reference.target_act_id === actId;
  const targetHref = reference.target_section_id
    ? `/sections/${reference.target_section_id}`
    : reference.target_act_id
      ? `/acts/${reference.target_act_id}`
      : null;
  return (
    <article className="flex items-start gap-3 rounded-lg border border-[#22684a] bg-card px-4 py-3.5">
      <span className="rounded-md bg-muted px-2 py-1 text-[10px] font-semibold uppercase">{incoming ? "IN" : "OUT"}</span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {reference.source_section_id ? `Section ${reference.target_section_number ?? "?"}` : reference.raw_reference_text}{" "}
          {reference.relationship_type.replaceAll("_", " ").toLowerCase()} →{" "}
          <strong>{reference.target_act_title_raw ?? "Mapped target"}</strong>
        </p>
        <p className="mt-1.5 text-xs text-muted-foreground">Verified span · confidence {reference.confidence_score.toFixed(2)}</p>
      </div>
      {targetHref ? <Link href={targetHref} className="shrink-0 text-sm font-medium text-primary hover:underline">Open →</Link> : null}
    </article>
  );
}
