"""Fail when plugin/lib/flinch copies drift from the package modules the hooks import."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "__init__.py",
    "auth.py",
    "jsonfile.py",
    "locate.py",
    "messages.py",
    "normalize.py",
    "redact.py",
    "relay.py",
    "rules.py",
    "scarcheck.py",
)


def main() -> int:
    drifted = []
    for name in NAMES:
        src = ROOT / "flinch" / name
        copy = ROOT / "plugin" / "lib" / "flinch" / name
        if not copy.exists() or src.read_bytes() != copy.read_bytes():
            drifted.append(name)
    if drifted:
        print("plugin copies differ from flinch/:", ", ".join(drifted))
        return 1
    print(f"plugin copies match ({len(NAMES)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
