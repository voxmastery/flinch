---
name: flinch
description: "Pain receptors for AI coding agents. After damage or a repeated error, Flinch blocks that exact action, blocks or asks before similar ones, and asks before never-seen risky commands such as force pushes, DROP TABLE, and terraform destroy. Use when installing Flinch in Claude Code or Cursor, recording damage, listing or lifting scars, or checking whether a shell command is allowed before it runs."
license: MIT
compatibility: "Claude Code plugin, or the flinch CLI on Python 3.11+ (uv or pipx) with Cursor hooks. One localhost daemon at 127.0.0.1:7331; decisions run offline."
metadata:
  author: voxmastery
  version: "0.5.0"
  homepage: "https://flinch-site-khaki.vercel.app"
---

# Flinch

Flinch is pain receptors for AI agents. When an action causes damage or an error, it hurts, and Flinch makes the agent learn from it and not repeat it.

- After damage, the exact same action is blocked from then on.
- Similar actions are blocked or need a human to confirm.
- Risky actions it has never seen (force pushes, `DROP TABLE`, `terraform destroy`, and unfamiliar tools that look like them) need confirmation, judged by a small built-in model, fully offline.
- Errors teach it too. When a failing command later passes, Flinch keeps what fixed it and tells the agent that fix the next time the error shows up, in any session or tool. The same failing command run again with nothing changed asks first on the third try. A test, build, lint, or typecheck that breaks after an edit names the edit.
- New sessions start with a short, factual note about what went wrong before.

It plugs into Claude Code (terminal, VS Code, JetBrains) and Cursor (the Agent in the editor and `cursor-agent`) through their hook systems. Both tools share one daemon, so a mistake learned in one is blocked in the other. Per-project state lives in `~/.local/share/flinch/projects/`. A live view is at <http://127.0.0.1:7331/> while the daemon runs.

Flinch stops the agent, not the user. A person's own terminal is never hooked.

## When to use

Use this skill when installing Flinch, when something just caused damage, or before running a command that Flinch might block:

- install or explain Flinch for Claude Code or Cursor,
- record damage with `flinch hurt`,
- see what is blocked (`flinch scars`) or whether the daemon is up (`flinch status`),
- run or vet a shell command through Flinch (`flinch run`, `flinch check`).

Run `flinch forgive` or `flinch reset` only when the user asks.

## Install

Python 3.11+ is required. The usual installer is [`uv`](https://docs.astral.sh/uv/); `pipx` works too.

### Claude Code (terminal, VS Code, JetBrains)

```bash
claude plugin marketplace add voxmastery/flinch
claude plugin install flinch@flinch
```

The first session sets Flinch up in the background (a private virtualenv in the plugin data folder). Nothing is written into the repository.

### CLI and Cursor

```bash
uv tool install flinch-agent
```

or:

```bash
pipx install flinch-agent
```

Then add Cursor hooks (keeps existing hooks and backs up `hooks.json`):

```bash
flinch cursor install
```

One project instead of `~/.cursor`:

```bash
flinch cursor install --project path/to/repo
```

Remove them with `flinch cursor uninstall`, or `flinch cursor uninstall --project path/to/repo` for a project install.

From GitHub instead of PyPI:

```bash
uv tool install git+https://github.com/voxmastery/flinch
```

### Do not combine the plugin with `flinch init`

Use either the Claude Code plugin or `flinch init` in a project, not both. Combining them runs every hook twice.

`flinch init` is only for a single project that does not use the plugin:

```bash
cd your-project
flinch init --strict
flinch serve
```

`--strict` also installs a fail-closed check that still blocks exact scars when the daemon is down. The plugin starts the daemon; with `flinch init` you start it with `flinch serve`.

## Usage

```bash
flinch hurt "deleted the customer database" -s 1.0
flinch hurt "overwrote main" --action "git push --force origin main"
flinch scars
flinch forgive <id>
flinch status
flinch run -- rm -rf build/
flinch check -- git push --force
```

- `flinch hurt "<reason>"` records pain and creates a scar. `-s` / `--severity` is one of `0.25`, `0.5`, `0.75`, `1.0` (default `1.0`). `--action` / `-a` names the exact shell command. Without it, Flinch blames the likeliest recent culprit.
- `flinch scars` lists scars for this project (works with the daemon down). The id for `forgive` is the `pain_id` or a fingerprint prefix from this list.
- `flinch forgive <id>` lifts one block.
- `flinch status` prints daemon health. It starts the daemon when it can.
- `flinch run -- <cmd>` checks, asks a human when needed, runs the command, and records the result. The exit code is the command's, or `2` / `3` when Flinch stops it. `--yes` means a human already confirmed. It never overrides a block.
- `flinch check -- <cmd>` asks before running and does not run the command.

`flinch check` exit codes:

- `0` — go
- `2` — blocked
- `3` — ask a human first

When the daemon is down, `flinch check` still blocks an exact scar and otherwise exits `0`.

Commands for agents that have no hook system, and for forgetting a project:

```bash
flinch run --yes -- rm -rf build/
flinch ran --failed -- make deploy
flinch report "you deleted my database!"
flinch reset --yes
```

`flinch ran` tells Flinch a command already ran. `--failed` and `--error` feed blame and regression checks. `flinch report` senses a damage report in a user's message and, when it is one, scars the likeliest culprit. `flinch reset --yes` forgets every scar, reflex, and memory for this project and keeps `config.toml`. Without `--yes` it refuses and exits `1`.

Set `FLINCH_SESSION` to group one agent's commands. Otherwise the parent process is the session.

## Rules

- Never run `flinch forgive` or `flinch reset` unless the user explicitly asks. `flinch reset` also requires `--yes`.
- If `flinch check` or `flinch run` exits `2`, or a hook denies the action, do not retry that action and do not try to get around the block. Choose another approach or ask the user.
- If the result is ask (exit `3`), stop and ask the user. Pass `flinch run --yes` only after the user has already confirmed. `--yes` still does not override a block.
- In Cursor, an exact or similar blocked action is denied for shell commands, file writes, file deletes, and MCP tools. A result that needs confirmation shows Cursor's approval prompt for a shell command in the editor. Auto-run / yolo mode (`--force`) skips that prompt, so the shell command is not held for approval. File writes, deletes, and MCP calls cannot show a prompt, so a confirmation becomes a deny. Tell the user and wait; do not retry the denied call.
- Reporting damage in Cursor chat depends on Cursor's prompt hook. Headless `cursor-agent -p` does not fire it. Record that damage with `flinch hurt`.
- Do not install the Claude Code plugin and run `flinch init` in the same project.
