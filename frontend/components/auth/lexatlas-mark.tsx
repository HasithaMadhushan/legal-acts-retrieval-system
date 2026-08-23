import { cn } from "@/lib/utils";

type LexAtlasMarkProps = Readonly<{
  inverted?: boolean;
  className?: string;
  /** Compact mark for dark sidebar (Figma Brand/Sidebar). */
  sidebar?: boolean;
}>;

export function LexAtlasMark({
  inverted = false,
  className,
  sidebar = false
}: LexAtlasMarkProps) {
  const light = inverted || sidebar;
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <svg viewBox="0 0 40 40" className="size-10 shrink-0" aria-hidden="true">
        <rect
          x="0.75"
          y="0.75"
          width="38.5"
          height="38.5"
          rx="3"
          fill={sidebar ? "#10243a" : "none"}
          className={light ? "stroke-[color:var(--gold)]" : "stroke-primary"}
          strokeWidth="1.25"
        />
        <rect
          x="2.5"
          y="2.5"
          width="35"
          height="35"
          rx="1.5"
          fill="none"
          className={light ? "stroke-[color:var(--gold)]" : "stroke-ring"}
          strokeWidth="1"
        />
        {/* Column + open statute book mark (Figma Logo/Mark) */}
        <rect x="12.75" y="10.75" width="2" height="16" fill={light ? "#f4efe4" : "#1e3a5f"} />
        <rect x="22.75" y="10.75" width="2" height="16" fill={light ? "#f4efe4" : "#1e3a5f"} />
        <rect x="10.75" y="8.75" width="16" height="2" fill="#c6a15b" />
        <rect x="11.75" y="7.25" width="14" height="1.5" fill={light ? "#f4efe4" : "#fcfaf4"} />
        <rect x="11.75" y="25.75" width="14" height="2.5" fill="#c6a15b" />
        <ellipse cx="14.75" cy="22.75" rx="7" ry="4" fill={sidebar ? "#10243a" : "#1e3a5f"} />
        <ellipse cx="22.75" cy="22.75" rx="7" ry="4" fill={sidebar ? "#10243a" : "#1e3a5f"} />
        <rect x="7.75" y="18.75" width="22" height="5" fill={sidebar ? "#10243a" : "#10243a"} />
        <rect x="18.15" y="19.75" width="1.2" height="6" fill={light ? "#f4efe4" : "#fcfaf4"} />
      </svg>
      <div className="flex min-w-0 flex-col gap-0.5 leading-none">
        <span
          className={cn(
            "font-serif text-xl font-semibold tracking-tight",
            light ? "text-[#f4efe4]" : "text-foreground"
          )}
        >
          LexAtlas
        </span>
        <span
          className={cn(
            "text-[11px] font-medium tracking-[0.02em]",
            light ? "text-[color:var(--gold)]" : "text-muted-foreground"
          )}
        >
          {sidebar ? "Statute & citation retrieval" : "Legal acts retrieval"}
        </span>
      </div>
    </div>
  );
}
