import type { EvalRunSummary } from "../lib/api";

interface Series {
  key: keyof EvalRunSummary;
  label: string;
  color: string;
  higherIsBetter: boolean;
}

const SERIES: Series[] = [
  { key: "attack_success_rate", label: "Attack success", color: "#ef4444", higherIsBetter: false },
  { key: "false_refusal_rate", label: "False refusal", color: "#f59e0b", higherIsBetter: false },
  { key: "recall_at_k", label: "Recall@3", color: "#0ea5e9", higherIsBetter: true },
  { key: "no_answer_accuracy", label: "No-answer accuracy", color: "#22c55e", higherIsBetter: true },
  { key: "citation_correctness", label: "Citation correctness", color: "#8b5cf6", higherIsBetter: true },
];

const WIDTH = 640;
const HEIGHT = 220;
const PAD = 28;

export default function MetricChart({ runs }: { runs: EvalRunSummary[] }) {
  // Oldest -> newest, left to right.
  const ordered = [...runs].reverse();
  const n = ordered.length;

  function points(key: keyof EvalRunSummary): string {
    if (n < 2) return "";
    return ordered
      .map((run, i) => {
        const x = PAD + (i / (n - 1)) * (WIDTH - PAD * 2);
        const value = Number(run[key]) || 0;
        const y = HEIGHT - PAD - value * (HEIGHT - PAD * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }

  return (
    <div className="metric-chart">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height={HEIGHT} role="img" aria-label="Eval metric history">
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = HEIGHT - PAD - frac * (HEIGHT - PAD * 2);
          return (
            <g key={frac}>
              <line x1={PAD} x2={WIDTH - PAD} y1={y} y2={y} stroke="var(--chart-grid)" strokeWidth={1} />
              <text x={2} y={y + 4} fontSize={10} fill="var(--muted)">
                {Math.round(frac * 100)}%
              </text>
            </g>
          );
        })}
        {SERIES.map((s) => (
          <polyline key={s.key} points={points(s.key)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {n === 1 &&
          SERIES.map((s) => {
            const value = Number(ordered[0][s.key]) || 0;
            const y = HEIGHT - PAD - value * (HEIGHT - PAD * 2);
            return <circle key={s.key} cx={WIDTH / 2} cy={y} r={4} fill={s.color} />;
          })}
      </svg>
      <div className="metric-legend">
        {SERIES.map((s) => (
          <span key={s.key} className="metric-legend-item">
            <span className="metric-swatch" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
      {n === 0 && <p className="empty-hint">No eval runs published yet.</p>}
    </div>
  );
}
