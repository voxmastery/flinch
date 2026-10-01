# Security

Flinch is a local safety layer for one developer’s coding agent. It is not a multi-tenant service.

## Threat model

- **Who it is for.** One user on one machine. The daemon listens on loopback only (`127.0.0.1`, `localhost`, or `::1`).
- **What it protects.** It tries to stop an agent from repeating an action that already caused damage, and from a short list of well-known destructive commands, including when the daemon is down.
- **Trusted.** The user account that owns `~/.local/share/flinch` and the project state directory. That account can read the daemon token, the scars, and the logs.
- **Not trusted.** Other local users, a browser page, and a remote host. A request without the per-user bearer token is rejected. A request whose `Host` is not loopback is rejected. Hook routes require `application/json`.
- **Daemon down.** The offline hook still blocks an exact scar and the high-precision danger rules (`/bin/rm -rf`, `rm --recursive --force`, `sudo /bin/rm -rf /`, `git -c … push --force`). A `scars.json` that is present but unreadable, or the wrong shape, blocks with a short message instead of failing open.
- **Secrets.** Commands are redacted before they are logged, embedded, or stored. That includes URL userinfo, `*_URL` / `DATABASE_URL` values, and `sk_live_` / `sk_test_` keys. State files are mode `0600`. State directories are mode `0700`.
- **Corrupt state.** A newer or unreadable `scars.json`, `errors.json`, `recent.json`, or `circuit.npz` is moved aside and kept. It is not overwritten.

## Reporting

Open a private security advisory on the GitHub repository, or email the address in `pyproject.toml`.
