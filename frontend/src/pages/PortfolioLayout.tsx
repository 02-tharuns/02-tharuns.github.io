import { Outlet } from "react-router-dom";
import SectionNav from "../components/SectionNav";

/** Shell for the six dedicated portfolio pages (About, Projects, Education,
 * Skills, Achievements, Contact) — renders the section sub-nav once and
 * hands the rest to whichever page route matched. */
export default function PortfolioLayout() {
  return (
    <div className="portfolio">
      <SectionNav />
      <div className="portfolio-content">
        <Outlet />
      </div>
    </div>
  );
}
