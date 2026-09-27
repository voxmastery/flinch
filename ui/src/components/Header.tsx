import type { ConnStatus, JudgmentStatus } from "../types";

interface HeaderProps {
  conn: ConnStatus;
  judgment: JudgmentStatus;
  loadError: string | null;
  project: string | null;
  loaded: boolean;
}

const CONN_LABEL: Record<ConnStatus, string> = {
  connecting: "connecting…",
  connected: "live",
  reconnecting: "reconnecting…",
  mock: "mock stream",
};

const DANGER_SENSE_LABEL: Record<JudgmentStatus, string> = {
  ok: "on",
  unavailable: "rules only",
  disabled: "off",
};

function ProjectName({ project, loaded }: { project: string | null; loaded: boolean }) {
  if (project) {
    return (
      // Keyed so the switch highlight replays whenever the followed project changes.
      <span key={project} className="project-name mono" title={project}>
        {project}
      </span>
    );
  }
  return <span className="project-name project-none">{loaded ? "waiting for the first agent action" : "…"}</span>;
}

export function Header({ conn, judgment, loadError, project, loaded }: HeaderProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span className="brand-name">flinch</span>
        <span className="brand-sub">reflexes for coding agents</span>
      </div>
      <div className="project" aria-live="polite">
        <span className="project-label">project</span>
        <ProjectName project={project} loaded={loaded} />
      </div>
      <div className="status">
        {loadError && <span className="status-error" title={loadError}>state unavailable</span>}
        <span className={`pill conn-${conn}`}>
          <span className="dot" aria-hidden="true" />
          {CONN_LABEL[conn]}
        </span>
        <span className={`pill judgment-${judgment}`} title="danger sense status">
          <span className="dot" aria-hidden="true" />
          danger sense: {DANGER_SENSE_LABEL[judgment]}
        </span>
      </div>
    </header>
  );
}
