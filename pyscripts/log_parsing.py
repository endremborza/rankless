import re
import sys
from collections import defaultdict
from datetime import datetime

LOG_PATH = "/tmp/rankless-live.log"

API_PATH_RE = re.compile(r"^https?://api\.rankless\.org/v1/names/([a-z]+)\?q=.+")
API_PATH_RE = re.compile(r"/v1/names/([a-z]+)\?q=.+")
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


class Request:
    __slots__ = ("time", "path", "line")

    def __init__(self, time, path, line):
        self.time = time
        self.path = path
        self.line = line


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
            line,
        ),
    )


def main():
    sessions = defaultdict(list)
    qualifying_ips = set()

    # First pass: parse & detect qualifying IPs
    with open(LOG_PATH, "rt") as f:
        for line in f:
            parsed = parse_log_line(line)
            if not parsed:
                continue

            ip, req = parsed
            sessions[ip].append(req)
            if API_PATH_RE.match(req.path):
                qualifying_ips.add(ip)

    # Second pass: emit all requests from qualifying IPs
    for ip in qualifying_ips:
        for req in sessions[ip]:
            sys.stdout.write(req.line)


if __name__ == "__main__":
    main()
