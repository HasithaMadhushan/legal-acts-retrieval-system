"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { VerifiedActList } from "@/components/lexatlas/verified-act-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { listActsBrowse } from "@/lib/api";
import type { LegalActBrowse } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [acts, setActs] = useState<LegalActBrowse[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listActsBrowse()
      .then(setActs)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load verified Acts."))
      .finally(() => setLoading(false));
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      router.push("/search");
      return;
    }
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">
          Find the statute
        </h1>
        <p className="max-w-xl text-[14.5px] leading-[23px] text-muted-foreground">
          Search verified English Acts by title, section text, or mapped statutory reference.
        </p>
      </div>

      <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={submit}>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. Personal Data Protection · Section 12 · repeals"
          className="h-[34px] flex-1 rounded-md border-border bg-[#fffdf8]"
        />
        <Button type="submit" className="h-[34px] px-4">
          Search Acts
        </Button>
      </form>

      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">
          Recently verified
        </p>
        <Link href="/browse" className="text-sm font-medium text-primary no-underline hover:underline">
          Browse all →
        </Link>
      </div>

      {loading ? (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          {[0, 1, 2].map((item) => (
            <div key={item} className="flex items-center gap-4 border-b border-border px-4 py-4 last:border-0">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-6 w-20" />
            </div>
          ))}
        </div>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {!loading && !error ? <VerifiedActList acts={acts.slice(0, 3)} /> : null}

      <p className="pt-4 text-xs text-muted-foreground">
        Corpus · {loading ? "…" : acts.length} verified Acts ·{" "}
        {loading
          ? "…"
          : acts.reduce((total, act) => total + act.verified_section_count, 0).toLocaleString()}{" "}
        sections ·{" "}
        {loading
          ? "…"
          : acts.reduce((total, act) => total + act.verified_reference_count, 0).toLocaleString()}{" "}
        mapped references
      </p>
    </div>
  );
}
