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
import { RoleGuard } from "@/components/role-guard";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";

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
      <div className="flex flex-col gap-5">
        <section>
          <h1 className="font-serif text-[30px] font-semibold tracking-[-0.45px] text-[#0b1626]">Evaluation</h1>
          <p className="mt-2 max-w-2xl text-[14.5px] leading-[23px] text-muted-foreground">
            Measure extraction and retrieval quality against a manually verified gold sample. Recall is the primary metric; precision and F1 support diagnosis but are not legal conclusions.
          </p>
          {loading ? <p className="mt-3 text-sm text-muted-foreground">Loading evaluation metrics...</p> : null}
          {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
          {message ? <p className="mt-3 text-sm text-muted-foreground">{message}</p> : null}
        </section>

        {currentRun ? <LatestRunSummary run={currentRun} /> : null}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex flex-col gap-4">
            {currentRun ? <ConfusionCard run={currentRun} /> : null}
            {runs.length ? <RunHistory runs={runs} currentId={currentRun?.id} onSelect={setCurrentRun} /> : null}
            {currentRun ? <EvaluationRunPanel run={currentRun} /> : (
              <Card className="rounded-lg">
                <CardContent className="p-4 text-sm text-muted-foreground">
                  No evaluation run has been selected yet.
                </CardContent>
              </Card>
            )}
            {metrics ? <CorpusMetrics metrics={metrics} /> : null}
          </div>

          <div className="flex flex-col gap-4">
            <Card className="rounded-lg">
              <CardContent className="space-y-4 p-5">
                <div>
                  <h2 className="font-serif text-lg font-semibold">Gold sample management</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {goldReferences.length} gold references · {runs.length} evaluation runs
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Act scope (optional ID)</Label>
                  <Input
                    value={runActId}
                    onChange={(event) => setRunActId(event.target.value)}
                    placeholder="Limit run to Act ID"
                    className="h-9 bg-[#fffdf8]"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="button" onClick={() => void startEvaluation()} className="flex-1">
                    ▶ Run evaluation
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void loadEvaluationData()}>
                    Refresh
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-lg">
              <CardContent className="space-y-4 p-5">
                <h2 className="font-serif text-lg font-semibold">Gold reference dataset entry</h2>
                <p className="text-sm text-muted-foreground">
                  Add manually verified expected references for precision, recall, and F1.
                </p>
                <form className="space-y-3" onSubmit={addGold}>
                  <Field label="Act ID optional">
                    <Input value={actId} onChange={(event) => setActId(event.target.value)} className="h-9 bg-[#fffdf8]" />
                  </Field>
                  <Field label="Expected raw reference text">
                    <Input
                      value={rawText}
                      onChange={(event) => setRawText(event.target.value)}
                      required
                      className="h-9 bg-[#fffdf8]"
                    />
                  </Field>
                  <Field label="Expected relationship type">
                    <Select value={relationship} onValueChange={(value) => setRelationship(value ?? "AMENDS")}>
                      <SelectTrigger className="h-9 w-full bg-[#fffdf8]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {["AMENDS", "REPEALS", "INSERTS", "SUBSTITUTES", "ADDS", "REFERS_TO", "CROSS_REFERENCE"].map(
                          (type) => (
                            <SelectItem key={type} value={type}>
                              {type}
                            </SelectItem>
                          )
                        )}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="Expected target Act title">
                    <Input
                      value={targetActTitle}
                      onChange={(event) => setTargetActTitle(event.target.value)}
                      className="h-9 bg-[#fffdf8]"
                    />
                  </Field>
                  <Field label="Expected target section/path">
                    <Input
                      value={targetSection}
                      onChange={(event) => setTargetSection(event.target.value)}
                      className="h-9 bg-[#fffdf8]"
                    />
                  </Field>
                  <Button type="submit" className="w-full">
                    Add gold reference
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </RoleGuard>
  );
}

function Field({ label, children }: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-semibold">{label}</Label>
      {children}
    </div>
  );
}

