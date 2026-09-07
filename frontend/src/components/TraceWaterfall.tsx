import type { Trace } from "../lib/api";

const STAGE_COLORS: Record<string, string> = {
  sanitise: "#64748b",
  injection_gate: "#64748b",
  policy_gates: "#64748b",
  tokenise: "#0ea5e9",
  retrieve_bm25: "#0ea5e9",
  retrieve_dense: "#6366f1",
  fuse_rrf: "#8b5cf6",
  rerank: "#a855f7",
  score_confidence: "#0ea5e9",
  subject_analysis: "#64748b",
  fit_question_path: "#64748b",
  scope_gate: "#64748b",
  evidence_gate: "#64748b",
  generate: "#22c55e",
  generate_stream: "#22c55e",
  extractive_fallback: "#f59e0b",
  extractive_no_key: "#f59e0b",
};

export default function TraceWaterfall({ trace }: { trace: Trace }) {
  const total = Math.max(trace.duration_ms, 1);
  return (
    <div className="trace-waterfall">
      <div className="trace-waterfall-head">
        <span className={`verdict-badge verdict-${trace.verdict}`}>{trace.verdict}</span>
        <span className="trace-question">{trace.question}</span>
        <span className="trace-duration">{trace.duration_ms.toFixed(1)} ms</span>
      </div>
      <div className="trace-bars">
        {trace.spans.map((span, i) => {
          const left = (span.started_at / total) * 100;
          const width = Math.max((span.duration_ms / total) * 100, 0.6);
          return (
            <div className="trace-bar-row" key={i}>
              <span className="trace-bar-label">{span.name}</span>
              <div className="trace-bar-track">
                <div
                  className="trace-bar-fill"
                  style={{
                    left: `${left}%`,
                    width: `${width}%`,
                    background: STAGE_COLORS[span.name] || "#94a3b8",
                  }}
                  title={`${span.name}: ${span.duration_ms.toFixed(2)} ms`}
                />
              </div>
              <span className="trace-bar-ms">{span.duration_ms.toFixed(2)} ms</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
