import { cn } from "@/lib/utils";

export function LexAtlasMark({
  inverted = false,
  className,
}: {
  inverted?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg viewBox="0 0 48 48" className="size-10 shrink-0" aria-hidden="true">
        <circle
          cx="24"
          cy="24"
          r="22"
          fill="none"
          className={inverted ? "stroke-ring" : "stroke-primary"}
          strokeWidth="1.5"
        />
        <circle
          cx="24"
          cy="24"
          r="17"
          fill="none"
          className={inverted ? "stroke-ring/70" : "stroke-ring"}
          strokeWidth="1"
        />
        <path
          d="M16 31V17h5.2c2.8 0 4.4 1.5 4.4 3.7 0 1.5-.8 2.7-2.2 3.3 1.7.5 2.7 1.8 2.7 3.6 0 2.4-1.8 4.4-5.1 4.4H16zm3.2-8.2h1.7c1.3 0 2-.6 2-1.6s-.7-1.5-2-1.5h-1.7v3.1zm0 2.3V28h2.1c1.5 0 2.3-.7 2.3-1.8s-.8-1.8-2.4-1.8h-2zM32.8 17l-4.6 14h-3.3l-4.6-14h3.4l3 9.8 3-9.8h3.1z"
          className={inverted ? "fill-primary-foreground" : "fill-primary"}
        />
      </svg>
      <div className="flex flex-col leading-none">
        <span
          className={cn(
            "font-serif text-xl tracking-tight",
            inverted ? "text-primary-foreground" : "text-foreground"
          )}
        >
          LexAtlas
        </span>
        <span
          className={cn(
            "mt-1 text-[0.65rem] tracking-[0.22em] uppercase",
            inverted ? "text-ring" : "text-muted-foreground"
          )}
        >
          Legal acts retrieval
        </span>
      </div>
    </div>
  );
}
