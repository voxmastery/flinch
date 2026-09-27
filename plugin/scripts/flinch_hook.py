"""Hook launcher: stdlib only, runs under the system python3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
if sys.argv[1:2] == ["scarcheck"]:  # hot path, every tool call: import only what it needs
    from flinch.scarcheck import main  # noqa: E402

    sys.exit(main([]))
from flinch.relay import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
