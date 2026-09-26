"""Rewrite one memory namespace with the current embedder.

Script and admin entry only. Chat tools do not call this.
"""

from __future__ import annotations

import argparse
import json


def main(argv: list[str] | None = None) -> int:
    from .. import db
    from .store import reembed_namespace

    parser = argparse.ArgumentParser(
        description="Re-embed every document in one memory namespace"
    )
    parser.add_argument("namespace", choices=("profile", "people", "jobs", "session", "corpus"))
    args = parser.parse_args(argv)
    db.init_db()
    result = reembed_namespace(args.namespace)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
