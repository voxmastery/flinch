"""Command-line interface. State-changing commands go through the daemon (single writer)."""

import json
import shlex
import sys
from pathlib import Path
from typing import Any

import httpx
import typer

from flinch.config import DEFAULT_CONFIG_TOML, HOST, PORT
from flinch.jsonfile import read_json
from flinch.scars import SEVERITIES
from flinch.settings_merge import SCARCHECK_MODULE, merge_hooks

app = typer.Typer(no_args_is_help=True, add_completion=False)

BASE_URL = f"http://{HOST}:{PORT}"
GITIGNORE_LINE = ".flinch/"
DOWN_MSG = ("daemon: DOWN. Start it with `flinch serve`. HTTP hooks fail open; only scars "
            "installed with `flinch init --strict` are still enforced.")


def _ensure_gitignore(project: Path) -> None:
    gi = project / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    if GITIGNORE_LINE not in lines:
        gi.write_text("\n".join([*lines, GITIGNORE_LINE]) + "\n")


def _port_in_use(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _start_daemon() -> bool:
    import subprocess

    if _port_in_use(HOST, PORT):
        return True
    from flinch.locate import data_home
    from flinch.relay import _claim

    if _claim(data_home() / "daemon.starting"):  # same start lock as the hooks: one daemon only
        subprocess.Popen([sys.executable, "-m", "flinch.cli", "serve", "--idle-exit", "10800"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    for _ in range(60):  # model load takes a few seconds on a cold start
        try:
            if httpx.get(BASE_URL + "/health", timeout=0.5).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        import time
        time.sleep(0.25)
    return False


def _api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    try:
        r = httpx.request(method, BASE_URL + path, json=body, timeout=10)
    except httpx.HTTPError:
        if not _start_daemon():
            typer.echo(DOWN_MSG, err=True)
            raise typer.Exit(1)
        r = httpx.request(method, BASE_URL + path, json=body, timeout=10)
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith(
            "application/json") else r.text
        typer.echo(f"error: {detail}", err=True)
        raise typer.Exit(1)
    return r.json()


@app.command()
def init(
    project: Path = typer.Option(Path("."), help="Project root."),
    strict: bool = typer.Option(False, help="Also install a fail-closed scar check that works with the daemon down."),
    hooks: bool = typer.Option(True, help="Write project hooks. Use --no-hooks when the Claude Code plugin is installed."),
) -> None:
    """Create .flinch/ (project-local state) and merge hooks into .claude/settings.json."""
    project = project.resolve()
    if not hooks:
        (project / ".flinch").mkdir(exist_ok=True)
        if not (project / ".flinch" / "config.toml").exists():
            (project / ".flinch" / "config.toml").write_text(DEFAULT_CONFIG_TOML)
        _ensure_gitignore(project)
        typer.echo(f"flinch: state dir ready in {project / '.flinch'} (no project hooks)")
        return
    settings_path = project / ".claude" / "settings.json"
    current = {}
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text() or "{}")
        except json.JSONDecodeError as e:
            typer.echo(f"error: {settings_path} is not valid JSON ({e}); not touching it.", err=True)
            raise typer.Exit(1)
    home = project / ".flinch"
    scarcheck = (f"{shlex.quote(sys.executable)} -m {SCARCHECK_MODULE} --home {shlex.quote(str(home))}"
                 if strict else None)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(merge_hooks(current, scarcheck), indent=2) + "\n")
    home.mkdir(exist_ok=True)
    if not (home / "config.toml").exists():
        (home / "config.toml").write_text(DEFAULT_CONFIG_TOML)
    _ensure_gitignore(project)
    typer.echo(f"flinch: hooks installed in {settings_path}" + (" (strict)" if strict else ""))


@app.command()
def serve(
    host: str = HOST,
    port: int = PORT,
    idle_exit: int = typer.Option(0, help="Exit after this many seconds without hooks (0 = never)."),
) -> None:
    """Run the daemon (localhost only). One daemon serves every project."""
    import uvicorn

    from flinch.daemon import create_app

    if host not in ("127.0.0.1", "localhost", "::1"):
        typer.echo("error: flinch binds to localhost only.", err=True)
        raise typer.Exit(1)
    if _port_in_use(host, port):  # check before opening state: a second daemon would wait on the store lock
        typer.echo(f"error: {host}:{port} is already in use (is a flinch daemon already running?).", err=True)
        raise typer.Exit(1)
    uvicorn.run(create_app(idle_exit_s=idle_exit or None), host=host, port=port, log_level="warning")


@app.command()
def status() -> None:
    """Report daemon health."""
    typer.echo(json.dumps(_api("GET", "/health"), indent=2))


@app.command()
def hurt(
    reason: str = typer.Argument(..., help="What damage was done."),
    severity: float = typer.Option(1.0, "--severity", "-s", help=f"One of {SEVERITIES}."),
    action: str = typer.Option(None, "--action", "-a", help="The exact shell command that did the damage."),
) -> None:
    """Record pain for a command (default: the likeliest recent culprit); it becomes a scar."""
    scar = _api("POST", "/api/hurt", {"reason": reason, "severity": severity, "project": str(Path.cwd()),
                                      "action": action})
    typer.echo(f"scarred {scar['pain_id']}: `{scar['normalized']}` ({scar['reason']})")


@app.command()
def scars(project: Path = typer.Option(Path("."), help="Any path inside the project.")) -> None:
    """List scars (reads state directly; works with the daemon down)."""
    from flinch.locate import project_root, state_dir

    raw = read_json(state_dir(project_root(str(project.resolve()))) / "scars.json", {})
    if not raw:
        typer.echo("no scars")
        return
    for fp, s in sorted(raw.items(), key=lambda kv: kv[1]["created_at"], reverse=True):
        typer.echo(f"{s['pain_id']}  {fp[:10]}  sev={s['severity']}  {s['created_at']}  "
                   f"`{s['normalized']}`  {s['reason']}")


@app.command()
def forgive(ident: str = typer.Argument(..., help="pain_id or fingerprint prefix.")) -> None:
    """Remove a scar."""
    scar = _api("POST", "/api/forgive", {"id": ident, "project": str(Path.cwd())})
    typer.echo(f"forgave {scar['pain_id']}: `{scar['normalized']}`")


@app.command()
def reset(
    yes: bool = typer.Option(False, "--yes", help="Confirm: forget all scars, reflexes and memories for this project."),
    project: Path = typer.Option(Path("."), help="Any path inside the project."),
) -> None:
    """Wipe what Flinch learned for a project (keeps config.toml)."""
    from flinch.locate import project_root, state_dir, wipe_state

    if not yes:
        typer.echo("refusing without --yes: this forgets every scar, reflex and memory for the project.", err=True)
        raise typer.Exit(1)
    root = project_root(str(project.resolve()))
    if _port_in_use(HOST, PORT):
        done = _api("POST", "/api/reset", {"project": str(root)})["reset"]
    else:  # no daemon holds the memory store: delete directly
        done = str(state_dir(root))
        wipe_state(Path(done))
    typer.echo(f"flinch: reset {done}")


def _post_hook(route: str, body: dict[str, Any]) -> dict[str, Any] | None:
    """POST a hook body to the daemon: its reply ({} when empty), or None if unreachable."""
    try:
        r = httpx.post(BASE_URL + route, json=body, timeout=10)
    except httpx.HTTPError:
        return None
    return r.json() if r.content.strip() else {}


def _hook(route: str, body: dict[str, Any]) -> dict[str, Any] | None:
    reply = _post_hook(route, body)
    if reply is None and _start_daemon():
        reply = _post_hook(route, body)
    return reply


def _check(command: str, tool_use_id: str) -> tuple[int, str]:
    from flinch.generic import DENY, offline_scar, tool_body, verdict

    reply = _hook("/hook/pre", tool_body("PreToolUse", command, str(Path.cwd()), tool_use_id))
    if reply is None:  # daemon unavailable: scars still hold
        reason = offline_scar(command, str(Path.cwd()))
        return (DENY, reason) if reason else (0, "")
    return verdict(reply)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def check(ctx: typer.Context, tool_use_id: str = typer.Option(None, "--id", help="Pair with a later `ran --id`.")) -> None:
    """Ask the reflex before running a command. Exit 0 = go, 2 = blocked, 3 = ask a human first."""
    from flinch.generic import command_text, new_id

    code, reason = _check(command_text(ctx.args), tool_use_id or new_id())
    if reason:
        typer.echo(reason)
    raise typer.Exit(code)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def ran(ctx: typer.Context, failed: bool = typer.Option(False, "--failed", help="The command failed."),
        tool_use_id: str = typer.Option(None, "--id", help="The id passed to `check --id`.")) -> None:
    """Tell Flinch a command ran (feeds blame, healing and test-regression detection)."""
    from flinch.generic import command_text, new_id, tool_body

    event, route = ("PostToolUseFailure", "/hook/post-failure") if failed else ("PostToolUse", "/hook/post")
    extra = {"error": "", "is_interrupt": False} if failed else {"tool_response": {}}
    _hook(route, tool_body(event, command_text(ctx.args), str(Path.cwd()), tool_use_id or new_id(), **extra))


@app.command()
def report(message: str = typer.Argument(..., help="What the user said, e.g. 'you deleted my database!'")) -> None:
    """Sense a damage report in a user message; if it is one, the likeliest culprit becomes a scar."""
    from flinch.generic import prompt_body

    reply = _hook("/hook/prompt", prompt_body(message, str(Path.cwd()))) or {}
    context = (reply.get("hookSpecificOutput") or {}).get("additionalContext")
    typer.echo(context if context and "recorded pain" in context else "no damage detected")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(ctx: typer.Context, yes: bool = typer.Option(
        False, "--yes", help="A human already confirmed: answer 'ask' with yes. Never overrides a block.")) -> None:
    """Check, (ask if needed), run, and record a command. Exit code is the command's, or 2/3 if stopped."""
    import subprocess

    from flinch.generic import ASK, DENY, command_text, new_id

    command, tool_use_id = command_text(ctx.args), new_id()
    code, reason = _check(command, tool_use_id)
    if code == DENY:
        typer.echo(reason, err=True)
        raise typer.Exit(DENY)
    if code == ASK:
        typer.echo(reason, err=True)
        if not (yes or (sys.stdin.isatty() and typer.confirm("Run it anyway?", default=False))):
            typer.echo("not run: needs a human to confirm", err=True)
            raise typer.Exit(ASK)
    argv = ["bash", "-c", command] if len(ctx.args) == 1 or ctx.args[:1] and ctx.args[0] in ("sh", "bash", "zsh") \
        else ctx.args
    result = subprocess.run(argv)
    failed = result.returncode != 0
    from flinch.generic import tool_body

    event, route = ("PostToolUseFailure", "/hook/post-failure") if failed else ("PostToolUse", "/hook/post")
    extra = {"error": f"Exit code {result.returncode}", "is_interrupt": False} if failed else {"tool_response": {}}
    _hook(route, tool_body(event, command, str(Path.cwd()), tool_use_id, **extra))
    raise typer.Exit(result.returncode)


cursor_app = typer.Typer(no_args_is_help=True, help="Cursor integration.")
app.add_typer(cursor_app, name="cursor")


@cursor_app.command("install")
def cursor_install(project: Path = typer.Option(None, help="Install into <project>/.cursor instead of ~/.cursor.")) -> None:
    """Add Flinch hooks to Cursor (keeps your other hooks; backs up hooks.json)."""
    from flinch.cursor_install import hooks_path, install_hooklib, write_config

    launcher = install_hooklib()
    path = hooks_path(project.resolve() if project else None)
    write_config(path, f"python3 -S {shlex.quote(str(launcher))}")
    typer.echo(f"flinch: Cursor hooks installed in {path}")


@cursor_app.command("uninstall")
def cursor_uninstall(project: Path = typer.Option(None, help="Project to uninstall from (default ~/.cursor).")) -> None:
    """Remove Flinch hooks from Cursor."""
    from flinch.cursor_install import hooks_path, write_config

    path = hooks_path(project.resolve() if project else None)
    if path.exists():
        write_config(path, None)
    typer.echo(f"flinch: Cursor hooks removed from {path}")


if __name__ == "__main__":
    app()
