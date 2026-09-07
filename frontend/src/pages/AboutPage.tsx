import { docsBySection } from "../lib/content";

export default function AboutPage() {
  const about = docsBySection("about");
  return (
    <section className="hero">
      <p className="eyebrow">Applied ML · Robotics · Edge Systems</p>
      <h1>Tharun Subramanya</h1>
      {about.map((doc) => (
        <div key={doc.id}>
          {doc.sections.map((s) => (
            <p className="hero-lede" key={s.heading}>
              {s.text}
            </p>
          ))}
        </div>
      ))}
    </section>
  );
}
