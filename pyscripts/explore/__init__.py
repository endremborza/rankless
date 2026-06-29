"""Agent reasoning paths over collected entity evidence.

The Playwright collector (tests/sanity-data.spec.ts) writes a wide, randomized
snapshot set to logs/sanity_check_data.json. Each path samples from it (see each
module's SAMPLE) and runs one Claude Code CLI pass; the orchestrator merges every
path's section into a single report. Paths:

- bugs     -> data-quality / correctness review; data findings become draft
              ledger suggestions (the same format ORCID users submit).
- features -> feature proposals grounded in the data and .cril/ideas.md.
- stories  -> shareable, data-grounded narratives.
"""

from dataclasses import dataclass, field
from pathlib import Path

LOG_DIR = Path("logs")
REPORT_PATH = LOG_DIR / "explore-report.md"
SUGGESTIONS_PATH = LOG_DIR / "explore-suggestions.jsonl"


@dataclass
class PathResult:
    """What a path returns: its markdown section plus side outputs."""

    section: str
    exit_code: int = 0
    suggestions: list[dict] = field(default_factory=list)
