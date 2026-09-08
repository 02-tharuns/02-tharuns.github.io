import type { ContentDoc } from "../lib/content";

/** Renders a list of content docs as cards — the shared building block for
 * every dedicated section page (Projects, Education, Skills, Achievements).
 * Extracted out of the old single-page Portfolio's `Section` helper so each
 * page can reuse the exact same card rendering without duplicating it. */
export default function DocGrid({ docs, showMeta }: { docs: ContentDoc[]; showMeta?: boolean }) {
  if (!docs.length) return <p className="empty-hint">Nothing published here yet.</p>;
  return (
    <div className="doc-grid">
      {docs.map((doc) => (
        <article className="doc-card" id={doc.id} key={doc.id}>
          <header className="doc-card-head">
            <h3>{doc.title}</h3>
            {showMeta && (
              <div className="doc-meta">
                {doc.status && <span className="badge badge-status">{doc.status}</span>}
                {doc.domain &&
                  doc.domain.split(",").map((d) => (
                    <span className="badge" key={d.trim()}>
                      {d.trim()}
                    </span>
                  ))}
                {doc.repo && (
                  <a href={doc.repo} target="_blank" rel="noreferrer" className="badge badge-link">
                    Repo ↗
                  </a>
                )}
              </div>
            )}
          </header>
          {doc.images?.length > 0 && (
            <div className="doc-photos">
              {doc.images.map((src) => (
                <img src={src} alt={doc.title} key={src} loading="lazy" />
              ))}
            </div>
          )}
          {doc.sections.map((s) => (
            <div className="doc-subsection" key={s.heading}>
              <h4>{s.heading}</h4>
              <p>{s.text}</p>
            </div>
          ))}
        </article>
      ))}
    </div>
  );
}
