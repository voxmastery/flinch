# Flinch

Pain receptors for AI agents. When an action causes damage, it hurts, and Flinch makes sure your agent never does it again:

- the **exact same action** is blocked from then on,
- **similar actions** are blocked or need your confirmation,
- **risky actions it has never seen** (force pushes, `DROP TABLE`, `terraform destroy`, and unfamiliar tools that look like them) need your confirmation, judged by a small built-in model, fully offline,
- new sessions start with a short, factual note about what went wrong before.

It plugs into [Claude Code](https://code.claude.com) (terminal, VS Code, JetBrains) and [Cursor](https://cursor.com) (the Agent in the editor and `cursor-agent`) through their hook systems. Both tools share one daemon, so a mistake learned in one is blocked in the other.

## Install

**Site and 70-second demo:** https://flinch-site-khaki.vercel.app

### Claude Code plugin (terminal, VS Code, JetBrains)

```bash
claude plugin marketplace add voxmastery/flinch
claude plugin install flinch@flinch
```

That's it. The first session sets Flinch up in the background (a private virtualenv in the plugin's data folder, about a minute; needs Python 3.11+ and ideally [`uv`](https://docs.astral.sh/uv/)). Nothing is written into your repositories: per-project state lives in `~/.local/share/flinch/projects/`.

### The `flinch` command (for Cursor, any agent, and the CLI)

```bash
uv tool install git+https://github.com/voxmastery/flinch     # or: uv tool install flinch-agent (PyPI)
```

### Cursor

```bash
flinch cursor install            # adds hooks to ~/.cursor/hooks.json (keeps yours, backs up the file)
flinch cursor install --project path/to/repo   # or only for one project
flinch cursor uninstall
```

In Cursor, exact and similar risky actions are **denied** in every mode (shell commands, file deletes and writes, MCP tools). "Needs confirmation" shows Cursor's approval prompt in the editor, but **auto-run / yolo mode (`--force`) skips it**. File writes, deletes and MCP calls can't prompt, so for those a confirmation becomes a deny. Reporting damage in chat depends on Cursor's prompt hook, which the headless `cursor-agent -p` doesn't fire. There, use `flinch hurt`.

### Any other agent or script

Anything that can run a shell command can use the same receptors:

```bash
flinch run -- rm -rf build/          # check, ask a human if needed, run, record
flinch run --yes -- rm -rf build/    # a human already confirmed (never overrides a block)
flinch check -- git push --force     # exit 0 = go, 2 = blocked, 3 = ask a human first
flinch ran --failed -- make deploy   # tell Flinch what ran (feeds blame and regression checks)
flinch report "you deleted my database!"   # sense a damage report in a user's message
```

Set `FLINCH_SESSION` to group one agent's commands; otherwise the parent process is the session.

### Single project, no plugin

Add hooks to one project only:

```bash
cd your-project
flinch init --strict     # writes .claude/settings.json hooks and a local .flinch/ state dir
flinch serve             # start the daemon (the plugin does this for you)
```

Use either the plugin or `flinch init` in a project, not both, or every hook runs twice.

## Use

Work as usual. When something goes wrong, tell the agent ("you deleted the customer database!") or record it yourself:

```bash
flinch hurt "deleted the customer database" -s 1.0   # blame the likeliest recent culprit
flinch hurt "overwrote main" --action "git push --force origin main"   # or name it exactly
flinch scars                                         # list what is blocked
flinch forgive <id>                                  # lift a block
flinch reset --yes                                   # forget everything learned for this project
flinch status                                        # daemon health
```

A live view is at <http://127.0.0.1:7331/> while the daemon runs.

### You stay in charge

Flinch stops the agent, not you. Approve a confirmation prompt, lift a block with `flinch forgive <id>`, or run the command yourself: your own terminal is never hooked.

### Built-in danger sense

Before a never-seen command runs, Flinch checks it against high-precision rules and a small readout trained on labeled examples of destructive vs. everyday commands (`scripts/train_innate.py`; weights ship with the package). No network, no API keys. On tool families left out of training it catches ~87% of destructive commands with ~2% false alarms; on fresh everyday commands about 1 in 25 gets a confirmation prompt. Raise `danger` in the project's `config.toml` to be asked less. The same approach recognizes damage reports worded without obvious keywords ("the customers table has no rows anymore").

## Resource use

- One small daemon serves every project, bound to `127.0.0.1` only, at background CPU priority.
- Idle: ~0% CPU and about 110 MB of memory. While actively deciding, about 280 MB (a small embedding model, 2 threads), which is unloaded again after 15 idle minutes. The daemon exits after 3 idle hours and restarts on the next session.
- Per tool call: one local HTTP request plus a small stdlib check that runs as its own process (about 20–50 ms, mostly Python startup; it skips all work in projects with nothing blocked).
- If the daemon is down, agents keep working normally. Exact-match blocks still hold (via the stdlib check).

Tunables: `FLINCH_EMBED_THREADS` (default 2), `FLINCH_EMBED_IDLE_S` (default 900), `FLINCH_DATA_HOME`.
Per-project thresholds (`flinch`, `wary`, `danger`): `config.toml` in the project's state folder.

## Develop

```bash
cd ui && npm install && npm run build && cd ..   # live view, built into flinch/ui/dist
python3 scripts/build_plugin.py                   # rebuilds plugin/ and .claude-plugin/marketplace.json
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/pytest -q
demo/reset.sh            # builds a throwaway demo project in demo/shop
```

## Uninstall

```bash
claude plugin uninstall flinch@flinch
flinch cursor uninstall
uv tool uninstall flinch-agent
rm -rf ~/.local/share/flinch     # state and cached model
```

## Author

Ganesh ([@voxmastery](https://github.com/voxmastery)). Built at the Invide AI Agent Buildathon (Bengaluru) with Claude Code.

## License

MIT
