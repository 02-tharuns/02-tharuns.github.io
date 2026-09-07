import { docsBySection } from "../lib/content";
import ContactForm from "../components/ContactForm";

export default function ContactPage() {
  const contact = docsBySection("contact");
  return (
    <section className="contact-section content-section-page">
      <h1>Contact</h1>
      {contact.map((doc) => (
        <div key={doc.id} className="contact-copy">
          {doc.sections.map((s) => (
            <p key={s.heading}>{s.text}</p>
          ))}
        </div>
      ))}
      <ContactForm />
    </section>
  );
}
