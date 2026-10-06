"""Python side of the ledger's identifier and subject-key rules.

Mirror of src/lib/utils/identifiers.ts (the writer of the stored forms),
src/lib/server/ledger-hash.ts (the subject keys events are addressed by) and
canonical_doi / normalize_orcid in rankless_rs/src/user_ledger.rs (the pipeline
side); the subject shapes are generated from that file. Anything writing ledger
rows from Python builds them here, so the sides cannot drift apart.
"""

import hashlib
import re
from typing import Any

from wire.rankless_rs.user_ledger import AuthorSubject, EventPayload, WorkSubject

_DOI_PREFIX = re.compile(r"^https?://(dx\.)?doi\.org/", re.I)
_ORCID_PREFIX = re.compile(r"^https?://(www\.)?orcid\.org/", re.I)


def canonical_doi(doi: str) -> str:
    return _DOI_PREFIX.sub("", doi.strip()).lower()


def normalize_orcid(s: str) -> str:
    return _ORCID_PREFIX.sub("", s.strip()).upper()


def oa_numeric(oa_id: str) -> int:
    return int(oa_id.lstrip("AW"))


def logical_key(orcid: str, kind: str, subject_hash: str) -> str:
    """Merge-stable id of an event — what the pipeline and the manifests reference,
    since event_id is renumbered by a DB merge."""
    return f"{orcid}|{kind}|{subject_hash}"


def author_subject(oa_id: int, orcid: str | None, display_name: str) -> AuthorSubject:
    return {
        "oa_id": oa_id,
        "orcid": orcid,
        "dm_id_at_creation": None,
        "semantic_id_at_creation": None,
        "run_id_at_creation": None,
        "display_snapshot": {"display_name": display_name},
    }


def work_subject(
    oa_id: int | None, doi: str | None, title: str, year: int | None
) -> WorkSubject:
    return {
        "oa_id": oa_id,
        "doi": canonical_doi(doi) if doi else None,
        "dm_id_at_creation": None,
        "semantic_id_at_creation": None,
        "run_id_at_creation": None,
        "display_snapshot": {"title": title, "year": year},
    }


def work_canonical_key(subject: WorkSubject) -> str:
    if subject["oa_id"] is not None:
        return f"oa:{subject['oa_id']}"
    doi = subject["doi"]
    assert doi is not None, "a work subject names an oa_id or a doi"
    return f"doi:{doi.lower()}"


def author_canonical_key(subject: AuthorSubject) -> str:
    if subject.get("orcid"):
        return f"orcid:{subject['orcid']}"
    return f"oa:{subject['oa_id']}"


def subject_hash(payload: EventPayload) -> str:
    """Subject key of an event the pipeline reads, as `subjectHash` builds it."""
    match payload:
        case {"kind": "disown_paper" | "claim_paper", "work": work}:
            keys = [work_canonical_key(work)]
        case {"kind": "merge_papers", "keep": keep, "drop": drop}:
            keys = sorted([work_canonical_key(keep), work_canonical_key(drop)])
        case {"kind": "merge_authors", "keep": keep, "drop": drop}:
            keys = sorted([author_canonical_key(keep), author_canonical_key(drop)])
        case {"kind": "strip_orcid" | "name_author", "author": author}:
            keys = [author_canonical_key(author)]
        case {"kind": "reassign_paper", "work": work, "author": author}:
            keys = [work_canonical_key(work), author_canonical_key(author)]
        case _:
            raise ValueError(f"no subject key for a {payload['kind']} event")
    return hashlib.sha1("|".join(keys).encode()).hexdigest()


def curated_line(
    orcid: str, payload: EventPayload, reason: str, evidence: dict[str, Any]
) -> dict[str, Any]:
    """One line of the curated ledger; `orcid` is empty for an event that names records only."""
    kind = payload["kind"]
    return {
        "key": logical_key(orcid, kind, subject_hash(payload)),
        "orcid": orcid,
        "kind": kind,
        "source": "curated",
        "reason": reason,
        "payload": payload,
        "evidence": evidence,
    }
