import { docsBySection } from "../lib/content";
import DocGrid from "../components/DocGrid";

export default function EducationPage() {
  const education = docsBySection("education");
  return (
    <section className="content-section content-section-page">
      <h1>Education</h1>
      <DocGrid docs={education} />
    </section>
  );
}
