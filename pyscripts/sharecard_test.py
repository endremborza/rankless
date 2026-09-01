"""Automated checks for the Rankless social share-card (Open Graph / Twitter card).

Covers Phase 0 (what's actually served), most of Phase 3 (acceptance criteria), and the
Phase 2 rasterize control. Visual confirmation on real platforms (Phase 1) stays manual:
the script fetches as a social crawler, evaluates the meta tags + the og:image, and prints
the validator links to click through. Optionally runs the live Facebook scrape API.

    uv run -m pyscripts.sharecard_test https://rankless.org/institutions/<slug>
    uv run -m pyscripts.sharecard_test <url> --rasterize        # Phase 2 control PNG
    uv run -m pyscripts.sharecard_test <url> --fb-token <token> # live FB scrape

Exits non-zero if any check FAILs, so it doubles as a pre-launch gate.
See docs/sharecard-render-test.md.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests

CARD_W, CARD_H = 1200, 630
DIM_TOL = 0.15
MAX_BYTES = 5 * 1024 * 1024
MAX_LOAD_S = 2.0
RASTER_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/webp")
RECOMMENDED = [
    "og:image:width",
    "og:image:height",
    "og:image:type",
    "og:url",
    "og:description",
    "twitter:title",
    "twitter:description",
    "twitter:image",
]
CRAWLER_UAS = {
    "facebook": (
        "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
    ),
    "twitter": "Twitterbot/1.0",
    "linkedin": "LinkedInBot/1.0 (compatible; Mozilla/5.0; +http://www.linkedin.com)",
    "browser": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
SYMBOL = {PASS: "✓", WARN: "!", FAIL: "✗"}
COLOR = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m"}
RESET = "\033[0m"


@dataclass
class ImageInfo:
    url: str
    ok: bool
    content_type: str = ""
    byte_size: int = 0
    width: int | None = None
    height: int | None = None
    load_seconds: float = 0.0
    error: str = ""


@dataclass
class Check:
    name: str
    status: str
    detail: str


def attr(tag: str, name: str) -> str | None:
    m = re.search(rf'{name}\s*=\s*"([^"]*)"', tag, re.I) or re.search(
        rf"{name}\s*=\s*'([^']*)'", tag, re.I
    )
    return m.group(1) if m else None


def parse_meta(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        key = attr(tag, "property") or attr(tag, "name")
        if not key:
            continue
        key = key.lower()
        if key.startswith(("og:", "twitter:")) or key == "description":
            content = attr(tag, "content")
            if content is not None:
                out[key] = content
    return out


def length_px(v: str | None) -> int | None:
    if not v:
        return None
    m = re.match(r"\s*([\d.]+)", v)
    return int(float(m.group(1))) if m else None


def svg_dimensions(data: bytes) -> tuple[int | None, int | None]:
    text = data.decode("utf-8", "ignore")
    m = re.search(r"<svg\b[^>]*>", text, re.I)
    if not m:
        return (None, None)
    tag = m.group(0)
    w, h = length_px(attr(tag, "width")), length_px(attr(tag, "height"))
    if w and h:
        return (w, h)
    vb = attr(tag, "viewBox")
    if vb:
        parts = re.split(r"[\s,]+", vb.strip())
        if len(parts) == 4:
            try:
                return (int(float(parts[2])), int(float(parts[3])))
            except ValueError:
                pass
    return (w, h)


def jpeg_dimensions(data: bytes) -> tuple[int | None, int | None]:
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = int.from_bytes(data[i + 5 : i + 7], "big")
            w = int.from_bytes(data[i + 7 : i + 9], "big")
            return (w, h)
        i += 2 + int.from_bytes(data[i + 2 : i + 4], "big")
    return (None, None)


def image_dimensions(data: bytes, content_type: str) -> tuple[int | None, int | None]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return (
            int.from_bytes(data[16:20], "big"),
            int.from_bytes(data[20:24], "big"),
        )
    if data[:2] == b"\xff\xd8":
        return jpeg_dimensions(data)
    if "svg" in content_type or b"<svg" in data[:512]:
        return svg_dimensions(data)
    return (None, None)


def fetch_html(url: str, ua: str) -> str:
    r = requests.get(url, headers={"User-Agent": ua}, timeout=20)
    r.raise_for_status()
    return r.text


def probe_image(url: str, ua: str) -> ImageInfo:
    try:
        t0 = time.perf_counter()
        r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
        dt = time.perf_counter() - t0
        r.raise_for_status()
    except requests.RequestException as e:
        return ImageInfo(url=url, ok=False, error=str(e))
    ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    data = r.content
    w, h = image_dimensions(data, ctype)
    return ImageInfo(url, True, ctype, len(data), w, h, dt)


def run_checks(meta: dict[str, str], img: ImageInfo) -> list[Check]:
    checks: list[Check] = []

    og_image = meta.get("og:image")
    checks.append(
        Check("og:image present", PASS, og_image)
        if og_image
        else Check("og:image present", FAIL, "no og:image meta tag found")
    )
    if not img.ok:
        checks.append(Check("og:image fetchable", FAIL, img.error or "no og:image"))
        return checks
    checks.append(
        Check(
            "og:image fetchable",
            PASS,
            f"{img.byte_size / 1024:.0f} KiB in {img.load_seconds:.2f}s",
        )
    )

    if img.content_type in RASTER_TYPES:
        checks.append(Check("og:image is raster", PASS, img.content_type))
    elif "svg" in img.content_type:
        checks.append(
            Check(
                "og:image is raster",
                FAIL,
                f"{img.content_type} — SVG is NOT rendered by X/LinkedIn/Facebook/"
                "Slack; the card shows blank. Serve a PNG/JPEG instead.",
            )
        )
    else:
        checks.append(
            Check("og:image is raster", WARN, f"unexpected type {img.content_type!r}")
        )

    card = meta.get("twitter:card", "")
    if card == "summary_large_image":
        checks.append(Check("twitter:card", PASS, card))
    elif card == "summary":
        checks.append(
            Check(
                "twitter:card",
                WARN,
                "summary → small square; use summary_large_image for a banner",
            )
        )
    else:
        checks.append(Check("twitter:card", WARN, f"missing/unknown ({card!r})"))

    if img.width and img.height:
        ok = (
            abs(img.width - CARD_W) <= CARD_W * DIM_TOL
            and abs(img.height - CARD_H) <= CARD_H * DIM_TOL
        )
        checks.append(
            Check(
                "dimensions ~1200x630",
                PASS if ok else WARN,
                f"{img.width}x{img.height}",
            )
        )
    else:
        checks.append(
            Check("dimensions ~1200x630", WARN, "could not read image dimensions")
        )

    checks.append(
        Check(
            "size < 5 MiB",
            PASS if img.byte_size <= MAX_BYTES else FAIL,
            f"{img.byte_size / 1024 / 1024:.2f} MiB",
        )
    )
    checks.append(
        Check(
            "loads < 2s",
            PASS if img.load_seconds <= MAX_LOAD_S else WARN,
            f"{img.load_seconds:.2f}s",
        )
    )

    missing = [k for k in RECOMMENDED if k not in meta]
    checks.append(
        Check("recommended tags", WARN, "missing: " + ", ".join(missing))
        if missing
        else Check("recommended tags", PASS, "all present")
    )
    return checks


def rasterize(og_image_url: str, ua: str, out: Path, w: int, h: int) -> None:
    if not shutil.which("rsvg-convert"):
        sys.exit(
            "rsvg-convert not found. Install: "
            "brew install librsvg / apt-get install librsvg2-bin"
        )
    data = requests.get(og_image_url, headers={"User-Agent": ua}, timeout=30).content
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        out.write_bytes(data)
        print(f"og:image is already PNG; saved as-is -> {out}")
        return
    subprocess.run(
        ["rsvg-convert", "-w", str(w), "-h", str(h), "-o", str(out)],
        input=data,
        check=True,
    )
    png = out.read_bytes()
    pw, ph = image_dimensions(png, "image/png")
    print(
        f"rasterized -> {out} ({pw}x{ph}, {len(png) / 1024:.0f} KiB). "
        "Host this publicly + point og:image at it to run the Phase 2 control."
    )


def fb_scrape(url: str, token: str) -> None:
    r = requests.get(
        "https://graph.facebook.com/v19.0/",
        params={
            "id": url,
            "fields": "image,title,description",
            "scrape": "true",
            "access_token": token,
        },
        timeout=30,
    )
    print("Facebook scrape result:")
    print(r.text)


def validator_links(url: str) -> list[tuple[str, str]]:
    q = quote(url, safe="")
    return [
        ("LinkedIn", f"https://www.linkedin.com/post-inspector/inspect/{q}"),
        ("Facebook/Slack", f"https://developers.facebook.com/tools/debug/?q={q}"),
        ("opengraph.xyz", f"https://www.opengraph.xyz/url/{q}"),
        ("metatags.io", "https://metatags.io/"),
        ("X/Twitter", "paste URL into the compose box (Card Validator retired)"),
    ]


def colorize(status: str, use_color: bool) -> str:
    label = f"{SYMBOL[status]} {status}"
    return f"{COLOR[status]}{label}{RESET}" if use_color else label


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated Rankless share-card (OG/Twitter) checks."
    )
    parser.add_argument(
        "url", help="entity page URL, e.g. https://rankless.org/institutions/<slug>"
    )
    parser.add_argument(
        "--ua",
        choices=sorted(CRAWLER_UAS),
        default="facebook",
        help="user-agent to fetch as (simulate a social crawler); default: facebook",
    )
    parser.add_argument(
        "--rasterize",
        action="store_true",
        help="Phase 2 control: convert og:image to a 1200x630 PNG via rsvg-convert",
    )
    parser.add_argument("--out", type=Path, default=Path("card.png"))
    parser.add_argument("--width", type=int, default=CARD_W)
    parser.add_argument("--height", type=int, default=CARD_H)
    parser.add_argument(
        "--fb-token", help="optional Graph API token to run the live Facebook scrape"
    )
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()

    use_color = sys.stdout.isatty() and not args.no_color
    ua = CRAWLER_UAS[args.ua]

    print(f"Fetching {args.url}\n  as: {ua}\n")
    meta = parse_meta(fetch_html(args.url, ua))

    print("Meta tags (og:/twitter:):")
    for k in sorted(meta):
        print(f"  {k} = {meta[k]}")
    print()

    og_image = meta.get("og:image", "")
    img = (
        probe_image(og_image, ua)
        if og_image
        else ImageInfo("", False, error="no og:image")
    )

    checks = run_checks(meta, img)
    print("Checks:")
    failed = False
    for c in checks:
        failed = failed or c.status == FAIL
        print(f"  {colorize(c.status, use_color)}  {c.name}: {c.detail}")
    print()

    if args.rasterize and og_image:
        rasterize(og_image, ua, args.out, args.width, args.height)
        print()

    if args.fb_token:
        fb_scrape(args.url, args.fb_token)
        print()

    print("Manual visual confirmation (Phase 1) — open these:")
    for name, link in validator_links(args.url):
        print(f"  {name}: {link}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
