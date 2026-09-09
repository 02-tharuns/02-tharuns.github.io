import { docsBySection } from "../lib/content";
import { RobotArmCar } from "../components/HeroArt";

export default function AboutPage() {
  const about = docsBySection("about");
  return (
    <section className="hero hero-art-host">
      <RobotArmCar className="hero-art hero-art-robot-about" />
      <img className="hero-photo" src="/img/profile/tharun.webp" alt="Tharun Subramanya" />
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
