from pathlib import Path

import pytest

from pyscripts import external_data
from pyscripts.orcid_summaries import Names, record_emails, record_names

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


def test_external_root_defaults_to_the_repo_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(external_data.EXTERNAL_DATA_ROOT, raising=False)
    assert external_data.root() == Path(external_data.DEFAULT_EXTERNAL_DATA_ROOT)
    monkeypatch.setenv(external_data.EXTERNAL_DATA_ROOT, "/elsewhere")
    assert external_data.root() == Path("/elsewhere")
    assert external_data.root(Path("/given")) == Path("/given")
