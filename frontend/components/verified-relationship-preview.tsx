import Link from "next/link";
import type { LegalReference } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export function VerifiedRelationshipPreview({
  references,
  title = "Verified related information"
}: {
  references: LegalReference[];
  title?: string;
}) {
  const visibleReferences = references.filter(
    (reference) =>
      reference.verification_status === "VERIFIED" &&
      Boolean(reference.target_act_id || reference.target_section_id)
  );

  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="muted">
        These links are extracted references that have been reviewed and mapped. They are for information retrieval only.
      </p>
      {!visibleReferences.length ? (
        <div className="empty">No verified relationships are available yet.</div>
      ) : (
        <div className="grid">
          {visibleReferences.map((reference) => (
            <article className="result" key={reference.id}>
              <div className="toolbar">
                <StatusBadge value={reference.relationship_type} />
                <StatusBadge value="VERIFIED" />
              </div>
              <p>
                <strong>{reference.raw_reference_text}</strong>
              </p>
              <p className="muted">{reference.context_snippet}</p>
              <p className="muted">
                Target: {reference.target_act_title_raw ?? "Mapped target"}
                {reference.target_section_number ? `, section ${reference.target_section_number}` : ""}
                {reference.target_section_path ? `, ${reference.target_section_path}` : ""}
              </p>
              {reference.target_section_id ? (
                <Link className="button secondary" href={`/sections/${reference.target_section_id}`}>
                  Open target section
                </Link>
              ) : reference.target_act_id ? (
                <Link className="button secondary" href={`/acts/${reference.target_act_id}`}>
                  Open target Act
                </Link>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
