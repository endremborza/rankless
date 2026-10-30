import tarfile
from pathlib import Path

import pytest
import zstandard

from pyscripts import external_data
from pyscripts.orcid_summaries import (
    EMAILS_NAME,
    NAMES_NAME,
    Names,
    record_emails,
    record_names,
    scan,
)

RECORD = b"""<?xml version="1.0"?>
<record:record xmlns:record="http://www.orcid.org/ns/record" xmlns:person="http://www.orcid.org/ns/person"
  xmlns:personal-details="http://www.orcid.org/ns/personal-details" xmlns:other-name="http://www.orcid.org/ns/other-name"
  xmlns:common="http://www.orcid.org/ns/common" xmlns:email="http://www.orcid.org/ns/email">
<person:person>
<person:name visibility="public">
  <personal-details:given-names>Anne</personal-details:given-names>
  <personal-details:family-name>Maa&#223; &amp; Co</personal-details:family-name>
  <personal-details:credit-name>A. Maass</personal-details:credit-name>
</person:name>
<other-name:other-names path="/0000-0001-2345-6789/other-names">
  <other-name:other-name put-code="1" visibility="public" path="/0000-0001-2345-6789/other-names/1" display-index="1">
    <common:source><common:source-name>Anne Maass</common:source-name></common:source>
    <other-name:content>Anne M.</other-name:content>
  </other-name:other-name>
  <other-name:other-name put-code="2" visibility="public" path="/0000-0001-2345-6789/other-names/2" display-index="2">
    <other-name:content>A.\tMaass</other-name:content>
  </other-name:other-name>
</other-name:other-names>
<person:biography><personal-details:content>given-names in a biography must not count</personal-details:content></person:biography>
<email:emails>
  <email:email visibility="public" primary="true" verified="true">
    <common:last-modified-date>2020-01-01</common:last-modified-date>
    <email:email>a@b.c</email:email>
  </email:email>
  <email:email visibility="limited" primary="false" verified="false">
    <email:email>hidden@b.c</email:email>
  </email:email>
</email:emails>
</person:person>
</record:record>"""

ORCID = "0000-0001-2345-6789"


def test_names_come_from_the_name_block_and_other_names() -> None:
    assert record_names(ORCID, RECORD) == Names(
        ORCID, "Anne", "Maaß & Co", "A. Maass", "Anne M.|A. Maass"
    )


def test_a_record_without_names_or_other_names_is_empty() -> None:
    bare = (
        b'<record:record><person:person><other-name:other-names path="/x/other-names"/>'
        b"<email:emails/></person:person></record:record>"
    )
    assert record_names(ORCID, bare) == Names(ORCID, "", "", "", "")


def test_only_public_emails_are_kept() -> None:
    (email,) = record_emails(ORCID, RECORD)
    assert (email.email, email.primary, email.verified, email.last_modified) == (
        "a@b.c",
        True,
        True,
        "2020-01-01",
    )


def test_regen_root_defaults_to_the_repo_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(external_data.EXTERNAL_REGEN_ROOT, raising=False)
    assert external_data.REGEN.path() == Path(external_data.DEFAULT_EXTERNAL_REGEN_ROOT)
    monkeypatch.setenv(external_data.EXTERNAL_REGEN_ROOT, "/elsewhere")
    assert external_data.REGEN.path() == Path("/elsewhere")
    assert external_data.REGEN.path(Path("/given")) == Path("/given")


def _summaries(tmp_path: Path, torn: bool) -> Path:
    xml = tmp_path / f"{ORCID}.xml"
    xml.write_bytes(RECORD)
    tarball = tmp_path / "summaries.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(xml, arcname=f"summaries/789/{ORCID}.xml")
    if torn:
        tarball.write_bytes(tarball.read_bytes()[:-4])
    return tarball


def test_a_failed_scan_keeps_the_previous_tables(tmp_path: Path) -> None:
    out = tmp_path / "orcid"
    out.mkdir()
    (out / NAMES_NAME).write_bytes(b"previous")
    with pytest.raises(RuntimeError, match="pigz"):
        scan(_summaries(tmp_path, torn=True), out)
    assert (out / NAMES_NAME).read_bytes() == b"previous"

    counts = scan(_summaries(tmp_path, torn=False), out)
    assert (counts.records, counts.named, counts.emails) == (1, 1, 1)
    names = zstandard.ZstdDecompressor().decompress(
        (out / NAMES_NAME).read_bytes(), max_output_size=1 << 20
    )
    assert ORCID.encode() in names
    assert sorted(p.name for p in out.iterdir()) == sorted([NAMES_NAME, EMAILS_NAME])
