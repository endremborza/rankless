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

# Vhost separation. A live box is a promoted alpha, so its access.log mixes live
# traffic with the box's prior alpha vhosts AND junk hitting it directly (raw IP,
# EC2 hostname, spoofed Host scanners). `$host` lets the report keep only the live
# domains. An allowlist is robust where an `alpha*` prefix denylist let the
# non-alpha junk through — most notably the old alpha box's raw IP counted as live.
LIVE_HOSTS = {"www.rankless.org", "rankless.org", "api.rankless.org"}

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
