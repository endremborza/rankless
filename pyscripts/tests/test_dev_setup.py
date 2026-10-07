from urllib.parse import urlsplit

from pyscripts.dev._common import FRONTEND_PORT, REPO_ROOT, read_env_file
from wire.rankless_server.consts import PORT


def test_env_example_addresses_follow_the_defined_ports() -> None:
    env = read_env_file(REPO_ROOT / ".env.example")
    assert urlsplit(env["PUBLIC_BACKEND_URL"]).port == PORT
    assert urlsplit(env["PUBLIC_ORIGIN"]).port == FRONTEND_PORT
