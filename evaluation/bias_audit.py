"""Command line entry point: see evaluation/README.md."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evalkit.cli_bias import main  # noqa: E402

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # older Windows consoles cannot print every character: never crash on that
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    raise SystemExit(main())
