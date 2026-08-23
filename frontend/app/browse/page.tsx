"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { listActs } from "@/lib/api";
import type { LegalAct } from "@/lib/types";
import { StatusBadge } from "@/components/status-badge";

export default function BrowseActsPage() {
  const [acts, setActs] = useState<LegalAct[]>([]);
  const [category, setCategory] = useState("");
  const [year, setYear] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listActs()
      .then(setActs)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load Acts. Login may be required."))
      .finally(() => setLoading(false));
  }, []);

  const filteredActs = useMemo(() => {
    return acts.filter((act) => {
      const categoryMatches = category
        ? (act.category ?? "").toLowerCase().includes(category.toLowerCase())
        : true;
      const yearMatches = year ? String(act.year ?? "") === year.trim() : true;
      return categoryMatches && yearMatches;
    });
  }, [acts, category, year]);

  return (
    <div className="grid">
      <section className="panel">
        <h1>Browse verified Acts</h1>
        <p className="muted">
          Browse Acts that are available for information retrieval. General Users see verified information and reviewed relationships only.
        </p>
        <div className="toolbar">
          <Link className="button" href="/search">Search verified information</Link>
        </div>
      </section>

      <section className="panel">
        <h2>Filters</h2>
        <div className="toolbar">
          <div className="field">
            <label htmlFor="category">Category</label>
            <input id="category" value={category} onChange={(event) => setCategory(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="year">Year</label>
            <input id="year" value={year} onChange={(event) => setYear(event.target.value)} inputMode="numeric" />
          </div>
        </div>
      </section>

      {loading ? <p>Loading verified Acts...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {!loading && !error && !filteredActs.length ? (
        <div className="empty">No verified Acts are available for those filters.</div>
      ) : null}

      <section className="grid">
        {filteredActs.map((act) => (
          <article className="panel result" key={act.id}>
            <div className="toolbar">
              <StatusBadge value={act.processing_status} />
              {act.category ? <StatusBadge value={act.category} /> : null}
            </div>
            <h2>{act.title}</h2>
            <p className="muted">
              {act.act_number ? `Act No. ${act.act_number}` : "Act number unavailable"} {act.year ? `of ${act.year}` : ""}
            </p>
            <p className="muted">Source file: {act.source_file_name}</p>
            <Link className="button secondary" href={`/acts/${act.id}`}>Open Act</Link>
          </article>
        ))}
      </section>
    </div>
  );
}
