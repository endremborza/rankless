from pyscripts.explore.posts import card_urls, render_article

CARD = "https://rankless.org/card/authors/a-b/map.png?hl=1"
OTHER = "https://rankless.org/card/authors/a-b/tree.png"
POSTS = {
    "x_thread": [{"text": "t", "images": [CARD]}, {"text": "u", "images": []}],
    "linkedin": {"text": "l", "images": [CARD]},
    "facebook": {"text": "f", "images": []},
    "reddit": {"title": "r", "body": "b", "images": [OTHER]},
    "html_post": {
        "title": "T",
        "markdown": f"Intro ![map]({CARD}) and see {OTHER}.",
    },
}


def test_card_urls_collects_each_card_once_across_formats():
    assert card_urls(POSTS) == [CARD, OTHER]


def test_article_references_bundled_cards_relatively():
    cards = {CARD: "cards/map.png", OTHER: "cards/tree.png"}
    assert render_article(POSTS, cards) == (
        "# T\n\nIntro ![map](cards/map.png) and see cards/tree.png.\n"
    )


def test_a_card_whose_url_extends_another_keeps_its_own_file():
    base = "https://rankless.org/card/authors/a-b/tree.png?tree=1&since=2010&isSpec=0"
    branch = f"{base}&paths=5"
    posts = {
        **POSTS,
        "html_post": {"title": "T", "markdown": f"![a]({base}) ![b]({branch})"},
    }
    cards = {base: "cards/base.png", branch: "cards/branch.png"}
    assert render_article(posts, cards) == (
        "# T\n\n![a](cards/base.png) ![b](cards/branch.png)\n"
    )


def test_a_card_url_with_parentheses_in_its_path_is_taken_whole():
    doi = "https://rankless.org/card/hit-papers/10.1175/1520-0469(1963)020%3C0130/tree.png"
    md = f"![c]({doi}) and (see {doi})."
    posts = {**POSTS, "html_post": {"title": "T", "markdown": md}}
    assert card_urls(posts)[-1] == doi
    assert render_article(posts, {doi: "cards/c.png"}) == (
        "# T\n\n![c](cards/c.png) and (see cards/c.png).\n"
    )
