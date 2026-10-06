"""The work-subject keys agree with src/lib/server/ledger-hash.ts (same vectors as its test)."""

import hashlib

from pyscripts.ledger_ids import (
    author_subject,
    curated_line,
    subject_hash,
    work_canonical_key,
    work_subject,
)


def test_work_key_prefers_the_oa_id_and_lowercases_a_doi() -> None:
    assert work_canonical_key(work_subject(123, "10.1/x", "T", 2001)) == "oa:123"
    by_doi = work_subject(None, "https://doi.org/10.1/Foo", "T", None)
    assert work_canonical_key(by_doi) == "doi:10.1/foo"
    claim = subject_hash({"kind": "claim_paper", "work": by_doi})
    assert claim == hashlib.sha1(b"doi:10.1/foo").hexdigest()


def test_pair_keys_ignore_which_side_is_kept() -> None:
    a, b = author_subject(2, None, "A"), author_subject(1, "0000-1", "B")
    merged = subject_hash({"kind": "merge_authors", "keep": a, "drop": b})
    assert merged == subject_hash({"kind": "merge_authors", "keep": b, "drop": a})
    assert merged == hashlib.sha1(b"oa:2|orcid:0000-1").hexdigest()
    w1, w2 = work_subject(7, None, "T", None), work_subject(3, None, "T", None)
    papers = subject_hash({"kind": "merge_papers", "keep": w1, "drop": w2})
    assert papers == hashlib.sha1(b"oa:3|oa:7").hexdigest()


def test_a_reassignment_is_keyed_by_the_row_it_takes() -> None:
    work, author = work_subject(7, None, "T", None), author_subject(2, None, "A")
    line = curated_line(
        "",
        {"kind": "reassign_paper", "work": work, "author": author},
        "namesake",
        {},
    )
    assert line["key"] == "|reassign_paper|" + hashlib.sha1(b"oa:7|oa:2").hexdigest()
    with_target = {**line["payload"], "to": author_subject(9, None, "B")}
    assert subject_hash(with_target) == line["key"].rsplit("|", 1)[1]
