import argparse
import subprocess
import sys
from pathlib import Path

import requests
from tqdm import tqdm

from .cache_prompting import BatchRequester, RTC, SIDC

DEV_SERVER = "http://127.0.0.1:5173"
DEFAULT_OUT = Path("svg-exports")
DEFAULT_W, DEFAULT_H, DEFAULT_DPI = 1200, 630, 512


def fetch_svg(root_type: str, semantic_id: str) -> bytes:
    url = f"{DEV_SERVER}/pic/{root_type}/{semantic_id}/breakdown.svg"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content


def svg_to_png(svg_bytes: bytes, out_path: Path, w: int, h: int, dpi: int) -> None:
    subprocess.run(
        ["rsvg-convert", "-o", str(out_path), "-w", str(w), "-h", str(h), "-d", str(dpi), "-p", str(dpi)],
        input=svg_bytes,
        check=True,
    )


def export_entity(root_type: str, semantic_id: str, out_dir: Path, w: int, h: int, dpi: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_bytes = fetch_svg(root_type, semantic_id)
    out_path = out_dir / f"{root_type}-{semantic_id}.png"
    svg_to_png(svg_bytes, out_path, w, h, dpi)
    print(f"saved {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export entity breakdown SVGs to PNG")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--entity",
        metavar="TYPE/SLUG",
        help="Single entity, e.g. institutions/budapesti-corvinus-egyetem",
    )
    mode.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="Export top N entities by cut_basis from BatchRequester",
    )

    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--width", type=int, default=DEFAULT_W)
    parser.add_argument("--height", type=int, default=DEFAULT_H)
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--min-citations", type=int, default=100_000)

    args = parser.parse_args()

    if args.entity:
        parts = args.entity.split("/", 1)
        if len(parts) != 2:
            print("--entity must be TYPE/SLUG, e.g. institutions/some-university")
            sys.exit(1)
        root_type, semantic_id = parts
        export_entity(root_type, semantic_id, args.out_dir, args.width, args.height, args.dpi)
    else:
        br = BatchRequester(min_citations=args.min_citations)
        sample = br.urled_sample.head(args.top)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for _, row in tqdm(sample.iterrows(), total=len(sample)):
            rt, sid = row[RTC], row[SIDC]
            try:
                svg_bytes = fetch_svg(rt, sid)
                svg_to_png(svg_bytes, args.out_dir / f"{rt}-{sid}.png", args.width, args.height, args.dpi)
            except Exception as e:
                print(f"failed {rt}/{sid}: {e}")


if __name__ == "__main__":
    main()
