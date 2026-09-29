"""The ORCID Public Data File summaries, reduced to the two tables Rankless reads.

Downloads the summaries tarball into `$EXTERNAL_DATA_ROOT/orcid/raw/` (resumable,
md5-checked), streams it once and writes into `orcid/`:

    names.tsv.zst         orcid, given_names, family_name, credit_name, other_names
                          for every record — the registered-name table
                          `rankless-rs derive-ledger` reads
    public_emails.tsv     orcid, email, primary, verified, last_modified for every
                          public email — the author email lane joins its ORCIDs to it
    summaries.stats.json  record and row counts of the pass

Usage:
    uv run -m pyscripts.orcid_summaries [--root DIR]
"""

import argparse
import hashlib
import html
import json
import re
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET
from dataclasses import astuple, dataclass, fields
from pathlib import Path

import zstandard

from pyscripts.external_data import fetched, source_dir

SOURCE = "orcid"
SUMMARIES_NAME = "ORCID_2025_10_summaries.tar.gz"
SUMMARIES_URL = "https://ndownloader.figshare.com/files/58834837"
SUMMARIES_MD5 = "210edf71f4a2bb44dd33aaa3037b3f17"
NAMES_NAME = "names.tsv.zst"
EMAILS_NAME = "public_emails.tsv"
STATS_NAME = "summaries.stats.json"
EMAIL_TAG = "{http://www.orcid.org/ns/email}email"
MODIFIED_TAG = "{http://www.orcid.org/ns/common}last-modified-date"
# The address element itself; the `<email:emails>` container is in every record.
EMAIL_MARKER = b"<email:email>"
NAME_END = b"</person:name>"
# The element an other name is written in; an empty `other-names` block has none.
OTHER_MARKER = b"<other-name:content>"
STREAM_BUF = 1 << 20
PROGRESS_EVERY = 1_000_000


def _tag(local: str) -> re.Pattern[bytes]:
    return re.compile(rb"<(?:[\w-]+:)?%s>(.*?)</" % local.encode(), re.S)


GIVEN_RE = _tag("given-names")
FAMILY_RE = _tag("family-name")
CREDIT_RE = _tag("credit-name")
OTHER_RE = _tag("content")
OTHER_BLOCK_RE = re.compile(
    rb"<(?:[\w-]+:)?other-names(?:\s[^>]*)?>(.*?)</(?:[\w-]+:)?other-names>", re.S
)


@dataclass(frozen=True)
class Names:
    orcid: str
    given_names: str
    family_name: str
    credit_name: str
    other_names: str


@dataclass(frozen=True)
class PublicEmail:
    orcid: str
    email: str
    primary: bool
    verified: bool
    last_modified: str


@dataclass
class ScanCounts:
    records: int = 0
    named: int = 0
    with_email: int = 0
    emails: int = 0


def verify(path: Path) -> None:
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "md5").hexdigest()
    if digest != SUMMARIES_MD5:
        raise ValueError(f"{path}: md5 {digest} != {SUMMARIES_MD5}")


def _text(m: re.Match[bytes] | None) -> str:
    if m is None:
        return ""
    return " ".join(html.unescape(m.group(1).decode("utf-8", "replace")).split())


def record_names(orcid: str, xml: bytes) -> Names:
    """The name block sits at the record's head, other names right after it; the regexes
    stay off the tens of kilobytes of activity summaries below."""
    end = xml.find(NAME_END)
    head = xml if end < 0 else xml[:end]
    others: list[str] = []
    if OTHER_MARKER in xml:
        block = OTHER_BLOCK_RE.search(xml, max(end, 0))
        others = [_text(m) for m in OTHER_RE.finditer(block.group(1))] if block else []
    return Names(
        orcid,
        _text(GIVEN_RE.search(head)),
        _text(FAMILY_RE.search(head)),
        _text(CREDIT_RE.search(head)),
        "|".join(o for o in others if o),
    )


def record_emails(orcid: str, xml: bytes) -> list[PublicEmail]:
    return [
        PublicEmail(
            orcid,
            address.strip(),
            el.get("primary") == "true",
            el.get("verified") == "true",
            el.findtext(MODIFIED_TAG) or "",
        )
        for el in ET.fromstring(xml).iter(EMAIL_TAG)
        if el.get("visibility") == "public" and (address := el.findtext(EMAIL_TAG))
    ]


def _tsv_line(row: object) -> str:
    return (
        "\t".join(
            str(v).lower() if isinstance(v, bool) else str(v) for v in astuple(row)
        )
        + "\n"
    )


def _header(cls: type) -> str:
    return "\t".join(fl.name for fl in fields(cls)) + "\n"


def scan(tarball: Path, out_dir: Path) -> ScanCounts:
    counts = ScanCounts()
    start = time.monotonic()
    proc = subprocess.Popen(
        ["pigz", "-dc", str(tarball)], stdout=subprocess.PIPE, bufsize=STREAM_BUF
    )
    assert proc.stdout is not None
    cctx = zstandard.ZstdCompressor(level=9)
    with (
        (out_dir / NAMES_NAME).open("wb") as names_raw,
        cctx.stream_writer(names_raw) as names_zst,
        (out_dir / EMAILS_NAME).open("w") as emails,
        tarfile.open(fileobj=proc.stdout, mode="r|", bufsize=STREAM_BUF) as tf,
    ):
        names_zst.write(_header(Names).encode())
        emails.write(_header(PublicEmail))
        for member in tf:
            if not member.isfile() or not member.name.endswith(".xml"):
                continue
            counts.records += 1
            if counts.records % PROGRESS_EVERY == 0:
                print(f"{time.monotonic() - start:7.0f}s {counts}", flush=True)
            orcid = member.name.rsplit("/", 1)[-1].removesuffix(".xml")
            handle = tf.extractfile(member)
            assert handle is not None
            xml = handle.read()
            names = record_names(orcid, xml)
            if names.given_names or names.family_name or names.credit_name:
                counts.named += 1
                names_zst.write(_tsv_line(names).encode())
            if EMAIL_MARKER in xml and (found := record_emails(orcid, xml)):
                counts.with_email += 1
                counts.emails += len(found)
                for e in found:
                    emails.write(_tsv_line(e))
    if proc.wait() != 0:
        raise RuntimeError(f"pigz exited with {proc.returncode}")
    return counts


def main(*, root: Path | None = None) -> None:
    """Download the summaries into the orcid source's `raw/` (if absent) and extract the
    names + public-emails tables (--root overrides $EXTERNAL_DATA_ROOT)."""
    out_dir = source_dir(SOURCE, root)
    tarball = fetched(SOURCE, SUMMARIES_NAME, SUMMARIES_URL, root)
    verify(tarball)
    counts = scan(tarball, out_dir)
    stats = {"source": SUMMARIES_NAME, **counts.__dict__}
    (out_dir / STATS_NAME).write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=None)
    main(root=parser.parse_args().root)
