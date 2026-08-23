import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function VerifiedBadge({ className }: { className?: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-sm border-[color:var(--gold)] bg-[color:var(--accent)] px-2 py-0.5 text-[10px] font-semibold tracking-[0.08em] text-[color:var(--accent-foreground)] uppercase",
        className
      )}
    >
      Verified
    </Badge>
  );
}

export function ResultTypeBadge({
  value,
  className
}: {
  value: string;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-sm border-border bg-muted px-2 py-0.5 text-[10px] font-semibold tracking-[0.08em] uppercase",
        className
      )}
    >
      {value}
    </Badge>
  );
}
