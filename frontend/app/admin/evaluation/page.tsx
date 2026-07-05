"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  createGoldReference,
  getEvaluationMetricsSummary,
  listEvaluationRuns,
  listGoldReferences,
  runEvaluation
} from "@/lib/api";
import type {
  EvaluationMetricsSummary,
  EvaluationMismatch,
  EvaluationRun,
  GoldReference
} from "@/lib/types";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";

export default function AdminEvaluationPage() {
  const [metrics, setMetrics] = useState<EvaluationMetricsSummary | null>(null);
  const [goldReferences, setGoldReferences] = useState<GoldReference[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [currentRun, setCurrentRun] = useState<EvaluationRun | null>(null);
  const [rawText, setRawText] = useState("section 5");
  const [relationship, setRelationship] = useState("AMENDS");
  const [targetActTitle, setTargetActTitle] = useState("");
  const [targetSection, setTargetSection] = useState("");
  const [actId, setActId] = useState("");
  const [runActId, setRunActId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void loadEvaluationData();
  }, []);

  async function loadEvaluationData() {
    setLoading(true);
    setError("");
    try {
      const [metricsData, goldData, runData] = await Promise.all([
        getEvaluationMetricsSummary(),
        listGoldReferences(),
        listEvaluationRuns()
      ]);
      setMetrics(metricsData);
      setGoldReferences(goldData);
      setRuns(runData);
      setCurrentRun(runData[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load evaluation dashboard.");
    } finally {
      setLoading(false);
    }
  }

  async function addGold(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      await createGoldReference({
        act_id: actId.trim() || null,
        expected_raw_text: rawText,
        expected_relationship_type: relationship,
        expected_target_act_title: targetActTitle.trim() || null,
        expected_target_section_number: targetSection.trim() || null
      });
      setMessage("Gold reference added for evaluation.");
      setRawText("");
      setTargetActTitle("");
      setTargetSection("");
      await loadEvaluationData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add gold reference.");
    }
  }

  async function startEvaluation() {
    setError("");
    setMessage("");
    try {
      const run = await runEvaluation({
        run_name: `MVP evaluation ${new Date().toISOString()}`,
        act_id: runActId.trim() || null
      });
      setCurrentRun(run);
      setMessage("Evaluation run completed.");
      await loadEvaluationData();
      setCurrentRun(run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation failed.");
    }
  }

  return (
    <RoleGuard allowed={["ADMIN"]} path="/admin/evaluation">
      <div className="grid">
        <LegalDisclaimer />
        <section className="panel">
          <h1>Evaluation and demo readiness</h1>
          <p className="muted">
            Metrics are deterministic counts and gold-reference comparisons for academic evaluation only. They are not legal conclusions.
          </p>
          {loading ? <p>Loading evaluation metrics...</p> : null}
          {error ? <p className="error">{error}</p> : null}
          {message ? <p className="muted">{message}</p> : null}
        </section>

        {metrics ? <MetricsPanel metrics={metrics} /> : null}

        <section className="grid two">
          <form className="panel grid" onSubmit={addGold}>
            <h2>Gold reference dataset entry</h2>
            <p className="muted">Add manually verified expected references for precision, recall, and F1.</p>
            <div className="field">
              <label htmlFor="actId">Act ID optional</label>
              <input id="actId" value={actId} onChange={(event) => setActId(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="rawText">Expected raw reference text</label>
              <input id="rawText" value={rawText} onChange={(event) => setRawText(event.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="relationship">Expected relationship type</label>
              <select id="relationship" value={relationship} onChange={(event) => setRelationship(event.target.value)}>
                <option>AMENDS</option>
                <option>REPEALS</option>
                <option>INSERTS</option>
                <option>SUBSTITUTES</option>
                <option>ADDS</option>
                <option>REFERS_TO</option>
                <option>CROSS_REFERENCE</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="targetAct">Expected target Act title</label>
              <input id="targetAct" value={targetActTitle} onChange={(event) => setTargetActTitle(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="targetSection">Expected target section/path</label>
              <input id="targetSection" value={targetSection} onChange={(event) => setTargetSection(event.target.value)} />
            </div>
            <button type="submit">Add gold reference</button>
          </form>

          <section className="panel">
            <h2>Run evaluation</h2>
            <p className="muted">Compare extracted references against the current gold dataset. No accuracy numbers are generated without data.</p>
            <div className="field">
              <label htmlFor="runActId">Limit to Act ID optional</label>
              <input id="runActId" value={runActId} onChange={(event) => setRunActId(event.target.value)} />
            </div>
            <div className="toolbar">
              <button type="button" onClick={startEvaluation}>Run evaluation</button>
              <button type="button" className="secondary" onClick={loadEvaluationData}>Refresh metrics</button>
            </div>
            <p>Gold references: {goldReferences.length}</p>
            <p>Evaluation runs: {runs.length}</p>
          </section>
        </section>

        {currentRun ? <EvaluationRunPanel run={currentRun} /> : <div className="empty">No evaluation run has been selected yet.</div>}
        {runs.length ? <RunHistory runs={runs} onSelect={setCurrentRun} /> : null}
      </div>
    </RoleGuard>
  );
}

function MetricsPanel({ metrics }: { metrics: EvaluationMetricsSummary }) {
  return (
    <div className="grid">
      <section className="grid two">
        <MetricCard title="Documents" values={metrics.document_counts} />
        <MetricCard title="Processing jobs" values={metrics.processing_job_counts} />
        <MetricCard title="Sections" values={metrics.section_counts} />
        <MetricCard title="References and mappings" values={metrics.reference_counts} />
      </section>
      <section className="panel">
        <h2>Latest processing warnings and errors</h2>
        {!metrics.latest_processing_messages.length ? (
          <div className="empty">No processing jobs have produced warnings or errors yet.</div>
        ) : (
          <div className="grid">
            {metrics.latest_processing_messages.map((job) => (
              <article className="result" key={job.job_id}>
                <div className="toolbar">
                  <StatusBadge value={job.status} />
                  <span className="muted">Act ID: {job.act_id}</span>
                  <span className="muted">{job.current_step}</span>
                </div>
                {job.warnings.length ? <p>Warnings: {job.warnings.join("; ")}</p> : null}
                {job.errors.length ? <p className="error">Errors: {job.errors.join("; ")}</p> : null}
                {!job.warnings.length && !job.errors.length ? <p className="muted">No warnings or errors recorded.</p> : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function MetricCard({ title, values }: { title: string; values: Record<string, number> }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div className="toolbar">
        {Object.entries(values).map(([key, value]) => (
          <span key={key}>
            <strong>{formatLabel(key)}:</strong> {value}
          </span>
        ))}
      </div>
    </section>
  );
}

function EvaluationRunPanel({ run }: { run: EvaluationRun }) {
  const falsePositives = run.run_summary_json?.false_positives ?? [];
  const falseNegatives = run.run_summary_json?.false_negatives ?? [];
  return (
    <section className="panel">
      <h2>{run.run_name}</h2>
      <div className="toolbar">
        <span>Precision: {formatPercent(run.precision)}</span>
        <span>Recall: {formatPercent(run.recall)}</span>
        <span>F1-score: {formatPercent(run.f1_score)}</span>
        <span>Gold references: {run.total_gold_references}</span>
        <span>TP/FP/FN: {run.true_positives}/{run.false_positives}/{run.false_negatives}</span>
        <span>Section segmentation accuracy: {run.section_segmentation_accuracy === null ? "Not supplied" : formatPercent(run.section_segmentation_accuracy)}</span>
      </div>
      <MismatchTable title="False positives" rows={falsePositives} empty="No false positives recorded." />
      <MismatchTable title="False negatives" rows={falseNegatives} empty="No false negatives recorded." />
    </section>
  );
}

function MismatchTable({ title, rows, empty }: { title: string; rows: EvaluationMismatch[]; empty: string }) {
  return (
    <section>
      <h3>{title}</h3>
      {!rows.length ? (
        <div className="empty">{empty}</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Raw text</th>
                <th>Relationship</th>
                <th>Target Act</th>
                <th>Target section/path</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.raw_text}-${index}`}>
                  <td>{row.raw_text}</td>
                  <td>{row.relationship_type}</td>
                  <td>{row.target_act_title || "-"}</td>
                  <td>{row.target_section || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function RunHistory({ runs, onSelect }: { runs: EvaluationRun[]; onSelect: (run: EvaluationRun) => void }) {
  return (
    <section className="panel">
      <h2>Evaluation run history</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Precision</th>
              <th>Recall</th>
              <th>F1-score</th>
              <th>Created</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td>{run.run_name}</td>
                <td>{formatPercent(run.precision)}</td>
                <td>{formatPercent(run.recall)}</td>
                <td>{formatPercent(run.f1_score)}</td>
                <td>{new Date(run.created_at).toLocaleString()}</td>
                <td><button type="button" className="secondary" onClick={() => onSelect(run)}>View mismatches</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
