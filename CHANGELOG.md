# Changelog

## Unreleased

- Shipped danger weights still load when ONNX whitening drifts slightly across CPU architectures. The projection must match, and a different embedder stays on rules only.
- Session start with a task prompt only injects scars that share the task. A cold start with no task still recalls the worst scars.
- The daemon requires a per-user bearer token on every route, rejects unexpected `Host` headers, and requires `application/json` on hook routes. It still binds to loopback only.
- The offline hook runs the danger rules after basename, `sudo`, `git -c`, and `rm` long-option normalization, so those bypasses are blocked with the daemon down.
- A present but unreadable or wrong-shape `scars.json` fails closed with a short message.
- `scars.json`, `errors.json`, and `recent.json` carry `schema_version`. Incompatible files are quarantined, not overwritten. `circuit.npz` is archived the same way. Saves take a file lock and `fsync` before replace.
- Redaction covers URL userinfo, `*_URL` / `DATABASE_URL` values, and `sk_live_`-style keys. Logs are mode `0600`. State directories are mode `0700`.
- The daemon keeps the embedding model loaded and does not answer `/health` until that load finishes.
- CI runs the tests and the trajectory eval on Linux and macOS, Python 3.11 and 3.12, and checks that `plugin/lib/flinch` matches `flinch/`.
- Config thresholds must satisfy `wary < flinch < danger`. Anything else uses the defaults.
