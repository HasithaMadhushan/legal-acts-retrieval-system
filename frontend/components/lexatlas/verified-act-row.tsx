import Link from "next/link";
import type { LegalActBrowse } from "@/lib/types";
import { VerifiedBadge } from "@/components/lexatlas/verified-badge";
import { cn } from "@/lib/utils";

function formatActMeta(act: LegalActBrowse) {
  const parts: string[] = [];
  if (act.act_number && act.year) {
    parts.push(`No. ${act.act_number} of ${act.year}`);
  } else if (act.year) {
    parts.push(String(act.year));
  }
  if (act.verified_section_count) {
    parts.push(`${act.verified_section_count} sections`);
  }
  if (act.verified_reference_count) {
    parts.push(`${act.verified_reference_count} references`);
  }
  if (act.last_verified_at) {
    parts.push(`Last verified ${new Date(act.last_verified_at).toLocaleDateString()}`);
  }
  return parts.join(" · ");
}

export function VerifiedActRow({
  act,
  className
}: {
  act: LegalActBrowse;
  className?: string;
}) {
  return (
    <article
      className={cn(
        "flex items-center gap-4 border-b border-border bg-card px-4 py-3.5 first:border-t",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        <h2 className="font-serif text-base font-semibold text-foreground">{act.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{formatActMeta(act)}</p>
      </div>
      <VerifiedBadge />
      <Link
        href={`/acts/${act.id}`}
        className="shrink-0 text-sm font-medium text-primary no-underline hover:underline"
      >
        View Act →
      </Link>
    </article>
  );
}

export function VerifiedActList({
  acts,
  emptyMessage = "No verified Acts are available yet."
}: {
  acts: LegalActBrowse[];
  emptyMessage?: string;
}) {
  if (!acts.length) {
    return (
      <div className="rounded-sm border border-dashed border-border px-4 py-8 text-sm text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-sm border border-border">
      {acts.map((act) => (
        <VerifiedActRow key={act.id} act={act} />
      ))}
    </div>
  );
}
