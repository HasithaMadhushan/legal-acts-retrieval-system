"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { VerifiedActList } from "@/components/lexatlas/verified-act-row";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
      .then((data) => setActs(data.slice(0, 4)))
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
        <h1 className="font-serif text-4xl font-semibold tracking-tight text-foreground">
          Find the statute
        </h1>
        <p className="max-w-3xl text-base text-muted-foreground">
          Search verified English Acts by title, section text, or mapped statutory reference.
        </p>
      </div>

      <form className="flex flex-col gap-3 sm:flex-row" onSubmit={submit}>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. Personal Data Protection · Section 12 · repeals"
          className="h-11 flex-1 rounded-sm bg-card"
        />
        <Button type="submit" className="h-11 rounded-sm px-5">
          Search Acts
        </Button>
      </form>

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          Recently verified
        </p>
        <Link href="/browse" className="text-sm font-medium text-primary no-underline hover:underline">
          Browse all →
        </Link>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading verified Acts…</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {!loading && !error ? <VerifiedActList acts={acts} /> : null}

      <p className="text-xs text-muted-foreground">
        Demo corpus: sample verified Acts for evaluation screenshots.
      </p>
    </div>
  );
}
