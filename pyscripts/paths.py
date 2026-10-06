"""Repo-relative data locations shared across the ops scripts: services.py renders
them into systemd units, deploy.py moves them between boxes. Stdlib-only (no imports) so it loads on the serving box's runtime-only venv
and before `uv sync` during bootstrap.
"""

import os

DATA_DIR = "data"
DB_REL = f"{DATA_DIR}/rankless.sqlite"
MCP_OBJECTS_REL = f"{DATA_DIR}/mcp-objects"
MCP_LOG_REL = f"{DATA_DIR}/mcp-log"


# Env overrides let tests (and ad-hoc runs) point every consumer — Python and
# frontend alike — at a scratch copy of the user-data unit; resolve through
# these, never os.environ directly.
def db_path() -> str:
    return os.environ.get("RANKLESS_DB_PATH", DB_REL)


def objects_root() -> str:
    return os.environ.get("MCP_OBJECTS_ROOT", MCP_OBJECTS_REL)
