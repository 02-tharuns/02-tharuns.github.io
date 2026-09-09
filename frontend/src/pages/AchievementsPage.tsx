import { docsBySection } from "../lib/content";
import DocGrid from "../components/DocGrid";
import { LossChart } from "../components/HeroArt";

export default function AchievementsPage() {
  const achievements = docsBySection("achievements");
  return (
    <section className="content-section content-section-page hero-art-host">
      <LossChart className="hero-art hero-art-loss" />
      <h1>Achievements</h1>
      <DocGrid docs={achievements} showMeta />
    </section>
  );
}
