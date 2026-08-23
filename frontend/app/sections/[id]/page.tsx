"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { getSection, listSectionReferences } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { LegalReference, Role, Section } from "@/lib/types";
import { SaveItemButton } from "@/components/save-item-button";
import { SectionViewer } from "@/components/section-viewer";
import { VerifiedRelationshipPreview } from "@/components/verified-relationship-preview";

export default function SectionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [section, setSection] = useState<Section | null>(null);
  const [references, setReferences] = useState<LegalReference[]>([]);
  const [role, setRole] = useState<Role | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setRole(getStoredRole());
    getSection(id)
      .then((data) => {
        setSection(data);
        return listSectionReferences(data.id);
      })
      .then(setReferences)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load section."));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!section) return <p>Loading...</p>;

  return (
    <div className="grid">
      <SectionViewer section={section} />
      <SaveItemButton payload={{ item_type: "SECTION", section_id: section.id }} label="Save Section to workspace" />
      {role === "ADMIN" || role === "LAWYER" ? (
        <Link className="button secondary" href={`/lawyer/relationships?sectionId=${section.id}`}>
          Open relationship explorer
        </Link>
      ) : null}
      <VerifiedRelationshipPreview references={references} title="Verified references from this section" />
    </div>
  );
}
