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
          Every push runs the full suite (golden / adjacent / red-team / deflection / role / retention / completeness)
          against the live API and publishes the result here — <code>evals/run_evals_api.py</code>.
        </p>
        {error && <p className="form-error">Could not reach the backend: {error}</p>}
      </div>

      {latest && (
        <div className="metric-cards">
          {/* Safety & Guardrail Evals — displayed inverted (1 - rate) so the
              card reads as "how resistant/how well-bounded", matching the
              goodness framing of the name; the raw published number is still
              the attack/refusal rate underneath. */}
          <MetricCard
            label="Jailbreak Resistance"
            value={1 - latest.attack_success_rate}
            threshold={0.95}
            hint="resists prompt injection & attempts to break persona"
          />
          <MetricCard
            label="Domain Boundary Awareness"
            value={1 - latest.false_refusal_rate}
            threshold={0.9}
            hint="declines topics outside his real experience"
          />
          {/* Accuracy & Grounding Evals */}
          <MetricCard
            label="Context Precision & Recall"
            value={latest.recall_at_k}
            hint="retrieves the correct supporting document"
          />
          <MetricCard label="Answer Relevancy" value={latest.answer_relevancy} hint="cosine similarity, question ↔ answer" />
          {/* Conversational & Behavioral Evals */}
          <MetricCard
            label="Role Adherence"
            value={latest.role_adherence}
            hint="stays on-persona, declines off-topic requests"
          />
          <MetricCard
            label="Knowledge Retention"
            value={latest.knowledge_retention}
            hint="resolves follow-up questions from earlier turns"
          />
          <MetricCard
            label="Conversation Completeness"
            value={latest.conversation_completeness}
            hint="answers every part of a multi-part question"
          />
          {/* Retained from the original build, outside the 8-category list above */}
          <MetricCard
            label="No-answer accuracy"
            value={latest.no_answer_accuracy}
            hint="correctly says 'not published' when info is absent"
          />
          <MetricCard
            label="Citation correctness"
            value={latest.citation_correctness}
            hint="cited sources actually support the answer"
          />
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
  hint,
}: {
  label: string;
  value: number | null | undefined;
  threshold?: number;
  lowerIsBetter?: boolean;
  hint?: string;
}) {
  if (value === null || value === undefined) {
    return (
      <div className="metric-card">
        <span className="metric-card-label">{label}</span>
        <span className="metric-card-value">n/a</span>
        {hint && <span className="metric-card-threshold">{hint}</span>}
      </div>
    );
  }
  const ok = threshold === undefined ? value >= 0.9 : lowerIsBetter ? value <= threshold : value >= threshold;
  return (
    <div className={`metric-card ${ok ? "ok" : "warn"}`} title={hint}>
      <span className="metric-card-label">{label}</span>
      <span className="metric-card-value">{(value * 100).toFixed(1)}%</span>
      {hint && <span className="metric-card-threshold">{hint}</span>}
      {threshold !== undefined && (
        <span className="metric-card-threshold">threshold {(threshold * 100).toFixed(0)}%</span>
      )}
    </div>
  );
}
