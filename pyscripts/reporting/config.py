import os
import re
from pathlib import Path

REPORTS_ROOT = Path(os.environ.get("REPORTS_V2_ROOT", "reports-v2")).resolve()

ARCHIVE_DIR = REPORTS_ROOT / "archive"
ARCHIVE_COLD_DIR = REPORTS_ROOT / "archive-cold"
AGGREGATES_DIR = REPORTS_ROOT / "aggregates"
SITE_LOCAL_DIR = REPORTS_ROOT / "site"
SITE_PUBLIC_DIR = REPORTS_ROOT / "site-public"
RUN_LOGS_DIR = REPORTS_ROOT / "logs"

STATE_PATH = REPORTS_ROOT / "state.json"
SALTS_PATH = REPORTS_ROOT / "salts.json"

LIVE_SSH_ID = os.environ.get("REPORTS_LIVE_SSH_ID", "rankless-live")
NGINX_LOG = os.environ.get("REPORTS_NGINX_LOG", "/var/log/nginx/access.log")
NGINX_LOG_ROTATED = NGINX_LOG + ".1"

GHPAGES_WORKTREE = Path(
    os.environ.get("REPORTS_GHPAGES_WORKTREE", "/tmp/rankless-ghpages")
)
GHPAGES_BRANCH = "gh-pages"
GHPAGES_REMOTE = "origin"

SESSION_IDLE_MIN = 30
COLD_AFTER_DAYS = 90
IP_HASH_LEN = 10
SESSION_ID_LEN = 12

LOG_TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"

# Regex for the upstream_time format defined in pyscripts/deploy.py log_format.
# `cs=` and `host=` always trail the line (cs may be empty when no upstream cache
# was consulted). A torn/interleaved line whose bracketed time cannot be parsed
# still matches here; it is dropped downstream in parse_lines, not rejected here.
LINE_RE = re.compile(
    r"^(?P<addr>\S+) - \S+ "
    r"\[(?P<time>[^\]]+)\] "
    r'"(?P<method>[A-Z]+) (?P<path>[^"]*?) [^"]*?" '
    r"(?P<status>\d{3}) (?P<size>\d+) "
    r'"(?P<referrer>[^"]*)" '
    r'"(?P<ua>[^"]*)"'
    r"rt=(?P<rt>\S+) "
    r'uct="(?P<uct>[^"]*)" '
    r'uht="(?P<uht>[^"]*)" '
    r'urt="(?P<urt>[^"]*)" '
    r"cs=(?P<cs>\S*) "
    r"host=(?P<host>\S+)$"
)

# Vhost separation. Live instances are promoted alphas, so the box's access.log
# carries its prior alpha-domain traffic alongside live; `$host` lets the report
# drop the non-live rows. Anything under the alpha.* subdomain is non-live.
ALPHA_HOST_PREFIX = "alpha"

CACHE_STATUSES = {
    "HIT",
    "MISS",
    "BYPASS",
    "EXPIRED",
    "REVALIDATED",
    "STALE",
    "UPDATING",
}


def ensure_dirs() -> None:
    for d in (
        REPORTS_ROOT,
        ARCHIVE_DIR,
        ARCHIVE_COLD_DIR,
        AGGREGATES_DIR,
        SITE_LOCAL_DIR,
        SITE_PUBLIC_DIR,
        RUN_LOGS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
