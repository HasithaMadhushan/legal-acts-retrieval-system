"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { displayActTitle } from "@/lib/act-display";
import type { DossierActGroup, DossierCitation, DossierSection } from "@/lib/relationship-dossier";
import type { LegalAct, RelationshipSummary } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type RelationshipDossierProps = Readonly<{
  focusLabel: string;
  focusTitle: string;
  focusAct: LegalAct | null;
  summary: RelationshipSummary | undefined;
  sections: DossierSection[];
  hasRendered: boolean;
  loading: boolean;
  expandedKey: string | null;
  onToggleGroup: (key: string) => void;
  onOpenTable: () => void;
  onRefocusAct: (actId: string) => void;
}>;

export function RelationshipDossier({
  focusLabel,
  focusTitle,
  focusAct,
  summary,
  sections,
  hasRendered,
  loading,
  expandedKey,
  onToggleGroup,
  onOpenTable,
  onRefocusAct
}: RelationshipDossierProps) {
  if (!hasRendered && !loading) {
    return (
      <section className="rounded-lg border border-[#e4ddcd] bg-[#fbf9f3] px-8 py-16 text-center shadow-[0_1px_2px_rgba(15,32,51,0.04)]">
        <p className="text-[15px] text-[#14263c]">Choose an Act to load its citing references.</p>
        <p className="mt-2 text-xs text-muted-foreground">
          References are grouped by type, then by the other Act involved.
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="rounded-lg border border-border bg-card px-5 py-5 shadow-sm">
        <p className="text-[11px] font-semibold tracking-[1.1px] text-[#92681f] uppercase">Focus Act</p>
        <h2 className="mt-1.5 font-serif text-[20px] font-semibold tracking-[-0.3px] text-[#14263c]" title={focusTitle}>
          {focusLabel || "Selected Act"}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">{focusMeta(focusAct)}</p>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <StatChip value={summary?.total_results ?? 0} label="References" />
          <StatChip value={summary?.outgoing_count ?? 0} label="Outgoing" />
          <StatChip value={summary?.incoming_count ?? 0} label="Incoming" />
        </div>
        <p className="mt-3 text-[12px] leading-5 text-muted-foreground">
          Click a linked Act or a line on the map to open that group here.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {focusAct ? (
            <Button
              size="sm"
              className="h-[30px] text-[12.5px]"
              render={<Link href={`/acts/${focusAct.id}`} />}
              nativeButton={false}
            >
              Open Act
            </Button>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-[30px] bg-card text-[12.5px]"
            onClick={onOpenTable}
          >
            View all in Table
          </Button>
        </div>
      </header>

      {loading ? <p className="text-sm text-muted-foreground">Loading relationships…</p> : null}

      {!loading && hasRendered && !sections.length ? (
        <div className="rounded-lg border border-dashed border-border bg-card px-4 py-8 text-sm text-muted-foreground">
          No relationships match these filters. Try Table for the full reference list.
        </div>
      ) : null}

      <div className="flex max-h-[min(70vh,720px)] flex-col gap-4 overflow-y-auto pr-0.5">
      {sections.map((section) => (
        <DossierFamilyBlock
          key={section.family}
          section={section}
          expandedKey={expandedKey}
          onToggleGroup={onToggleGroup}
          onOpenTable={onOpenTable}
          onRefocusAct={onRefocusAct}
        />
      ))}
      </div>
    </section>
  );
}

function DossierFamilyBlock({
  section,
  expandedKey,
  onToggleGroup,
  onOpenTable,
  onRefocusAct
}: Readonly<{
  section: DossierSection;
  expandedKey: string | null;
  onToggleGroup: (key: string) => void;
  onOpenTable: () => void;
  onRefocusAct: (actId: string) => void;
}>) {
  const total = section.groups.reduce((sum, group) => sum + group.count, 0);
  return (
    <div className="rounded-lg border border-border bg-card shadow-sm">
      <div className="flex items-baseline justify-between gap-3 border-b border-[#ede8db] px-4 py-3">
        <h3 className="font-serif text-[16px] font-semibold text-[#14263c]">{section.title}</h3>
        <span className="text-[12px] text-muted-foreground">
          {total} citation{total === 1 ? "" : "s"} · {section.groups.length} Act
          {section.groups.length === 1 ? "" : "s"}
        </span>
      </div>
      <div>
        {section.groups.map((group) => (
          <DossierGroupRow
            key={group.key}
            group={group}
            expanded={expandedKey === group.key}
            onToggle={() => onToggleGroup(group.key)}
            onOpenTable={onOpenTable}
            onRefocusAct={onRefocusAct}
          />
        ))}
      </div>
    </div>
  );
}

function DossierGroupRow({
  group,
  expanded,
  onToggle,
  onOpenTable,
  onRefocusAct
}: Readonly<{
  group: DossierActGroup;
  expanded: boolean;
  onToggle: () => void;
  onOpenTable: () => void;
  onRefocusAct: (actId: string) => void;
}>) {
  const label = displayActTitle({
    title: group.counterpartLabel,
    act_number: null,
    year: null,
    source_file_name: null
  });
  const shown = group.citations.slice(0, 8);
  const counterpartId = group.counterpartId;
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (expanded) {
      rowRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [expanded]);

  return (
    <div ref={rowRef} className={cn("border-b border-[#ede8db] last:border-b-0", expanded && "bg-[#fffbf2]")}>
      <button
        type="button"
        className={cn(
          "flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-[#fffdf8]",
          expanded && "bg-[#fffbf2]"
        )}
        aria-expanded={expanded}
        onClick={onToggle}
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate font-serif text-[14.5px] font-semibold text-[#14263c]" title={label}>
            {label}
          </span>
          <span className="mt-1 flex flex-wrap gap-1.5">
            {group.types.map((type) => (
              <span
                key={type}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                  typePillClass(type)
                )}
              >
                {formatType(type)}
              </span>
            ))}
            {group.pending ? (
              <span className="rounded-full border border-dashed border-[#e6d8b4] bg-[#fffdf8] px-2 py-0.5 text-[11px] font-semibold text-[#92681f]">
                Pending
              </span>
            ) : null}
          </span>
        </span>
        <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[12px] font-semibold text-[#14263c]">
          {group.count}
        </span>
      </button>
      {expanded ? (
        <div className="space-y-2 bg-[#fbf9f3] px-4 py-3">
          {shown.map((citation) => (
            <CitationLine key={citation.id} citation={citation} />
          ))}
          {group.count > shown.length ? (
            <button
              type="button"
              className="text-[12px] font-medium text-[#1e3a5f] hover:underline"
              onClick={onOpenTable}
            >
              {group.count - shown.length} more in Table
            </button>
          ) : null}
          {counterpartId ? (
            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                size="sm"
                variant="outline"
                className="h-[28px] bg-card text-[12px]"
                render={<Link href={`/acts/${counterpartId}`} />}
                nativeButton={false}
              >
                Open Act
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-[28px] bg-card text-[12px]"
                onClick={() => onRefocusAct(counterpartId)}
              >
                Focus this Act
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function CitationLine({ citation }: Readonly<{ citation: DossierCitation }>) {
  const sectionHref = citation.sectionId
    ? `/sections/${citation.sectionId}`
    : null;
  const heading = citation.sectionNumber
    ? `s.${citation.sectionNumber}${citation.sectionHeading ? ` · ${citation.sectionHeading}` : ""}`
    : citation.rawText;
  return (
    <div className="rounded-md border border-[#ede8db] bg-card px-3 py-2">
      <div className="flex items-center gap-2">
        <span className={cn("rounded-full border px-2 py-0.5 text-[10.5px] font-semibold", typePillClass(citation.relationshipType))}>
          {formatType(citation.relationshipType)}
        </span>
        {sectionHref ? (
          <Link href={sectionHref} className="min-w-0 truncate text-[12.5px] font-medium text-[#1e3a5f] hover:underline">
            {heading}
          </Link>
        ) : (
          <span className="min-w-0 truncate text-[12.5px] text-[#14263c]">{heading}</span>
        )}
      </div>
      {citation.snippet ? (
        <p className="mt-1 line-clamp-2 text-[11.5px] leading-5 text-muted-foreground">{citation.snippet}</p>
      ) : null}
    </div>
  );
}

function StatChip({ value, label }: Readonly<{ value: number; label: string }>) {
  return (
    <div className="rounded-md border border-[#ede8db] bg-[#fffdf8] px-2.5 py-2 text-center">
      <p className="text-base font-semibold text-[#0b1626]">{value}</p>
      <p className="text-[10.5px] text-muted-foreground">{label}</p>
    </div>
  );
}

function focusMeta(act: LegalAct | null) {
  if (!act) return "Mapped citing references for this Act";
  const parts = [
    act.act_number && act.year ? `No. ${act.act_number} of ${act.year}` : null,
    act.category,
    act.page_count ? `${act.page_count} pages` : null
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Mapped citing references for this Act";
}

function formatType(type: string) {
  return type
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^\w/, (char) => char.toUpperCase());
}

function typePillClass(type: string) {
  if (type.includes("AMEND") || type.includes("REPEAL")) {
    return "border-[#e3c3c8] bg-[#fbf3f4] text-[#8c2433]";
  }
  if (type.includes("INSERT") || type.includes("ADD")) {
    return "border-[#cfe0d4] bg-[#ebf3ee] text-[#22684a]";
  }
  return "border-[#c8d5e2] bg-[#f0f4f8] text-[#1e3a5f]";
}
