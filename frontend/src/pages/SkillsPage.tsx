import { docsBySection } from "../lib/content";
import DocGrid from "../components/DocGrid";

export default function SkillsPage() {
  const skills = docsBySection("skills");
  return (
    <section className="content-section content-section-page">
      <h1>Skills</h1>
      <DocGrid docs={skills} />
    </section>
  );
}
