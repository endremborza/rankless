"""Repo-relative data locations shared across the ops scripts: services.py renders
them into systemd units, deploy.py moves them between boxes, mcp_worker.py reads
them. Stdlib-only (no imports) so it loads on the serving box's runtime-only venv
and before `uv sync` during bootstrap.
"""

DATA_DIR = "data"
DB_REL = f"{DATA_DIR}/rankless.sqlite"
MCP_SESSIONS_REL = f"{DATA_DIR}/mcp-sessions"
MCP_OBJECTS_REL = f"{DATA_DIR}/mcp-objects"
# The on-disk companions of the user DB: session artifacts + object bundles.
# Deploys rsync them next to the DB handoff; backups mirror them next to the
# DB snapshots.
MCP_ARTIFACT_RELS = (MCP_SESSIONS_REL, MCP_OBJECTS_REL)
