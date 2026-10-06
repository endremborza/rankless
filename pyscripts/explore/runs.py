"""Identity and home of AI-agent runs.

Every agentic workflow (deep exploration, the game-card round) names its runs
`<workflow>-<scope>-<UTC stamp>` and writes its outputs into a dir of that name
under the run root, `$EXTERNAL_DATA_ROOT/runs/`: private, never served by the
site, synced between boxes with `make external-push|pull`. What a run makes
public leaves it by hand: a story through rankless-stories, game cards through
the object store.
"""

from datetime import UTC, datetime
from pathlib import Path

from pyscripts import external_data

SOURCE = "runs"
STAMP_FMT = "%Y%m%dT%H%M%S"


def root() -> Path:
    return external_data.source_dir(SOURCE)


def run_stamp() -> str:
    return datetime.now(UTC).strftime(STAMP_FMT)


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_name(workflow: str, scope: str) -> str:
    return f"{workflow}-{scope}-{run_stamp()}"
