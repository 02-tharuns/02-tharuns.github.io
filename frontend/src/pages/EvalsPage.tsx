import { useEffect, useState } from "react";
import { fetchEvalRun, fetchEvalRuns, type EvalRunDetail, type EvalRunSummary } from "../lib/api";
import MetricChart from "../components/MetricChart";

export default function EvalsPage() {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "fail">("all");

  useEffect(() => {
    fetchEvalRuns(100)
      .then(setRuns)
      .catch((err) => setError(err.message));
  }, []);

  async function openRun(id: string) {
    try {
      setDetail(await fetchEvalRun(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const latest = runs[0];
  const failedCases = detail?.cases.filter((c) => !c.pass) ?? [];
  const visibleCases = detail ? (filter === "fail" ? failedCases : detail.cases) : [];

  return (
    <div className="evals-page">
      <div className="obs-header">
        <h1>Evals</h1>
        <p>
          Every push runs the 97-case suite (golden / adjacent / red-team / deflection) against the live API and publishes
          the result here — <code>evals/run_evals_api.py</code>.
        </p>
        {error && <p className="form-error">Could not reach the backend: {error}</p>}
      </div>

      {latest && (
        <div className="metric-cards">
          <MetricCard label="Attack success" value={latest.attack_success_rate} threshold={0.05} lowerIsBetter />
          <MetricCard label="False refusal" value={latest.false_refusal_rate} threshold={0.1} lowerIsBetter />
          <MetricCard label="Recall@3" value={latest.recall_at_k} />
          <MetricCard label="No-answer accuracy" value={latest.no_answer_accuracy} />
          <MetricCard label="Citation correctness" value={latest.citation_correctness} />
        </div>
      )}

      <section className="chart-section">
        <h2>History</h2>
        <MetricChart runs={runs} />
      </section>

      <div className="evals-grid">
        <section className="obs-col">
          <h2>Runs ({runs.length})</h2>
          <ul className="run-list">
            {runs.map((r) => (
              <li key={r.id}>
                <button className={`run-list-item ${detail?.id === r.id ? "is-selected" : ""}`} onClick={() => openRun(r.id)}>
                  <span className={`pass-dot ${r.passed ? "pass" : "fail"}`} />
                  <span className="run-list-id">{r.id}</span>
                  <span className="run-list-date">{new Date(r.started_at).toLocaleString()}</span>
                  {r.git_sha && <span className="run-list-sha">{r.git_sha}</span>}
                </button>
              </li>
            ))}
            {!runs.length && <li className="empty-hint">No runs published yet.</li>}
          </ul>
        </section>

        <section className="obs-col obs-detail">
          <div className="run-detail-head">
            <h2>Run detail</h2>
            {detail && (
              <div className="run-filter">
                <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>
                  All ({detail.cases.length})
                </button>
                <button className={filter === "fail" ? "active" : ""} onClick={() => setFilter("fail")}>
                  Failed ({failedCases.length})
                </button>
              </div>
            )}
          </div>
          {detail ? (
            <ul className="case-list">
              {visibleCases.map((c, i) => (
                <li key={i} className={`case-row ${c.pass ? "pass" : "fail"}`}>
                  <span className="case-suite">{c.suite}</span>
                  <span className="case-q">{c.q || "(empty)"}</span>
                  <span className="case-got">{c.got}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-hint">Select a run.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  threshold,
  lowerIsBetter,
}: {
  label: string;
  value: number;
  threshold?: number;
  lowerIsBetter?: boolean;
}) {
  const ok = threshold === undefined ? value >= 0.9 : lowerIsBetter ? value <= threshold : value >= threshold;
  return (
    <div className={`metric-card ${ok ? "ok" : "warn"}`}>
      <span className="metric-card-label">{label}</span>
      <span className="metric-card-value">{(value * 100).toFixed(1)}%</span>
      {threshold !== undefined && <span className="metric-card-threshold">threshold {(threshold * 100).toFixed(0)}%</span>}
    </div>
  );
}
