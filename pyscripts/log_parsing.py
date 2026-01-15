#!/usr/bin/env python3
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# ================= CONFIG ================= #

CONFIG = {
    "filter_user_agents": True,
    "filter_referrer_chains": True,
    "filter_timing": True,
    # User-Agent filtering
    "bot_ua_patterns": [
        r"bot",
        r"crawler",
        r"spider",
        r"slurp",
        r"curl",
        r"wget",
        r"python",
        r"httpclient",
        r"libwww",
        r"go-http-client",
    ],
    # Timing heuristics
    "min_human_delay": 0.3,  # seconds between requests
    "max_requests_per_min": 60,  # sustained browsing speed
    "session_timeout": 30 * 60,  # seconds
    # Referrer chaining
    "max_chain_length": 3,  # tolerate a little JS navigation
}

"""
log_format upstream_time '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent"'
                         'rt=$request_time uct="$upstream_connect_time" uht="$upstream_header_time" urt="$upstream_response_time"';
"""

LOG_RE = re.compile(
    r"(?P<ip>\S+) \S+ \S+ "
    r"\[(?P<time>[^\]]+)\]  "
    r'"(?P<request>[^"]+)" '
    r"(?P<status>\d+) \S+  "
    r'"(?P<referrer>[^"]*)" '
    r'"(?P<ua>[^"]*)" '
    r"rt=(?P<rt>\S+) "
    r'uct="(?P<uct>[^"]*)" '
    r'uht="(?P<uht>[^"]*)" '
    r'urt="(?P<urt>[^"]*)"'
)

TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"

BOT_UA_RE = re.compile("|".join(CONFIG["bot_ua_patterns"]), re.I)

# ================= DATA STRUCTURES ================= #


class Request:
    __slots__ = ("time", "path", "referrer", "line")

    def __init__(self, time, path, referrer, line):
        self.time = time
        self.path = path
        self.referrer = referrer
        self.line = line


# ================= PARSING ================= #


def parse_log_line(line):
    m = LOG_RE.match(line)
    if not m:
        return None

    try:
        method, path, _ = m.group("request").split(" ", 2)
    except ValueError:
        return None

    return {
        "ip": m.group("ip"),
        "time": datetime.strptime(m.group("time"), TIME_FMT),
        "path": path,
        "referrer": m.group("referrer"),
        "ua": m.group("ua"),
        "line": line,
    }


# ================= FILTERS ================= #


def is_bot_ua(ua):
    return BOT_UA_RE.search(ua) is not None


def is_referrer_chain(requests):
    """
    Detects crawler-like:
    /a -> /b -> /c where each referer == previous path
    """
    chain = 0
    for prev, curr in zip(requests, requests[1:]):
        if curr.referrer.endswith(prev.path):
            chain += 1
            if chain >= CONFIG["max_chain_length"]:
                return True
        else:
            chain = 0
    return False


def violates_timing(requests):
    if len(requests) < 2:
        return False

    deltas = [(b.time - a.time).total_seconds() for a, b in zip(requests, requests[1:])]

    if any(d < CONFIG["min_human_delay"] for d in deltas):
        return True

    span = (requests[-1].time - requests[0].time).total_seconds()
    rpm = len(requests) / max(span / 60, 1)
    return rpm > CONFIG["max_requests_per_min"]


# ================= MAIN LOGIC ================= #

LOG_PATH = "/tmp/rankless-live.log"


def main():

    sessions = defaultdict(list)

    with open(LOG_PATH, "rt") as fp:
        for line in fp:
            parsed = parse_log_line(line)
            if not parsed:
                continue
            if CONFIG["filter_user_agents"] and is_bot_ua(parsed["ua"]):
                continue
            sessions[parsed["ip"]].append(
                Request(
                    parsed["time"],
                    parsed["path"],
                    parsed["referrer"],
                    parsed["line"],
                )
            )

    for ip, requests in sessions.items():
        requests.sort(key=lambda r: r.time)

        # Split into sessions
        current = [requests[0]]
        for r in requests[1:]:
            if (r.time - current[-1].time).total_seconds() > CONFIG["session_timeout"]:
                yield_session(current)
                current = [r]
            else:
                current.append(r)
        yield_session(current)


def yield_session(requests):
    if CONFIG["filter_referrer_chains"] and is_referrer_chain(requests):
        return

    if CONFIG["filter_timing"] and violates_timing(requests):
        return

    for r in requests:
        sys.stdout.write(r.line)


if __name__ == "__main__":
    main()
