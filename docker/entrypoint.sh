#!/usr/bin/env bash
# Runs inside the rankless-dev-test container. Mirrors the host repo into a
# clean working dir, runs `make bootstrap`, then uses the canonical
# ServerProcess helper (pyscripts.server_ops) to verify the backend boots.
set -euo pipefail

: "${NANO_ARTIFACT_URL:?must be set (host bootstrap target)}"
export CCL_CLONE_DIR=/opt/ccl-science-data

echo "==> syncing /host into /work (excluding build artefacts)"
mkdir -p /work
rsync -a --delete \
    --exclude='/.env' \
    --exclude='/target/' \
    --exclude='/node_modules/' \
    --exclude='/.venv/' \
    --exclude='/libs/' \
    --exclude='/data/oa-root/' \
    --exclude='/data/oa-snapshot/' \
    --exclude='/data/oa-test/' \
    --exclude='/data/nano-root/' \
    --exclude='/data/nano-snapshot/' \
    --exclude='/.svelte-kit/' \
    --exclude='/build/' \
    --exclude='/test-results/' \
    --exclude='/logs/' \
    --exclude='/reports/' \
    --exclude='/reports-v2/' \
    --exclude='nano-snapshot.tar.zst*' \
    /host/ /work/

cd /work

echo "==> make bootstrap"
make bootstrap

echo "==> verifying backend boots cleanly"
uv run python -c '
import sys
from pyscripts.server_ops import ServerConfig, ServerProcess
from pyscripts.dev._common import env_with_dotenv, resolve_path

env = env_with_dotenv()
data_root = resolve_path(env["OA_ROOT"])
cfg = ServerConfig(data_root=data_root)
with ServerProcess(cfg) as srv:
    srv.start()
    srv.wait_ready(max_attempts=60)
    print("OK — backend healthy at", cfg.base_url)
'

echo
echo "==> test-dev-env: PASSED"
