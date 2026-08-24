"""Unified entry point for Rankless tooling (`uv run -m pyscripts <command>`).

Dispatch, help and argument parsing are signature-driven via protocli:
commands map to lazily-imported modules whose `main` (or `_dispatcher`)
defines the CLI. `-h` lists commands, `--help-all` prints every parser.

Adding a command is one line in COMMANDS; the module either exposes
`main(...)` (typed signature = the parser) or a nested `_dispatcher`.
"""

from protocli import Dispatcher

COMMANDS = {
    "compare-sql": "pyscripts.sql_comparison",
    "compare-branch": "pyscripts.branch_comparison",
    "bench": "pyscripts.bm",
    "cache": "pyscripts.cache_prompting",
    "recalc": "pyscripts.recalc",
    "claims": "pyscripts.claims",
    "release-report": "pyscripts.release_report",
    "cohort-baseline": "pyscripts.cohort_baseline",
    "deploy": "pyscripts.deploy",
    "fleet": "pyscripts.fleet",
    "stress": "pyscripts.stress",
    "review-ledger": "pyscripts.review_ledger",
    "calibrate-map": "pyscripts.calibrate_map",
    "game-cards": "pyscripts.explore.game_cards",
    "country-cards": "pyscripts.explore.country_cards",
    "impact-stories": "pyscripts.explore.impact_stories",
    "objects": "pyscripts.object_store",
    "userdb": "pyscripts.userdb",
}


def main() -> None:
    Dispatcher("pyscripts", COMMANDS).run()


if __name__ == "__main__":
    main()
