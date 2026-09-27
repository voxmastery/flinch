import { Stage } from "./hero/Stage";
import "./Hero.css";

export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <h1 id="hero-title">Pain receptors for AI agents.</h1>
          <p className="hero-lead">
            When an action causes damage, it hurts. Flinch makes sure your agent never does it again.
          </p>
          <p className="hero-sub">
            Your coding agent will make a mistake. Flinch makes sure it only makes it once: the same action is blocked,
            similar ones are blocked or ask you first, and new sessions start with the lesson.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href="#install">
              Install
            </a>
            <a className="btn btn-ghost" href="#demo">
              Watch the demo
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
