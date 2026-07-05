"use client";

import type { Section } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export function SectionViewer({ section }: { section: Section }) {
  const pageRange =
    section.page_start && section.page_end
      ? `${section.page_start}-${section.page_end}`
      : section.page_start
        ? `${section.page_start}`
        : "Unavailable";

  return (
    <article className="panel">
      <div className="toolbar">
        <StatusBadge value={`Section ${section.section_number}`} />
        <StatusBadge value={section.section_type} />
        <StatusBadge value={section.verification_status} />
      </div>
      <h2>{section.heading ?? `Section ${section.section_number}`}</h2>
      <p className="muted">
        Sort order: {section.sort_order} | Path: {section.section_path ?? "-"} | Pages: {pageRange}
      </p>
      <pre className="section-text">{section.text}</pre>
    </article>
  );
}
