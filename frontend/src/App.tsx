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
import { BOT_NAME } from "./lib/config";

export default function App() {
  const location = useLocation();
  // "Portfolio" covers every section page (About, Projects, Education,
  // Skills, Achievements, Contact) — active whenever we're not on one of
  // the other two top-level tabs, rather than only on an exact path match.
  const portfolioActive = !location.pathname.startsWith("/observability") && !location.pathname.startsWith("/evals");

  return (
    <div className="app-shell">
      <header className="topnav">
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

      <footer className="site-footer">
        <span>Built with a hybrid BM25 + dense + rerank RAG pipeline. Every answer is cited.</span>
      </footer>

      <ChatWidget botName={BOT_NAME} />
    </div>
  );
}
