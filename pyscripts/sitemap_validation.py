import time
from io import BytesIO

import requests
from lxml import etree
from tqdm import tqdm

SITEMAP_INDEX_URL = "https://www.rankless.org/sitemap-index.xml"
SITEMAP_INDEX_URL = "http://127.0.0.1:5173/sitemap-index.xml"
SITEMAP_INDEX_URL = "http://127.0.0.1:5173/sitemap-index-mini.xml"
# SITEMAP_INDEX_URL = "https://alpha.rankless.org/sitemap-index.xml"


def elems(content):
    root = etree.parse(BytesIO(content)).getroot()
    ns = {"ns": root.nsmap[None]} if None in root.nsmap else {}
    return [elem.text for elem in root.findall(".//ns:loc", namespaces=ns)]


def main():
    index_resp = requests.get(SITEMAP_INDEX_URL)
    assert (
        index_resp.ok
    ), f"[FAIL] Could not fetch sitemap index (status {index_resp.status_code if index_resp else 'N/A'})"

    lens = []
    for sitemap_url in tqdm(elems(index_resp.content)):
        resp = requests.get(sitemap_url)
        assert resp.ok, sitemap_url
        lens.append(f"{sitemap_url} -> {len(elems(resp.content))}")
        time.sleep(0.6)
    print("\n".join(lens))


if __name__ == "__main__":
    main()
