"""Fixture log lines covering the format variants we expect in the wild."""

# Post-Phase-0 line (cs= field present).
LINE_POST_CS_HUMAN = (
    '203.0.113.42 - - [28/Apr/2026:13:14:15 +0000] '
    '"GET /v1/names/authors?q=darwin HTTP/2.0" 200 4321 '
    '"https://www.rankless.org/" '
    '"Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"'
    'rt=0.045 uct="0.001" uht="0.040" urt="0.040" cs=MISS'
)

LINE_POST_CS_BOT = (
    '198.51.100.7 - - [28/Apr/2026:13:14:16 +0000] '
    '"GET /sitemap.xml HTTP/1.1" 200 1024 '
    '"-" '
    '"Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"'
    'rt=0.012 uct="0.000" uht="0.011" urt="0.011" cs=HIT'
)

# Pre-Phase-0 line (no cs= field).
LINE_PRE_CS = (
    '192.0.2.1 - - [28/Apr/2026:13:14:17 +0000] '
    '"GET /institutions/harvard HTTP/2.0" 200 8765 '
    '"https://www.google.com/" '
    '"Mozilla/5.0 (Macintosh; Intel Mac OS X) Safari/605.1.15"'
    'rt=0.080 uct="0.002" uht="0.075" urt="0.075"'
)

# Hyphenated upstream timings (no upstream involvement).
LINE_NO_UPSTREAM = (
    '198.51.100.99 - - [28/Apr/2026:13:14:18 +0000] '
    '"GET /robots.txt HTTP/1.1" 200 56 '
    '"-" "AhrefsBot/7.0"'
    'rt=0.001 uct="-" uht="-" urt="-" cs=BYPASS'
)

# 429 rate-limited.
LINE_429 = (
    '203.0.113.99 - - [28/Apr/2026:13:14:19 +0000] '
    '"GET /v1/trees/authors/asem-foo HTTP/2.0" 429 0 '
    '"-" "python-requests/2.31.0"'
    'rt=0.000 uct="-" uht="-" urt="-" cs=BYPASS'
)

# Empty UA.
LINE_EMPTY_UA = (
    '203.0.113.5 - - [28/Apr/2026:13:14:20 +0000] '
    '"GET / HTTP/1.1" 200 1234 '
    '"-" "-"'
    'rt=0.005 uct="-" uht="-" urt="-" cs=HIT'
)

# Garbage line for failure counting.
LINE_GARBAGE = "this is not an nginx log line at all"

ALL = [
    LINE_POST_CS_HUMAN,
    LINE_POST_CS_BOT,
    LINE_PRE_CS,
    LINE_NO_UPSTREAM,
    LINE_429,
    LINE_EMPTY_UA,
]
