#!/usr/bin/env python3
import re
import sys
from collections import defaultdict
from datetime import datetime

# ================= CONFIG ================= #

CONFIG = {
    "filter_user_agents": True,
    "filter_referrer_chains": True,
    "filter_timing": True,
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
    "min_human_delay": 0.3,
    "max_requests_per_min": 60,
    "session_timeout": 30 * 60,
    "max_chain_length": 3,
}

LOG_PATH = "/tmp/rankless-live.log"

# ================= REGEX ================= #

LOG_RE = re.compile(
    r"(?P<ip>\S+) - \S+ "
    r"\[(?P<time>[^\]]+)\] "
    r'"(?P<request>[^"]+)" '
    r"\d+ \S+ "
    r'"(?P<referrer>[^"]*)" '
    r'"(?P<ua>[^"]*)"'
    r'rt=\S+ uct="[^"]*" uht="[^"]*" urt="[^"]*"'
)

TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"
BOT_UA_RE = re.compile("|".join(CONFIG["bot_ua_patterns"]), re.I)

# ================= DATA ================= #


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
        _, path, _ = m.group("request").split(" ", 2)
    except ValueError:
        return None

    return (
        m.group("ip"),
        Request(
            datetime.strptime(m.group("time"), TIME_FMT),
            path,
            m.group("referrer"),
            line,
        ),
        m.group("ua"),
    )


# ================= FILTERS ================= #


def is_bot_ua(ua):
    return BOT_UA_RE.search(ua) is not None


def is_referrer_chain(reqs):
    chain = 0
    for a, b in zip(reqs, reqs[1:]):
        if b.referrer.endswith(a.path):
            chain += 1
            if chain >= CONFIG["max_chain_length"]:
                return True
        else:
            chain = 0
    return False


def violates_timing(reqs):
    if len(reqs) < 2:
        return False

    deltas = [(b.time - a.time).total_seconds() for a, b in zip(reqs, reqs[1:])]

    if any(d < CONFIG["min_human_delay"] for d in deltas):
        return True

    span = (reqs[-1].time - reqs[0].time).total_seconds()
    rpm = len(reqs) / max(span / 60, 1)
    return rpm > CONFIG["max_requests_per_min"]


# ================= MAIN ================= #


def yield_session(reqs):
    if CONFIG["filter_referrer_chains"] and is_referrer_chain(reqs):
        return
    if CONFIG["filter_timing"] and violates_timing(reqs):
        return

    for r in reqs:
        sys.stdout.write(r.line)


def main():
    sessions = defaultdict(list)

    with open(LOG_PATH, "rt") as f:
        for line in f:
            parsed = parse_log_line(line)
            if not parsed:
                continue

            ip, req, ua = parsed

            if CONFIG["filter_user_agents"] and is_bot_ua(ua):
                continue

            sessions[ip].append(req)

    for reqs in sessions.values():
        reqs.sort(key=lambda r: r.time)

        current = [reqs[0]]
        for r in reqs[1:]:
            if (r.time - current[-1].time).total_seconds() > CONFIG["session_timeout"]:
                yield_session(current)
                current = [r]
            else:
                current.append(r)

        yield_session(current)


if __name__ == "__main__":
    main()
