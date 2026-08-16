"""Python side of the ledger's identifier and subject-key rules.

Mirror of src/lib/utils/identifiers.ts (the writer of the stored forms),
src/lib/server/ledger-hash.ts (the subject keys events are addressed by),
src/lib/types/ledger.ts (subject shape) and canonical_doi / normalize_orcid in
rankless_rs/src/user_ledger.rs (the pipeline side). Anything writing ledger rows
from Python builds them here, so the four sides cannot drift apart.
"""

import hashlib
import re
from typing import Any

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


def author_subject(oa_id: int, orcid: str | None, display_name: str) -> dict[str, Any]:
    return {
        "oa_id": oa_id,
        "orcid": orcid,
        "dm_id_at_creation": None,
        "semantic_id_at_creation": None,
        "run_id_at_creation": None,
        "display_snapshot": {"display_name": display_name},
    }


def author_canonical_key(subject: dict[str, Any]) -> str:
    if subject.get("orcid"):
        return f"orcid:{subject['orcid']}"
    return f"oa:{subject['oa_id']}"


def merge_subject_hash(keep: dict[str, Any], drop: dict[str, Any]) -> str:
    keys = sorted([author_canonical_key(keep), author_canonical_key(drop)])
    return hashlib.sha1("|".join(keys).encode()).hexdigest()
