"""Unified entry point for Rankless benchmark / comparison tooling.

    uv run -m pyscripts <command> [options]

Commands:
    compare-sql        Flask/PostgreSQL vs Rust server comparison (correctness + timing)
    compare-branch     branch-vs-branch Rust server comparison
    bench              local throughput + memory benchmark (current branch vs main)
    cache <action>     warm/validate the server response cache

Run any command with -h for its options, e.g. `uv run -m pyscripts compare-sql -h`.

Adding a command is one line: add `"name": "module"` to COMMANDS below, where the
module exposes `run(args)` (and, optionally, `add_arguments(parser)`). Modules are
imported lazily, so a missing/broken dependency in one never breaks the others.
One-off data/figure scripts (nobel, poster_figures, …) stay plain modules:
`uv run -m pyscripts.<name>`.
"""

import argparse
import importlib
from typing import Optional

COMMANDS = {
    "compare-sql": "sql_comparison",
    "compare-branch": "branch_comparison",
    "bench": "bm",
    "cache": "cache_prompting",
}


def _module(name: str):
    return importlib.import_module(f"pyscripts.{name}")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pyscripts",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        metavar="<command>",
        choices=list(COMMANDS),
        help=" | ".join(COMMANDS),
    )
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="command options (pass -h after the command for details)",
    )
    args = parser.parse_args(argv)

    try:
        module = _module(COMMANDS[args.command])
    except ImportError as e:
        parser.error(f"command '{args.command}' is unavailable: {e}")
    sub = argparse.ArgumentParser(
        prog=f"pyscripts {args.command}",
        description=module.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    if hasattr(module, "add_arguments"):
        module.add_arguments(sub)
    module.run(sub.parse_args(args.rest))


if __name__ == "__main__":
    main()
