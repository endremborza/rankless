from pyscripts.reporting.paths import has_query, template


def test_api_routes():
    assert template("/v1/names/authors") == "/v1/names/{etype}"
    assert template("/v1/names/authors?q=foo") == "/v1/names/{etype}"
    assert template("/v1/views/authors/asem-x") == "/v1/views/{etype}/{semantic_id}"
    assert template("/v1/trees/authors/asem-x") == "/v1/trees/{root_type}/{semantic_id}"
    assert template("/v1/works/authors/asem-x/0") == "/v1/works/{etype}/{semantic_id}/{from}"
    assert template("/v1/slice/authors/0/40") == "/v1/slice/{etype}/{from}/{to}"
    assert template("/v1/paper-profile/asem-x") == "/v1/paper-profile/{asem}"
    assert template("/v1/author-peers/asem-x") == "/v1/author-peers/{asem}"
    assert template("/v1/orcid/0000-0001-2345-6789") == "/v1/orcid/{orcid_id}"
    assert template("/v1/resolve/work?doi=10.x") == "/v1/resolve/work"


def test_frontend_routes():
    assert template("/") == "/"
    assert template("/about") == "/about"
    assert template("/login") == "/login"
    assert template("/survey") == "/survey"
    assert template("/callback?code=xyz") == "/callback"
    assert template("/robots.txt") == "/robots.txt"
    assert template("/sitemap-index.xml") == "/sitemap*.xml"
    assert template("/sitemap-2.xml") == "/sitemap*.xml"


def test_ledger_api():
    assert template("/api/ledger") == "/api/ledger"
    assert template("/api/ledger/abc-123") == "/api/ledger/{event_id}"
    assert template("/api/ledger-status") == "/api/ledger-status"
    assert template("/api/papers/claim") == "/api/papers/claim"
    assert template("/api/authors/merge-request") == "/api/authors/merge-request"


def test_assetlike():
    assert template("/tiles/foo/bar/baz.png") == "/tiles/{...}"
    assert template("/pic/abc/def") == "/pic/{...}"
    assert template("/pathlogo/x") == "/pathlogo/{...}"


def test_ssr_pages():
    assert template("/institutions/table") == "/{rootType}/table"
    assert template("/institutions/harvard") == "/{rootType}/{...semanticId}"
    assert template("/authors/some-author/sub-page") == "/{rootType}/{...semanticId}"
    assert template("/institutions") == "/{rootType}"


def test_unknown():
    assert template("foobar") == "_unknown"
    assert template("") == "_unknown"


def test_has_query():
    assert has_query("/v1/names/authors?q=foo")
    assert not has_query("/v1/names/authors")
