import { docsBySection } from "../lib/content";
import DocGrid from "../components/DocGrid";

export default function ProjectsPage() {
  const projects = docsBySection("projects");
  return (
    <section className="content-section content-section-page">
      <h1>Projects</h1>
      <DocGrid docs={projects} showMeta />
    </section>
  );
}
