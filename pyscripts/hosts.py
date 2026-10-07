"""Public hostnames of the site and its backends.

Stdlib + `mcp_server` only, so the stress driver, the access-log reporting and the
monitors read them without `deploy`'s cloud dependencies. The domain and the API hosts
come from `mcp_server` (`MAIN_DOMAIN`, `BACKENDS`).
"""

from urllib.parse import urlsplit

from mcp_server import BACKENDS, MAIN_DOMAIN

ALPHA_DOMAIN = f"alpha.{MAIN_DOMAIN}"
LIVE_DOMAIN = f"www.{MAIN_DOMAIN}"
ALPHA_BACKEND = urlsplit(BACKENDS["alpha"]).netloc
LIVE_BACKEND = urlsplit(BACKENDS["live"]).netloc
