import { useState } from "react";
import { submitContact } from "../lib/api";

export default function ContactForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("sending");
    setError("");
    try {
      await submitContact(name, email, message);
      setStatus("sent");
      setName("");
      setEmail("");
      setMessage("");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (status === "sent") {
    return <p className="contact-sent">Thanks — that's on its way. He usually responds within a day or two.</p>;
  }

  return (
    <form className="contact-form" onSubmit={onSubmit}>
      <div className="form-row">
        <label htmlFor="c-name">Name</label>
        <input id="c-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
      </div>
      <div className="form-row">
        <label htmlFor="c-email">Email</label>
        <input id="c-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={200} />
      </div>
      <div className="form-row">
        <label htmlFor="c-message">Message</label>
        <textarea id="c-message" value={message} onChange={(e) => setMessage(e.target.value)} required maxLength={3000} rows={4} />
      </div>
      {/* Honeypot: hidden from real visitors via CSS, a bot filling every field trips it. */}
      <input type="text" name="honeypot" tabIndex={-1} autoComplete="off" className="honeypot-field" aria-hidden="true" />
      {status === "error" && <p className="form-error">{error}</p>}
      <button type="submit" disabled={status === "sending"}>
        {status === "sending" ? "Sending…" : "Send"}
      </button>
    </form>
  );
}
