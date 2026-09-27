import "./Footer.css";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="wrap footer-row">
        <p className="footer-line">It never makes the same mistake twice.</p>
        <p className="footer-meta">
          Flinch: pain receptors for AI agents. Runs locally, offline, with no API keys.
        </p>
        <p className="footer-links">
          <a href="https://github.com/voxmastery/flinch" rel="noopener">Source on GitHub</a> (MIT)
        </p>
        <a className="footer-top" href="#top">
          Back to top
        </a>
      </div>
    </footer>
  );
}
