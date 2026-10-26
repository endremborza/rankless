from pyscripts.explore import infographic


def paper(year: int, authors: list[str], count: int | None = None) -> dict:
    return {
        "year": year,
        "authorCount": len(authors) if count is None else count,
        "authorships": [{"author": a} for a in authors],
    }


def test_coauthors_skip_papers_the_site_draws_no_coauthor_relation_from():
    papers = [
        paper(2001, ["me", "small"]),
        paper(2002, ["me", "small", "alphabetical"], infographic.TEAM_LIMIT + 1),
        paper(2003, ["me", "small"]),
    ]
    by_id, collab = infographic.coauthors(papers, "me", str.upper)
    assert by_id == {"small": [2001, 2003]}
    assert collab == {"SMALL": [2001, 2003]}


def test_timeline_rows_keep_a_marked_coauthor_in_its_sorted_place():
    years = {
        "early": [2001, 2002],
        "marked": [2003],
        "late": [2005, 2006],
        "later": [2007] * 3,
    }
    a = {"team": {k: {"years": ys} for k, ys in years.items()}}
    opts = {"sort": "first", "n": 3, "min": 2}
    rows = infographic.timeline_rows(a, opts, [("marked", "Marked")])
    assert [k for k, _ in rows] == ["early", "marked", "late"]


def test_sources_that_display_alike_carry_their_years():
    sources = {1: "Physical review. D", 2: "Physical review. D. Particles and fields"}
    papers = [
        {"source": 2, "year": 1980},
        {"source": 2, "year": 2010},
        {"source": 1, "year": 2020},
    ]
    names = infographic.journal_names(papers, sources)
    assert names == {
        "Physical review. D. Particles and fields": "Physical Review D, 1980–2010",
        "Physical review. D": "Physical Review D, 2020",
    }


def test_a_draw_restamps_only_the_page_version(tmp_path):
    page = tmp_path / "index.md"
    edited = '---\ntitle: "Edited"\ndata_version: "old"\n---\n\nText an editor wrote.\n'
    page.write_text(edited)
    infographic.stamp_page(page, {}, [], "new|full|run")
    assert page.read_text() == edited.replace('"old"', '"new|full|run"')
    assert infographic.page_version(page) == "new|full|run"


def test_a_journal_abbreviates_to_its_iso4_form():
    assert (
        infographic.abbreviation("Nature reviews. Neuroscience")
        == "Nat. Rev. Neurosci."
    )
    assert (
        infographic.abbreviation("The Journal of Organic Chemistry") == "J. Org. Chem."
    )


def test_sections_deal_into_the_columns_with_the_shortest_tallest_one():
    cols = infographic.deal([5, 3, 3, 2, 1], 2)
    assert cols[0][0] == 0
    assert max(sum([5, 3, 3, 2, 1][i] for i in c) for c in cols) == 7
    assert all(c == sorted(c) for c in cols)
