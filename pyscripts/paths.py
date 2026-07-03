"""Repo-relative data locations shared across the ops scripts: services.py renders
them into systemd units, deploy.py moves them between boxes, mcp_worker.py reads
them. Stdlib-only (no imports) so it loads on the serving box's runtime-only venv
and before `uv sync` during bootstrap.
"""

DATA_DIR = "data"
DB_REL = f"{DATA_DIR}/rankless.sqlite"
MCP_SESSIONS_REL = f"{DATA_DIR}/mcp-sessions"
