import { useEffect, useRef } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import PortfolioLayout from "./pages/PortfolioLayout";
import AboutPage from "./pages/AboutPage";
import ProjectsPage from "./pages/ProjectsPage";
import EducationPage from "./pages/EducationPage";
import SkillsPage from "./pages/SkillsPage";
import AchievementsPage from "./pages/AchievementsPage";
import ContactPage from "./pages/ContactPage";
import ObservabilityPage from "./pages/ObservabilityPage";
import EvalsPage from "./pages/EvalsPage";
import ChatWidget from "./components/ChatWidget";
import BgScene from "./components/BgScene";
import { BOT_NAME } from "./lib/config";

export default function App() {
  const location = useLocation();
  const topnavRef = useRef<HTMLElement>(null);
  // "Portfolio" covers every section page (About, Projects, Education,
  // Skills, Achievements, Contact) — active whenever we're not on one of
  // the other two top-level tabs, rather than only on an exact path match.
  const portfolioActive = !location.pathname.startsWith("/observability") && !location.pathname.startsWith("/evals");

  // The top nav wraps to two lines on narrow phones (see .topnav's
  // flex-wrap breakpoint), so its rendered height isn't a fixed number —
  // a hardcoded `top` offset for anything docking under it (the section
  // nav) would either leave a gap or get covered. Measuring it directly
  // and publishing it as a CSS var keeps every sticky-under-the-header
  // element correct at any width without hand-tuned breakpoint math.
  useEffect(() => {
    const el = topnavRef.current;
    if (!el) return;
    const setHeight = () => document.documentElement.style.setProperty("--topnav-h", `${el.offsetHeight}px`);
    setHeight();
    const observer = new ResizeObserver(setHeight);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="app-shell">
      <BgScene />
      <div className="bg-grain" aria-hidden="true" />
      <div className="bg-vignette" aria-hidden="true" />

      <header className="topnav" ref={topnavRef}>
        <nav className="topnav-links">
          <NavLink to="/about" className={() => (portfolioActive ? "active" : "")}>
            Portfolio
          </NavLink>
          <NavLink to="/observability" className={({ isActive }) => (isActive ? "active" : "")}>
            Observability
          </NavLink>
          <NavLink to="/evals" className={({ isActive }) => (isActive ? "active" : "")}>
            Evals
          </NavLink>
        </nav>
        <a className="nav-cta" href="/resume.pdf" download>
          Download Resume
        </a>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<PortfolioLayout />}>
            <Route index element={<Navigate to="/about" replace />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="education" element={<EducationPage />} />
            <Route path="skills" element={<SkillsPage />} />
            <Route path="achievements" element={<AchievementsPage />} />
            <Route path="contact" element={<ContactPage />} />
          </Route>
          <Route path="/observability" element={<ObservabilityPage />} />
          <Route path="/evals" element={<EvalsPage />} />
        </Routes>
      </main>

      <ChatWidget botName={BOT_NAME} />
    </div>
  );
}
