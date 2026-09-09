import { useEffect, useMemo, useState } from "react";
import {
  fetchAgentEvents, fetchReports, fetchTraces, subscribeToAgentEvents, subscribeToReports, subscribeToTraceStream,
  type AgentEvent, type Trace, type VisitorReport,
} from "../lib/api";
import TraceWaterfall from "../components/TraceWaterfall";

const REFUSAL_CODES = new Set(["injection", "off_topic", "out_of_bounds", "route", "malformed", "ungrounded"]);

interface ChatHealth {
  total: number;
  answered: number;
  deflected: number;
  refused: number;
  avgMs: number;
  p95Ms: number;
  errorRate: number; // ungrounded + malformed-from-backend-fault-like codes, as a fraction of total
  totalTokens: number;
  totalCostUsd: number;
  pricedGenerations: number; // how many of `total` had a cost we could compute, for the "n/a" case
}

// Token Cost Tracking reads straight off the trace it already has — the
// "generate"/"generate_stream" span's meta carries prompt_tokens,
// completion_tokens and cost_usd once backend/app/ask/routes.py records
// them, so no new endpoint or table is needed on the frontend either.
function generationUsage(t: Trace): { tokens: number; costUsd: number | null } {
  const span = t.spans.find((s) => s.name === "generate" || s.name === "generate_stream");
  const meta = span?.meta ?? {};
  const prompt = typeof meta.prompt_tokens === "number" ? meta.prompt_tokens : 0;
  const completion = typeof meta.completion_tokens === "number" ? meta.completion_tokens : 0;
  const costUsd = typeof meta.cost_usd === "number" ? meta.cost_usd : null;
  return { tokens: prompt + completion, costUsd };
}

function computeHealth(traces: Trace[]): ChatHealth {
  const total = traces.length;
  if (!total) {
    return {
      total: 0, answered: 0, deflected: 0, refused: 0, avgMs: 0, p95Ms: 0, errorRate: 0,
      totalTokens: 0, totalCostUsd: 0, pricedGenerations: 0,
    };
  }
  const answered = traces.filter((t) => t.verdict === "allow").length;
  const deflected = traces.filter((t) => t.verdict === "not_published").length;
  const refused = traces.filter((t) => REFUSAL_CODES.has(t.verdict)).length;
  const errors = traces.filter((t) => t.verdict === "ungrounded").length;
  const durations = traces.map((t) => t.duration_ms).sort((a, b) => a - b);
  const avgMs = durations.reduce((a, b) => a + b, 0) / total;
  const p95Ms = durations[Math.min(durations.length - 1, Math.floor(durations.length * 0.95))];

  let totalTokens = 0;
  let totalCostUsd = 0;
  let pricedGenerations = 0;
  for (const t of traces) {
    const { tokens, costUsd } = generationUsage(t);
    totalTokens += tokens;
    if (costUsd !== null) {
      totalCostUsd += costUsd;
      pricedGenerations += 1;
    }
  }

  return { total, answered, deflected, refused, avgMs, p95Ms, errorRate: errors / total, totalTokens, totalCostUsd, pricedGenerations };
}