function LatestRunSummary({ run }: Readonly<{ run: EvaluationRun }>) {
  const values = [
    ["Precision", formatScore(run.precision)],
    ["Recall", formatScore(run.recall)],
    ["F1 score", formatScore(run.f1_score)],
    [
      "Segmentation acc.",
      run.section_segmentation_accuracy === null
        ? "—"
        : formatScore(run.section_segmentation_accuracy)
    ],
    ["Gold references", String(run.total_gold_references)]
  ];
  return (
    <section className="space-y-2">
      <p className="text-[11px] font-semibold tracking-[0.12em] text-[#92681f] uppercase">
        Latest run — {run.run_name}
      </p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {values.map(([label, value]) => (
          <Card key={label} className="rounded-lg border-border bg-card shadow-sm">
            <CardContent className="px-4 py-4">
              <p className="font-serif text-2xl font-semibold text-[#0b1626]">{value}</p>
              <p className="mt-1 text-[10px] font-semibold tracking-[0.08em] text-muted-foreground uppercase">
                {label}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}

function ConfusionCard({ run }: Readonly<{ run: EvaluationRun }>) {
  const total = Math.max(1, run.true_positives + run.false_positives + run.false_negatives);
  const rows = [
    { label: "True positives", value: run.true_positives, color: "bg-[#b8955a]" },
    { label: "False positives", value: run.false_positives, color: "bg-[#8c2433]" },
    { label: "False negatives", value: run.false_negatives, color: "bg-[#92681f]" }
  ];
  return (
    <Card className="rounded-lg">
      <CardContent className="space-y-4 p-5">
        <h2 className="font-serif text-lg font-semibold">Confusion breakdown</h2>
        {rows.map((row) => (
          <div key={row.label} className="space-y-1.5">
            <div className="flex justify-between text-sm">
              <span>{row.label}</span>
              <strong>{row.value}</strong>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${row.color}`}
                style={{ width: `${Math.max(4, (row.value / total) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function CorpusMetrics({ metrics }: Readonly<{ metrics: EvaluationMetricsSummary }>) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <MetricsPanel title="Documents" values={metrics.document_counts} />
      <MetricsPanel title="Processing jobs" values={metrics.processing_job_counts} />
      <MetricsPanel title="Sections" values={metrics.section_counts} />
      <MetricsPanel title="References and mappings" values={metrics.reference_counts} />
      <Card className="rounded-lg sm:col-span-2">
        <CardContent className="space-y-3 p-5">
          <h2 className="font-serif text-lg font-semibold">Latest processing warnings and errors</h2>
          {!metrics.latest_processing_messages.length ? (
            <p className="text-sm text-muted-foreground">
              No processing jobs have produced warnings or errors yet.
            </p>
          ) : (
            metrics.latest_processing_messages.map((job) => (
              <div key={job.job_id} className="rounded-md border border-border bg-[#fffdf8] px-3 py-2 text-sm">
                <div className="flex flex-wrap gap-2">
                  <StatusBadge value={job.status} />
                  <span className="text-muted-foreground">Act ID: {job.act_id}</span>
                  <span className="text-muted-foreground">{job.current_step}</span>
                </div>
                {job.warnings.length ? <p className="mt-1">Warnings: {job.warnings.join("; ")}</p> : null}
                {job.errors.length ? (
                  <p className="mt-1 text-destructive">Errors: {job.errors.join("; ")}</p>
                ) : null}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MetricsPanel({ title, values }: Readonly<{ title: string; values: Record<string, number> }>) {
  return (
    <Card className="rounded-lg">
      <CardContent className="space-y-2 p-4">
        <h2 className="font-serif text-base font-semibold">{title}</h2>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
          {Object.entries(values).map(([key, value]) => (
            <span key={key}>
              <strong>{formatLabel(key)}:</strong> {value}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function EvaluationRunPanel({ run }: Readonly<{ run: EvaluationRun }>) {
  const falsePositives = run.run_summary_json?.false_positives ?? [];
  const falseNegatives = run.run_summary_json?.false_negatives ?? [];
  return (
    <Card className="rounded-lg">
      <CardContent className="space-y-4 p-5">
        <h2 className="font-serif text-lg font-semibold">{run.run_name}</h2>
        <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
          <span>
            <strong className="text-foreground">Recall:</strong> {formatPercent(run.recall)}
          </span>
          <span>Precision: {formatPercent(run.precision)}</span>
          <span>F1: {formatPercent(run.f1_score)}</span>
          <span>
            TP/FP/FN: {run.true_positives}/{run.false_positives}/{run.false_negatives}
          </span>
        </div>
        <MismatchTable title="False positives" rows={falsePositives} empty="No false positives recorded." />
        <MismatchTable title="False negatives" rows={falseNegatives} empty="No false negatives recorded." />
      </CardContent>
    </Card>
  );
}

function MismatchTable({
  title,
  rows,
  empty
}: Readonly<{ title: string; rows: EvaluationMismatch[]; empty: string }>) {
  return (
    <section>
      <h3 className="text-sm font-semibold">{title}</h3>
      {!rows.length ? (
        <p className="mt-2 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="table-wrap mt-2">
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

function RunHistory({
  runs,
  currentId,
  onSelect
}: Readonly<{
  runs: EvaluationRun[];
  currentId?: string;
  onSelect: (run: EvaluationRun) => void;
}>) {
  return (
    <Card className="rounded-lg">
      <CardContent className="space-y-3 p-5">
        <h2 className="font-serif text-lg font-semibold">Run history</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>P</th>
                <th>R</th>
                <th>F1</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className={run.id === currentId ? "font-semibold" : undefined}>
                  <td>
                    <button type="button" className="text-left hover:underline" onClick={() => onSelect(run)}>
                      {run.run_name}
                    </button>
                  </td>
                  <td>{formatScore(run.precision)}</td>
                  <td>{formatScore(run.recall)}</td>
                  <td>{formatScore(run.f1_score)}</td>
                  <td>{new Date(run.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatScore(value: number) {
  return value.toFixed(2);
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
