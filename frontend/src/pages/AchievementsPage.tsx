import { docsBySection } from "../lib/content";
import DocGrid from "../components/DocGrid";

export default function AchievementsPage() {
  const achievements = docsBySection("achievements");
  return (
    <section className="content-section content-section-page">
      <h1>Achievements</h1>
      <DocGrid docs={achievements} />
    </section>
  );
}
