"""Repo-relative data locations shared across the ops scripts: services.py renders
them into systemd units, deploy.py moves them between boxes. The names the site
also uses are read from `src/lib/assets/data/paths.json` (`src/lib/paths.ts`
reads the same file). Also the zstd level their archives are written at, and the
generated-code ladder (`GEN_DIR`; a forced make of its last file `LADDER_TOP`
rebuilds the whole pipeline). Stdlib-only so it loads on the serving box's
runtime-only venv and before `uv sync` during bootstrap.
"""

import json
import os
from pathlib import Path
from typing import Any

ASSET_DIR = Path(__file__).resolve().parents[1] / "src/lib/assets/data"


def asset(name: str) -> Any:
    return json.loads((ASSET_DIR / name).read_text())


_PATHS = asset("paths.json")
DATA_DIR = _PATHS["dataDir"]
DB_REL = f"{DATA_DIR}/{_PATHS['db']}"
MCP_OBJECTS_REL = f"{DATA_DIR}/{_PATHS['mcpObjects']}"
MCP_LOG_REL = f"{DATA_DIR}/mcp-log"
USER_LEDGER_DIR = _PATHS["userLedger"]
CARD_CACHE_NAME = _PATHS["cardCache"]
SURVEY_LOG_PATH = _PATHS["surveyLog"]
ZSTD_LEVEL = 19
GEN_DIR = "rankless_rs/src/gen"
LADDER_TOP = f"{GEN_DIR}/derive_links5.rs"


# Env overrides let tests (and ad-hoc runs) point every consumer — Python and
# frontend alike — at a scratch copy of the user-data unit; resolve through
# these, never os.environ directly.
def db_path() -> str:
    return os.environ.get("RANKLESS_DB_PATH", DB_REL)


def objects_root() -> str:
    return os.environ.get("MCP_OBJECTS_ROOT", MCP_OBJECTS_REL)
