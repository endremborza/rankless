import random
import time
from io import BytesIO

import requests
from lxml import etree
from tqdm import tqdm

ROOT = "https://www.rankless.org"
# ROOT = "https://alpha.rankless.org"
# ROOT = "http://127.0.0.1:5173"

indices = [
    "",
    "-mini",
    "-entities",
]

urls = [f"{ROOT}/sitemap-index{suff}.xml" for suff in indices]


def url_to_elems(url):
    resp = requests.get(url)
    msg = f"[FAIL] Could not fetch sitemap index (status {resp.status_code if resp else 'N/A'})"
    assert resp.ok, msg
    try:
        return elems(resp.content)
    except Exception as e:
        print("Failed parse", url)
        raise e


def elems(content):
    root = etree.parse(BytesIO(content)).getroot()
    ns = {"ns": root.nsmap[None]} if None in root.nsmap else {}
    return [elem.text for elem in root.findall(".//ns:loc", namespaces=ns)]


def main():
    rand_sample = []
    for url in urls:
        lens = []
        for sitemap_url in tqdm(url_to_elems(url), desc=url):
            sitemap_subs = url_to_elems(sitemap_url)
            rand_sample.append(random.choice(sitemap_subs))
            lens.append(f"{sitemap_url} -> {len(sitemap_subs)}")
            time.sleep(0.5)
        print("\n".join(lens))
    for found_url in tqdm(rand_sample, desc="found"):
        assert requests.get(found_url).ok, found_url
        time.sleep(0.1)


if __name__ == "__main__":
    main()
