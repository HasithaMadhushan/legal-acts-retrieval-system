"use client";

import { useEffect, useMemo, useState } from "react";
import { VerifiedActList } from "@/components/lexatlas/verified-act-row";
import { Button } from "@/components/ui/button";
import { listActsBrowse } from "@/lib/api";
import type { LegalActBrowse } from "@/lib/types";

const PAGE_SIZE = 6;

export default function BrowseActsPage() {
  const [acts, setActs] = useState<LegalActBrowse[]>([]);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listActsBrowse()
      .then(setActs)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load Acts. Login may be required."))
      .finally(() => setLoading(false));
  }, []);

  const visibleActs = useMemo(() => acts.slice(0, visibleCount), [acts, visibleCount]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-4xl font-semibold tracking-tight">Browse Acts</h1>
        <p className="text-base text-muted-foreground">
          {acts.length} verified English Acts in the corpus. Unverified and pending Acts are not shown to General Users.
        </p>
        {!loading ? (
          <p className="text-sm text-muted-foreground">
            Showing {Math.min(visibleCount, acts.length)} of {acts.length}
          </p>
        ) : null}
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading verified Acts…</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {!loading && !error ? (
        <VerifiedActList acts={visibleActs} emptyMessage="No verified Acts are available for browsing." />
      ) : null}

      {!loading && visibleCount < acts.length ? (
        <div>
          <Button
            type="button"
            variant="outline"
            className="rounded-sm"
            onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}
          >
            Show more Acts
          </Button>
        </div>
      ) : null}
    </div>
  );
}
