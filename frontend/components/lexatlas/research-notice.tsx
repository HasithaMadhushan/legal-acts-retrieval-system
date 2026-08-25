import { cn } from "@/lib/utils";

export function ResearchNotice({
  className,
  children,
}: {
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <p
      className={cn(
        "rounded-sm border border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground",
        className
      )}
    >
      {children ?? "Research support only. Verify against the official legislation. Not legal advice or consolidated law."}
    </p>
  );
}

export function OfficialSourceBlock({
  act,
  className
}: {
  act: {
    source_name?: string | null;
    source_url?: string | null;
    act_number?: string | null;
    year?: number | null;
    source_file_name: string;
    certification_date?: string | null;
    publication_date?: string | null;
  };
  className?: string;
}) {
  const published = act.publication_date ?? act.certification_date;
  return (
    <section
      className={cn("rounded-sm border border-border bg-card px-3.5 py-3 text-sm", className)}
    >
      <p className="text-xs font-semibold tracking-[0.12em] text-muted-foreground uppercase">
        Official source
      </p>
      <p className="mt-2 font-medium text-foreground">
        {act.source_name ?? "Parliament of Sri Lanka"} · Act PDF
        {act.source_url ? ` · ${act.source_url.replace(/^https?:\/\//, "")}` : ""}
      </p>
      <p className="mt-1 text-muted-foreground">
        {act.act_number && act.year ? `Act No. ${act.act_number} of ${act.year}` : "Act metadata pending"}
        {published ? ` · Certified / published ${new Date(published).toLocaleDateString()}` : ""}
        {` · Source file: ${act.source_file_name}`}
      </p>
      {act.source_url ? (
        <a
          href={act.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-block text-sm font-medium text-primary no-underline hover:underline"
        >
          Open official PDF →
        </a>
      ) : null}
    </section>
  );
}
