import { useEffect, useRef, useState } from "react";
import { askQuestionStream, submitReport, type AskResponse, type Turn } from "../lib/api";

interface Message {
  role: "user" | "bot";
  html?: string;
  text?: string;
  refusalCode?: string | null;
  sources?: AskResponse["sources"];
  streaming?: boolean;
  question?: string; // the question this bot message answers — absent for the greeting
  traceId?: string | null;
}

const SUGGESTIONS = [
  "What has he built with sensor data?",
  "How does he evaluate his models?",
  "What has he not worked on?",
  "Which project fits a robotics role?",
];

export default function ChatWidget({ botName }: { botName: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [greeted, setGreeted] = useState(false);
  const history = useRef<Turn[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  function openPanel() {
    setOpen(true);
    if (!greeted) {
      setGreeted(true);
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text: `I'm ${botName}. I answer questions about Tharun using retrieval over his own documents — hybrid BM25 + dense search, reranked, then generated with every claim cited. Ask anything about his projects, skills or education.`,
        },
      ]);
    }
  }

  async function submit(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }]);
    const thinkingIndex = messages.length + 1;
    setMessages((m) => [...m, { role: "bot", text: "", streaming: true }]);

    try {
      const result = await askQuestionStream(text, history.current, (soFar) => {
        setMessages((m) => {
          const copy = [...m];
          copy[thinkingIndex] = { role: "bot", text: soFar, streaming: true };
          return copy;
        });
      });
      const nextHistory: Turn[] = [
        ...history.current,
        { role: "user", content: text },
        { role: "assistant", content: stripTags(result.html) },
      ];
      history.current = nextHistory.slice(-8);
      setMessages((m) => {
        const copy = [...m];
        copy[thinkingIndex] = {
          role: "bot",
          html: result.html,
          refusalCode: result.ok ? null : result.code,
          sources: result.sources,
          question: text,
          traceId: result.trace_id,
        };
        return copy;
      });
    } catch {
      setMessages((m) => {
        const copy = [...m];
        copy[thinkingIndex] = {
          role: "bot",
          html: "<p>The answering service didn't respond. Try again in a moment.</p>",
          refusalCode: "backend_error",
          question: text,
          traceId: null,
        };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`chat-root ${open ? "is-open" : ""}`}>
      <button type="button" className="chat-launcher" onClick={() => (open ? setOpen(false) : openPanel())} aria-expanded={open}>
        <ChappieMark className="chat-launcher-mark" />
        <span>Ask {botName}</span>
      </button>

      {open && (
        <section className="chat-panel" role="dialog" aria-label={`Ask ${botName}`}>
          <header className="chat-head">
            <div className="chat-head-id">
              <ChappieMark className="chat-head-mark" />
              <div>
                <p className="chat-title">{botName}</p>
                <p className="chat-sub">Hybrid retrieval, reranked, cited generation</p>
              </div>
            </div>
            <button type="button" className="chat-close" onClick={() => setOpen(false)} aria-label="Close">
              ×
            </button>
          </header>

          <div className="chat-log" ref={logRef}>
            {messages.map((m, i) => (
              <ChatBubble key={i} message={m} />
            ))}
          </div>

          {messages.length <= 1 && (
            <div className="chat-suggest">
              {SUGGESTIONS.map((q) => (
                <button key={q} type="button" className="chat-chip" onClick={() => submit(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}

          <form
            className="chat-form"
            onSubmit={(e) => {
              e.preventDefault();
              submit(input);
            }}
          >
            <input
              className="chat-input"
              type="text"
              value={input}
              maxLength={400}
              placeholder="Ask about his projects, skills or education…"
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button type="submit" className="chat-send" disabled={busy} aria-label="Send">
              →
            </button>
          </form>
        </section>
      )}
    </div>
  );
}

function ChatBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="chat-msg chat-user">
        <span>{message.text}</span>
      </div>
    );
  }
  const isRefusal = message.refusalCode && message.refusalCode !== "not_published";
  const isDeflection = message.refusalCode === "not_published";
  const answeredSomething = Boolean(message.question) && !message.streaming;
  return (
    <div className={`chat-msg chat-bot ${isRefusal ? "chat-refusal" : ""} ${isDeflection ? "chat-deflection" : ""}`}>
      <span className="chat-av">
        <ChappieMark className="chat-av-mark" />
      </span>
      <div className="chat-body">
        {message.streaming ? (
          <p>
            {message.text}
            <span className="chat-caret" />
          </p>
        ) : message.html ? (
          <div dangerouslySetInnerHTML={{ __html: sanitizeChatHtml(message.html) }} onClick={handleCiteClick} />
        ) : (
          <p>{message.text}</p>
        )}
        {answeredSomething && (
          <ReportControl
            question={message.question!}
            answerText={message.html ? stripTags(message.html) : message.text || ""}
            traceId={message.traceId ?? null}
          />
        )}
      </div>
    </div>
  );
}

function ReportControl({ question, answerText, traceId }: { question: string; answerText: string; traceId: string | null }) {
  const [state, setState] = useState<"idle" | "open" | "sending" | "sent" | "error">("idle");
  const [reason, setReason] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");

  if (state === "sent") {
    return <p className="report-sent">Thanks — flagged for review.</p>;
  }

  if (state === "idle") {
    return (
      <button type="button" className="report-toggle" onClick={() => setState("open")}>
        Not the answer you expected? Report it →
      </button>
    );
  }

  async function send() {
    setState("sending");
    setError("");
    try {
      await submitReport({ traceId, question, answerText, reason, contactEmail: email });
      setState("sent");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <div className="report-form">
      <label htmlFor={`report-reason-${traceId ?? question}`}>What was wrong or missing?</label>
      <textarea
        id={`report-reason-${traceId ?? question}`}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={1000}
        rows={2}
        placeholder="e.g. I asked about Kubernetes specifically and this didn't say yes or no"
      />
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        maxLength={200}
        placeholder="Your email, if you'd like a reply (optional)"
      />
      {state === "error" && <p className="form-error">{error}</p>}
      <div className="report-actions">
        <button type="button" className="report-cancel" onClick={() => setState("idle")} disabled={state === "sending"}>
          Cancel
        </button>
        <button type="button" className="report-submit" onClick={send} disabled={state === "sending"}>
          {state === "sending" ? "Sending…" : "Submit"}
        </button>
      </div>
    </div>
  );
}

function handleCiteClick(e: React.MouseEvent) {
  const target = (e.target as HTMLElement).closest<HTMLElement>(".rag-cite");
  if (!target) return;
  const section = document.getElementById(target.dataset.section || "");
  if (!section) return;
  section.scrollIntoView({ behavior: "smooth", block: "start" });
  section.classList.add("rag-flash");
  setTimeout(() => section.classList.remove("rag-flash"), 1600);
}

// The backend already produces trusted, server-templated HTML (headings,
// citation buttons, source cards) — no user input is ever interpolated
// into it unescaped (see backend/app/guardrails/gates.py's escape_html use
// throughout). This strips anything that isn't in that known-safe set as a
// defense-in-depth belt, not because the source is untrusted.
const ALLOWED_TAGS = new Set(["p", "strong", "em", "a", "button", "blockquote", "div", "span", "sup"]);
function sanitizeChatHtml(html: string): string {
  const template = document.createElement("template");
  template.innerHTML = html;
  const walk = (node: Node) => {
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const el = child as HTMLElement;
        if (!ALLOWED_TAGS.has(el.tagName.toLowerCase())) {
          el.replaceWith(...Array.from(el.childNodes));
          continue;
        }
        for (const attr of Array.from(el.attributes)) {
          if (!["href", "class", "data-cite", "data-section", "type", "title", "aria-hidden", "target", "rel"].includes(attr.name)) {
            el.removeAttribute(attr.name);
          }
        }
        walk(el);
      }
    }
  };
  walk(template.content);
  return template.innerHTML;
}

function stripTags(html: string): string {
  const el = document.createElement("div");
  el.innerHTML = html;
  return (el.textContent || "").trim().slice(0, 2000);
}

function ChappieMark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M7.6 7.2 5.2 1.8M16.4 7.2 18.8 1.8" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
      <circle cx="5.1" cy="1.9" r="1.5" fill="currentColor" />
      <circle cx="18.9" cy="1.9" r="1.5" fill="currentColor" />
      <rect x="3.4" y="6.6" width="17.2" height="14.4" rx="4.6" stroke="currentColor" strokeWidth="1.9" />
      <rect x="6.6" y="10" width="10.8" height="5.4" rx="2.7" fill="currentColor" />
      <circle cx="9.6" cy="12.7" r="1.15" fill="var(--bg, #0b0c10)" />
      <circle cx="14.4" cy="12.7" r="1.15" fill="var(--bg, #0b0c10)" />
      <path d="M9.4 18h5.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
