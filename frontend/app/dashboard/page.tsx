"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ResearchNotice } from "@/components/lexatlas/research-notice";
import { listReadingHistory } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { ReadingHistoryItem, Role } from "@/lib/types";

export default function DashboardPage() {
  const [role, setRole] = useState<Role | null>(null);
  const [items, setItems] = useState<ReadingHistoryItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setRole(getStoredRole());
    listReadingHistory()
      .then((response) => setItems(response.items))
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load recent reading."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-4xl font-semibold tracking-tight">Recent reading</h1>
        <p className="text-base text-muted-foreground">
          Acts and sections you opened recently. Saving research and export belong to the Lawyer workspace.
        </p>
      </div>

      <ResearchNotice />

      <p className="text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
        Continue reading
      </p>

      {loading ? <p className="text-sm text-muted-foreground">Loading recent reading…</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {!loading && !error && items.length ? (
        <div className="overflow-hidden rounded-sm border border-border">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 border-b border-border px-3.5 py-3 first:border-t"
            >
              <p className="min-w-0 text-sm text-foreground">
                {item.item_type === "SECTION" && item.section_number
                  ? `${item.act_title} — Section ${item.section_number}${item.section_heading ? ` · ${item.section_heading}` : ""}`
                  : item.act_title}
              </p>
              <Link href={item.href} className="shrink-0 text-sm font-medium text-primary no-underline hover:underline">
                Open →
              </Link>
            </div>
          ))}
        </div>
      ) : null}

      {!loading && !error && !items.length ? (
        <p className="text-sm text-muted-foreground">
          No recent reading yet. Open an Act or section from Browse or Search to populate this list.
        </p>
      ) : null}

      <p className="text-xs text-muted-foreground">
        {role === "LAWYER" || role === "ADMIN"
          ? "Use Lawyer → Workspace to manage saved research and exports."
          : "No saved Acts, sections, or references on this role. Open Lawyer → Workspace to manage saved research."}
      </p>
    </div>
  );
}
