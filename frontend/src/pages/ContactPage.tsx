import ContactForm from "../components/ContactForm";

const METHODS = [
  {
    label: "Email",
    value: "tharunmysuru@gmail.com",
    href: "mailto:tharunmysuru@gmail.com",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3 7 9 6 9-6" />
      </svg>
    ),
  },
  {
    label: "LinkedIn",
    value: "/in/tharun-subramanya-p",
    href: "https://linkedin.com/in/tharun-subramanya-p",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6ZM2 9h4v12H2zM4 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
      </svg>
    ),
  },
  {
    label: "GitHub",
    value: "02-tharuns",
    href: "https://github.com/02-tharuns",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21" />
      </svg>
    ),
  },
];

export default function ContactPage() {
  return (
    <section className="contact-section content-section-page">
      <p className="eyebrow">Contact</p>
      <h1 className="contact-title">
        Open to roles in <span className="grad-text">applied AI, IoT &amp; robotics.</span>
      </h1>
      <p className="hero-lede">Machine learning, industrial IoT, edge AI and robotics. Reach out directly below.</p>

      <div className="contact-methods">
        {METHODS.map((m) => (
          <a className="contact-card" href={m.href} target="_blank" rel="noreferrer" key={m.label}>
            <span className="contact-icon">{m.icon}</span>
            <span className="contact-label">{m.label}</span>
            <span className="contact-value">{m.value}</span>
          </a>
        ))}
      </div>
      <p className="contact-note">Response usually within a day or two.</p>

      <ContactForm />
    </section>
  );
}
