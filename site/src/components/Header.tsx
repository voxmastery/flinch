import "./Header.css";

export function Header() {
  return (
    <header className="site-header">
      <div className="wrap header-row">
        <a className="brand" href="#top" aria-label="Flinch, back to top">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>Flinch</span>
        </a>
        <nav aria-label="Main">
          <ul className="nav-list">
            <li>
              <a href="#how">How it works</a>
            </li>
            <li>
              <a href="#demo">Demo</a>
            </li>
            <li>
              <a href="#install">Install</a>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
