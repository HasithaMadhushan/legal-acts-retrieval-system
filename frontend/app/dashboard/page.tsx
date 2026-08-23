"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getStoredRole } from "@/lib/auth";
import type { Role } from "@/lib/types";

export default function DashboardPage() {
  const [role, setRole] = useState<Role | null>(null);

  useEffect(() => setRole(getStoredRole()), []);

  return (
    <div className="grid">
      <section className="panel">
        <h1>Dashboard</h1>
        <p className="muted">Current role: {role ?? "Not logged in"}</p>
        {role === "GENERAL_USER" || !role ? (
          <p className="muted">
            General Users can search and browse verified legal information only. This dashboard does not provide legal advice.
          </p>
        ) : null}
        <div className="toolbar">
          {role === "ADMIN" ? <Link className="button" href="/admin/acts">Manage Acts</Link> : null}
          {role === "LAWYER" || role === "ADMIN" ? <Link className="button secondary" href="/lawyer/workspace">Workspace</Link> : null}
          <Link className="button secondary" href="/search">Search verified information</Link>
          <Link className="button secondary" href="/browse">Browse Acts</Link>
        </div>
      </section>
    </div>
  );
}
