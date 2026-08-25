"use client";

import { BookOpen, Clock3, FolderOpen, Network, Search, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { navItemsForRole } from "@/lib/auth";
import type { Role } from "@/lib/types";

const iconByHref = {
  "/": BookOpen,
  "/browse": BookOpen,
  "/search": Search,
  "/dashboard": Clock3,
  "/admin/acts": FolderOpen,
  "/admin/acts/upload": FolderOpen,
  "/admin/users": ShieldCheck,
  "/admin/evaluation": ShieldCheck,
  "/lawyer/search": Search,
  "/lawyer/relationships": Network,
  "/lawyer/workspace": FolderOpen,
};

export function GlobalSearch({ role }: { role: Role | null }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const items = useMemo(() => navItemsForRole(role), [role]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function navigate(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  function runSearch() {
    const trimmed = query.trim();
    navigate(trimmed ? `/search?q=${encodeURIComponent(trimmed)}` : "/search");
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-8 w-[214px] items-center gap-2 rounded-md border border-border bg-card px-3 text-xs text-muted-foreground shadow-[0_1px_1px_rgba(15,32,51,0.04)] hover:text-foreground sm:w-[300px]"
        aria-label="Search acts, sections, and references"
      >
        <Search className="size-3.5" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-left">Search acts, sections…</span>
        <kbd className="hidden rounded border border-border bg-background px-1.5 py-0.5 font-sans text-[10px] sm:inline-block">
          ⌘K
        </kbd>
      </button>

      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title="Search LexAtlas"
        description="Search verified Acts, sections, references, or open a workspace page."
        className="max-w-xl rounded-lg"
      >
        <CommandInput
          value={query}
          onValueChange={setQuery}
          placeholder="Search acts, sections, references…"
          onKeyDown={(event) => {
            if (event.key === "Enter" && query.trim()) {
              event.preventDefault();
              runSearch();
            }
          }}
        />
        <CommandList>
          <CommandEmpty>
            <button type="button" onClick={runSearch} className="text-primary hover:underline">
              Search LexAtlas for “{query}”
            </button>
          </CommandEmpty>
          {query.trim() ? (
            <CommandGroup heading="Search">
              <CommandItem value={`search ${query}`} onSelect={runSearch}>
                <Search />
                Search for “{query}”
                <CommandShortcut>↵</CommandShortcut>
              </CommandItem>
            </CommandGroup>
          ) : null}
          <CommandGroup heading="Navigate">
            {items.map((item) => {
              const Icon = iconByHref[item.href as keyof typeof iconByHref] ?? BookOpen;
              return (
                <CommandItem key={item.href} value={item.label} onSelect={() => navigate(item.href)}>
                  <Icon />
                  {item.label}
                </CommandItem>
              );
            })}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
