import Link from "next/link";

export default function HomePage() {
  return (
    <div className="grid">
      <section className="panel">
        <h1 className="page-title">Automated Legal Acts Retrieval System</h1>
        <p className="muted">
          Search and browse verified English-language Sri Lankan Legal Act information by Act
          metadata, section text, and reviewed statutory relationships.
        </p>
        <div className="toolbar">
          <Link className="button" href="/search">Start search</Link>
          <Link className="button secondary" href="/browse">Browse Acts</Link>
          <Link className="button secondary" href="/login">Login</Link>
        </div>
      </section>
      <section className="grid two">
        <article className="panel">
          <h2>Verified information retrieval</h2>
          <p>General Users can search and browse reviewed Act and section records without Admin or Lawyer tools.</p>
        </article>
        <article className="panel">
          <h2>Academic prototype boundary</h2>
          <p>This system helps locate legal information. It does not explain legal meaning, recommend action, or provide legal advice.</p>
        </article>
      </section>
    </div>
  );
}