export default function ObservabilityPage() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [reports, setReports] = useState<VisitorReport[]>([]);
  const [selected, setSelected] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const health = useMemo(() => computeHealth(traces), [traces]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchTraces(50), fetchAgentEvents(100), fetchReports(50)])
      .then(([t, e, rep]) => {
        if (cancelled) return;
        setTraces(t);
        setEvents(e);
        setReports(rep);
        setSelected(t[0] || null);
      })
      .catch((err) => setError(err.message));

    const unsubTraces = subscribeToTraceStream((t) => {
      setTraces((prev) => [t, ...prev].slice(0, 100));
    });
    const unsubEvents = subscribeToAgentEvents((e) => {
      setEvents((prev) => [e, ...prev].slice(0, 200));
    });
    const unsubReports = subscribeToReports((r) => {
      setReports((prev) => [r, ...prev].slice(0, 200));
    });
    return () => {
      cancelled = true;
      unsubTraces();
      unsubEvents();
      unsubReports();
    };
  }, []);

  return (
    <div className="observability-page">
      <div className="obs-header">
        <h1>Observability</h1>
        <p>
          Every <code>/ask</code> call traced stage by stage — gates, retrieval, fusion, reranking, generation — plus a live
          feed from the separate AI SRE agent watching this service in production.
        </p>
        {error && <p className="form-error">Could not reach the backend: {error}</p>}
      </div>

      <div className="metric-cards">
        <HealthCard label="Questions (window)" value={String(health.total)} />
        <HealthCard
          label="Answered"
          value={health.total ? `${((health.answered / health.total) * 100).toFixed(0)}%` : "—"}
          ok={!health.total || health.answered / health.total >= 0.5}
        />
        <HealthCard label="Deflected" value={health.total ? `${((health.deflected / health.total) * 100).toFixed(0)}%` : "—"} />
        <HealthCard
          label="Refused"
          value={health.total ? `${((health.refused / health.total) * 100).toFixed(0)}%` : "—"}
          ok={!health.total || health.refused / health.total <= 0.4}
        />
        <HealthCard label="Avg response time" value={health.total ? `${health.avgMs.toFixed(0)} ms` : "—"} />
        <HealthCard
          label="Slowest response time"
          value={health.total ? `${health.p95Ms.toFixed(0)} ms` : "—"}
          hint="95th percentile — 19 out of 20 questions answer faster than this"
        />
        <HealthCard label="Ungrounded rate" value={health.total ? `${(health.errorRate * 100).toFixed(1)}%` : "—"} ok={health.errorRate <= 0.02} />
        <HealthCard label="Visitor reports" value={String(reports.length)} ok={reports.length === 0} />
        <HealthCard label="Tokens (window)" value={health.pricedGenerations || health.totalTokens ? health.totalTokens.toLocaleString() : "—"} />
        <HealthCard
          label="Est. cost (window)"
          value={health.pricedGenerations ? `$${health.totalCostUsd.toFixed(4)}` : "n/a"}
        />
      </div>

      <section className="obs-reports">
        <h2>Visitor reports ({reports.length})</h2>
        <p className="obs-reports-sub">
          Anyone can flag an answer as wrong or unhelpful from the chat widget — that's a human overriding the
          bot's own confidence, which the automated eval suite can't catch on its own. Each one also emails Tharun.
        </p>
        <ul className="report-list">
          {reports.map((r) => (
            <li key={r.id} className="report-item">
              <p className="report-item-q">"{r.question}"</p>
              {r.reason && <p className="report-item-reason">{r.reason}</p>}
              <time className="agent-event-time">{new Date(r.received_at).toLocaleString()}</time>
            </li>
          ))}
          {!reports.length && <li className="empty-hint">No reports yet — that's the goal.</li>}
        </ul>
      </section>

      <div className="obs-grid">
        <section className="obs-col">
          <h2>Recent traces ({traces.length})</h2>
          <ul className="trace-list">
            {traces.map((t) => (
              <li key={t.id}>
                <button className={`trace-list-item ${selected?.id === t.id ? "is-selected" : ""}`} onClick={() => setSelected(t)}>
                  <span className={`verdict-dot verdict-${t.verdict}`} />
                  <span className="trace-list-q">{t.question || "(empty)"}</span>
                  <span className="trace-list-ms">{t.duration_ms.toFixed(0)}ms</span>
                </button>
              </li>
            ))}
            {!traces.length && <li className="empty-hint">No traces yet — ask Chappie a question.</li>}
          </ul>
        </section>

        <section className="obs-col obs-detail">
          <h2>Trace detail</h2>
          {selected ? <TraceWaterfall trace={selected} /> : <p className="empty-hint">Select a trace.</p>}
        </section>

        <section className="obs-col">
          <h2>Agent events ({events.length})</h2>
          <ul className="agent-event-list">
            {events.map((e) => (
              <li key={e.id} className={`agent-event severity-${e.severity}`}>
                <div className="agent-event-head">
                  <span className="agent-event-agent">{e.agent}</span>
                  <span className="agent-event-kind">{e.kind}</span>
                  <span className={`severity-badge severity-${e.severity}`}>{e.severity}</span>
                </div>
                <p className="agent-event-message">{e.message}</p>
                <time className="agent-event-time">{new Date(e.received_at).toLocaleString()}</time>
              </li>
            ))}
            {!events.length && (
              <li className="empty-hint">
                Nothing yet — the AI SRE agent posts here via <code>POST /agents/events</code>.
              </li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}

function HealthCard({ label, value, ok, hint }: { label: string; value: string; ok?: boolean; hint?: string }) {
  return (
    <div className={`metric-card ${ok === false ? "warn" : "ok"}`} title={hint}>
      <span className="metric-card-label">{label}</span>
      <span className="metric-card-value">{value}</span>
      {hint && <span className="metric-card-threshold">{hint}</span>}
    </div>
  );
}
