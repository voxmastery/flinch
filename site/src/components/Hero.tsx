import { Stage } from "./hero/Stage";
import "./Hero.css";

export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <h1 id="hero-title">Pain receptors for AI agents.</h1>
          <p className="hero-lead">
            When an action causes damage or an error, it hurts. Flinch makes sure your agent learns from it and never
            repeats it.
          </p>
          <p className="hero-sub">
            Your coding agent will make a mistake. Flinch makes sure it only makes it once: damaging actions are blocked,
            similar ones ask you first, errors come back with the fix that worked last time, and every new session
            starts with the lessons.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href="#install">
              Install
            </a>
            <a className="btn btn-ghost" href="#demo">
              Watch the demo
            </a>
            <a className="btn btn-ghost" href="https://github.com/voxmastery/flinch" rel="noopener">
              View on GitHub
            </a>
          </div>
          <p className="hero-meta">
            For Claude Code and Cursor. Runs on your machine, offline, with no API keys.
          </p>
        </div>
        <div className="hero-stage">
          <Stage />
        </div>
      </div>
    </section>
  );
}
