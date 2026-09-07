import { API_BASE } from "./config";

export interface SourceChunk {
  id: string;
  heading: string;
  doc: string;
  domain: string;
  section: string;
  text: string;
  score: number;
}

export interface AskResponse {
  ok: boolean;
  code: string | null;
  html: string;
  answer: string | null;
  sources: SourceChunk[];
  trace_id: string | null;
}

export interface Turn {
  role: "user" | "assistant";
  content: string;
}

export async function askQuestion(question: string, history: Turn[]): Promise<AskResponse> {
  const r = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  if (!r.ok) throw new Error(`ask failed: ${r.status}`);
  return r.json();
}

/** Streams tokens via `onToken`, resolves with the authoritative final
 * verdict once the server emits it — the client must always display the
 * verdict's html, discarding whatever was rendered optimistically if the
 * citation gate failed server-side (see ARCHITECTURE.md's streaming
 * contract, unchanged from the old browser-only build). */
export async function askQuestionStream(
  question: string,
  history: Turn[],
  onToken: (soFar: string) => void
): Promise<AskResponse> {
  const r = await fetch(`${API_BASE}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  if (!r.ok || !r.body) throw new Error("stream unavailable");

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  let verdict: AskResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      const eventMatch = /event:\s*(\w+)/.exec(frame);
      const dataMatch = /data:\s*(.+)/.exec(frame);
      if (!eventMatch || !dataMatch) continue;
      let parsed: any;
      try {
        parsed = JSON.parse(dataMatch[1]);
      } catch {
        continue;
      }
      if (eventMatch[1] === "token" && parsed.t) {
        text += parsed.t;
        onToken(text);
      }
      if (eventMatch[1] === "verdict") verdict = parsed as AskResponse;
    }
  }
  if (!verdict) throw new Error("stream ended without a verdict");
  return verdict;
}

export async function submitContact(name: string, email: string, message: string): Promise<{ ok: boolean; detail: string }> {
  const r = await fetch(`${API_BASE}/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, message, honeypot: "" }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `contact failed: ${r.status}`);
  }
  return r.json();
}

// --- "report this answer" (recruiter flags a wrong/unhelpful answer) -------------

export interface ReportPayload {
  traceId: string | null;
  question: string;
  answerText: string;
  reason: string;
  contactEmail?: string;
}

export async function submitReport(payload: ReportPayload): Promise<{ ok: boolean; detail: string }> {
  const r = await fetch(`${API_BASE}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      trace_id: payload.traceId,
      question: payload.question,
      answer_text: payload.answerText,
      reason: payload.reason,
      contact_email: payload.contactEmail || "",
      honeypot: "",
    }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok || body.ok === false) {
    throw new Error(body.detail || `report failed: ${r.status}`);
  }
  return body;
}

// --- observability -----------------------------------------------------------

export interface TraceSpan {
  name: string;
  started_at: number;
  duration_ms: number;
  meta: Record<string, unknown>;
}

export interface Trace {
  id: string;
  started_at: string;
  duration_ms: number;
  question: string;
  verdict: string;
  reason: string | null;
  score: number | null;
  spans: TraceSpan[];
}

export async function fetchTraces(limit = 50): Promise<Trace[]> {
  const r = await fetch(`${API_BASE}/observability/traces?limit=${limit}`);
  if (!r.ok) throw new Error(`fetchTraces failed: ${r.status}`);
  return r.json();
}

export function subscribeToTraceStream(onTrace: (t: Trace) => void): () => void {
  const es = new EventSource(`${API_BASE}/observability/stream`);
  es.addEventListener("trace", (ev) => {
    try {
      onTrace(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore malformed frame */
    }
  });
  return () => es.close();
}

// --- agent events (the separate AI SRE agent project) ----------------------------

export interface AgentEvent {
  id: number;
  received_at: string;
  agent: string;
  kind: string;
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  payload: Record<string, unknown>;
}

export async function fetchAgentEvents(limit = 100): Promise<AgentEvent[]> {
  const r = await fetch(`${API_BASE}/agents/events?limit=${limit}`);
  if (!r.ok) throw new Error(`fetchAgentEvents failed: ${r.status}`);
  return r.json();
}

export function subscribeToAgentEvents(onEvent: (e: AgentEvent) => void): () => void {
  const es = new EventSource(`${API_BASE}/agents/events/stream`);
  es.addEventListener("agent_event", (ev) => {
    try {
      onEvent(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore malformed frame */
    }
  });
  return () => es.close();
}

// --- visitor reports, read side (the Observability dashboard's feed) -----------

export interface VisitorReport {
  id: number;
  received_at: string;
  trace_id: string | null;
  question: string;
  answer_text: string;
  reason: string;
}

export async function fetchReports(limit = 50): Promise<VisitorReport[]> {
  const r = await fetch(`${API_BASE}/report?limit=${limit}`);
  if (!r.ok) throw new Error(`fetchReports failed: ${r.status}`);
  return r.json();
}

export function subscribeToReports(onReport: (r: VisitorReport) => void): () => void {
  const es = new EventSource(`${API_BASE}/report/stream`);
  es.addEventListener("report", (ev) => {
    try {
      onReport(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore malformed frame */
    }
  });
  return () => es.close();
}

// --- evals ----------------------------------------------------------------------

export interface EvalRunSummary {
  id: string;
  started_at: string;
  duration_ms: number;
  suite_counts: Record<string, number>;
  attack_success_rate: number;
  false_refusal_rate: number;
  recall_at_k: number;
  no_answer_accuracy: number;
  citation_correctness: number;
  passed: boolean;
  git_sha: string | null;
}

export interface EvalRunDetail extends EvalRunSummary {
  cases: Array<{ suite: string; q: string; expected: string; got: string; pass: boolean }>;
}

export async function fetchEvalRuns(limit = 50): Promise<EvalRunSummary[]> {
  const r = await fetch(`${API_BASE}/evals/runs?limit=${limit}`);
  if (!r.ok) throw new Error(`fetchEvalRuns failed: ${r.status}`);
  return r.json();
}

export async function fetchEvalRun(id: string): Promise<EvalRunDetail> {
  const r = await fetch(`${API_BASE}/evals/runs/${id}`);
  if (!r.ok) throw new Error(`fetchEvalRun failed: ${r.status}`);
  return r.json();
}
