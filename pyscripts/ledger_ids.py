"""Canonical forms of the two external identifiers the ledger joins on.

Mirror of src/lib/utils/identifiers.ts (the writer of the stored forms) and of
canonical_doi / normalize_orcid in rankless_rs/src/user_ledger.rs (the pipeline side).
"""

import re

_DOI_PREFIX = re.compile(r"^https?://(dx\.)?doi\.org/", re.I)
_ORCID_PREFIX = re.compile(r"^https?://(www\.)?orcid\.org/", re.I)


def canonical_doi(doi: str) -> str:
    return _DOI_PREFIX.sub("", doi.strip()).lower()


def normalize_orcid(s: str) -> str:
    return _ORCID_PREFIX.sub("", s.strip()).upper()
