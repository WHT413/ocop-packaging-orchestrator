from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def main() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from ocop_pack.cli.app import app

    app()


if __name__ == "__main__":
    main()
