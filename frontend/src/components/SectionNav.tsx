import { NavLink } from "react-router-dom";

const SECTIONS = [
  { to: "/about", label: "About" },
  { to: "/projects", label: "Projects" },
  { to: "/education", label: "Education" },
  { to: "/skills", label: "Skills" },
  { to: "/achievements", label: "Achievements" },
  { to: "/contact", label: "Contact" },
];

/** The portfolio's own sub-navigation — each entry is a real route (its own
 * page, its own URL, back/forward and direct linking all work) rather than
 * an in-page anchor jump. Shown on every portfolio section page. */
export default function SectionNav() {
  return (
    <nav className="section-nav" aria-label="Portfolio sections">
      {SECTIONS.map((s) => (
        <NavLink key={s.to} to={s.to} className={({ isActive }) => (isActive ? "active" : "")}>
          {s.label}
        </NavLink>
      ))}
    </nav>
  );
}
