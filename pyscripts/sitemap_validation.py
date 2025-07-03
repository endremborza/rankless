import random
import time
from io import BytesIO

import requests
from lxml import etree
from tqdm import tqdm

ROOT = "https://www.rankless.org"
ROOT = "https://alpha.rankless.org"
# ROOT = "http://127.0.0.1:5173"

indices = ["", "-mini", "-entities"]
indices = ["-mini", "-entities"]

urls = [f"{ROOT}/sitemap-index{suff}.xml" for suff in indices]


def elems(content):
    root = etree.parse(BytesIO(content)).getroot()
    ns = {"ns": root.nsmap[None]} if None in root.nsmap else {}
    return [elem.text for elem in root.findall(".//ns:loc", namespaces=ns)]


def main():
    rand_sample = []
    for url in urls:
        index_resp = requests.get(url)
        assert (
            index_resp.ok
        ), f"[FAIL] Could not fetch sitemap index (status {index_resp.status_code if index_resp else 'N/A'})"

        lens = []
        for sitemap_url in tqdm(elems(index_resp.content), desc=url):
            resp = requests.get(sitemap_url)
            assert resp.ok, sitemap_url
            sitemap_subs = elems(resp.content)
            rand_sample.append(random.choice(sitemap_subs))
            lens.append(f"{sitemap_url} -> {len(sitemap_subs)}")
            time.sleep(0.5)
        print("\n".join(lens))
    for found_url in tqdm(rand_sample, desc="found"):
        assert requests.get(found_url).ok, found_url
        time.sleep(0.1)


if __name__ == "__main__":
    main()
