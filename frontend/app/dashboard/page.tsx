"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ResearchNotice } from "@/components/lexatlas/research-notice";
import { listReadingHistory } from "@/lib/api";
import { getStoredRole } from "@/lib/auth";
import type { ReadingHistoryItem, Role } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

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
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Recent reading</h1>
        <p className="mt-2 text-[14.5px] text-muted-foreground">
          Acts and sections you opened recently. Saving research and export belong to the Lawyer workspace.
        </p>
      </div>

      <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">
        Continue reading
      </p>

      {loading ? (
        <div className="space-y-px overflow-hidden rounded-lg border border-border bg-card p-3">
          {[0, 1, 2].map((item) => <Skeleton key={item} className="h-16 w-full rounded-md" />)}
        </div>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {!loading && !error && items.length ? (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-4 border-b border-border px-4 py-3.5 last:border-0"
            >
              <div className="min-w-0 flex-1">
                <p className="font-serif text-sm font-semibold text-foreground">
                  {item.item_type === "SECTION" && item.section_number
                    ? `${item.act_title} — Section ${item.section_number}${item.section_heading ? ` · ${item.section_heading}` : ""}`
                    : item.act_title}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Opened {formatViewedAt(item.viewed_at)}</p>
              </div>
              <Link href={item.href} className="shrink-0 text-sm font-medium text-primary no-underline hover:underline">
                Resume →
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

      <ResearchNotice>
        {role === "LAWYER" || role === "ADMIN"
          ? "Use Lawyer → Workspace to manage saved research and exports."
          : "No saved Acts, sections, or references on this role. Open Lawyer → Workspace to manage saved research."}
      </ResearchNotice>
    </div>
  );
}

function formatViewedAt(value: string) {
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return `today, ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }
  return date.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
