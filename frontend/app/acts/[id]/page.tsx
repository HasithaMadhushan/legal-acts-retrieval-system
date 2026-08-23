"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { getAct, listActReferences, listSections } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { LegalAct, LegalReference, Role, Section } from "@/lib/types";
import { SaveItemButton } from "@/components/save-item-button";
import { StatusBadge } from "@/components/status-badge";
import { VerifiedRelationshipPreview } from "@/components/verified-relationship-preview";

export default function ActDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [act, setAct] = useState<(LegalAct & { raw_text?: string | null }) | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [references, setReferences] = useState<LegalReference[]>([]);
  const [role, setRole] = useState<Role | null>(null);
  const [error, setError] = useState("");

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

  if (error) return <p className="error">{error}</p>;
  if (!act) return <p>Loading...</p>;

  return (
    <div className="grid">
      <section className="panel">
        <StatusBadge value={act.processing_status} />
        <h1>{act.title}</h1>
        <p className="muted">
          {act.act_number ? `No. ${act.act_number}` : "Act number unavailable"} {act.year ? `of ${act.year}` : ""}
        </p>
        <p>Source file: {act.source_file_name}</p>
        <SaveItemButton payload={{ item_type: "ACT", act_id: act.id }} label="Save Act to workspace" />
        {role === "ADMIN" || role === "LAWYER" ? (
          <Link className="button secondary" href={`/lawyer/relationships?actId=${act.id}`}>
            Open relationship explorer
          </Link>
        ) : null}
      </section>
      <section className="panel">
        <h2>Verified sections</h2>
        <div className="grid">
          {sections.map((section) => (
            <Link key={section.id} href={`/sections/${section.id}`}>
              Section {section.section_number}: {section.heading ?? "Untitled"} <StatusBadge value={section.verification_status} />
            </Link>
          ))}
          {!sections.length ? <div className="empty">No verified sections are available yet.</div> : null}
        </div>
      </section>
      <VerifiedRelationshipPreview references={references} title="Verified relationship preview" />
    </div>
  );
}
