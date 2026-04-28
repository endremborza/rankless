import re
from collections import Counter
from urllib.parse import urlsplit

# Ordered list of (compiled_pattern, template, capture_names).
# First match wins. Regexes anchor on path only (no query). Trailing slashes ignored.
_RAW_RULES: list[tuple[str, str]] = [
    # API v1
    (r"^/v1/names/([a-z\-]+)$", "/v1/names/{etype}"),
    (r"^/v1/slice/([a-z\-]+)/(\d+)/(\d+)$", "/v1/slice/{etype}/{from}/{to}"),
    (r"^/v1/views/([a-z\-]+)/([^/]+)$", "/v1/views/{etype}/{semantic_id}"),
    (r"^/v1/sem-id-via-oa/([a-z\-]+)/([^/]+)$", "/v1/sem-id-via-oa/{etype}/{oa_id}"),
    (r"^/v1/orcid/([^/]+)$", "/v1/orcid/{orcid_id}"),
    (r"^/v1/resolve/work$", "/v1/resolve/work"),
    (r"^/v1/resolve/author$", "/v1/resolve/author"),
    (r"^/v1/paper-profile/([^/]+)$", "/v1/paper-profile/{asem}"),
    (r"^/v1/author-peers/([^/]+)$", "/v1/author-peers/{asem}"),
    (r"^/v1/trees/([a-z\-]+)/([^/]+)$", "/v1/trees/{root_type}/{semantic_id}"),
    (r"^/v1/shallows/([a-z\-]+)$", "/v1/shallows/{root_type}"),
    (r"^/v1/works/([a-z\-]+)/([^/]+)/(\d+)$", "/v1/works/{etype}/{semantic_id}/{from}"),
    (r"^/v1/counts/?$", "/v1/counts"),
    (r"^/v1/tops/?$", "/v1/tops"),
    (r"^/v1/specs(?:/.*)?$", "/v1/specs"),
    # Frontend special files
    (r"^/$", "/"),
    (r"^/about/?$", "/about"),
    (r"^/login/?$", "/login"),
    (r"^/logout/?$", "/logout"),
    (r"^/survey/?$", "/survey"),
    (r"^/dev-login/?$", "/dev-login"),
    (r"^/callback/?$", "/callback"),
    (r"^/robots\.txt$", "/robots.txt"),
    (r"^/sitemap.*\.xml$", "/sitemap*.xml"),
    (r"^/favicon\.ico$", "/favicon.ico"),
    # Frontend api (ledger flow)
    (r"^/api/ledger$", "/api/ledger"),
    (r"^/api/ledger/[^/]+$", "/api/ledger/{event_id}"),
    (r"^/api/ledger-status$", "/api/ledger-status"),
    (r"^/api/papers/claim$", "/api/papers/claim"),
    (r"^/api/papers/disown$", "/api/papers/disown"),
    (r"^/api/papers/merge$", "/api/papers/merge"),
    (r"^/api/authors/merge-request$", "/api/authors/merge-request"),
    (r"^/api/survey$", "/api/survey"),
    # Asset-ish frontend routes
    (r"^/tiles/.+$", "/tiles/{...}"),
    (r"^/pic/.+$", "/pic/{...}"),
    (r"^/img/.+$", "/img/{...}"),
    (r"^/pathlogo/.+$", "/pathlogo/{...}"),
    (r"^/oa-id/.+$", "/oa-id/{...}"),
    (r"^/path-to-person/.+$", "/path-to-person/{...}"),
    # Static / build assets
    (r"^/_app/.+$", "/_app/{...}"),
    # Frontend SSR pages: /{rootType}/{...semanticId}
    (r"^/([a-z\-]+)/table/?$", "/{rootType}/table"),
    (r"^/([a-z\-]+)/[^?]+$", "/{rootType}/{...semanticId}"),
    (r"^/([a-z\-]+)/?$", "/{rootType}"),
]

_RULES = [(re.compile(p), tpl) for p, tpl in _RAW_RULES]


def template(path: str) -> str:
    """Return route template for a given URL path (with or without query)."""
    raw = path
    if not path:
        return "_unknown"
    if path.startswith(("http://", "https://")):
        path = urlsplit(path).path or "/"
    else:
        # Strip query string if present.
        q = path.find("?")
        if q >= 0:
            path = path[:q]
    if not path.startswith("/"):
        return "_unknown"
    for rx, tpl in _RULES:
        if rx.match(path):
            return tpl
    return "_unknown"


def has_query(path: str) -> bool:
    return "?" in path


def collect_unmatched(paths) -> Counter:
    c: Counter = Counter()
    for p in paths:
        if template(p) == "_unknown":
            c[p] += 1
    return c
