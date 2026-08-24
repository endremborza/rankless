"""Fit the world-map asset's projection so a map click inverts to lat/lon.

`country-svg-paths.json` is linear in longitude and latitude (equirectangular
with a stretched parallel); the fit anchors it to per-country medians of
institution coordinates from `$OA_ROOT/entity-csvs/institutions/geo.part-*`.
Writes `src/lib/assets/data/map-projection.json` for the game's guess map.
Re-run only if the map asset itself changes.
"""

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAP_ASSET = Path("src/lib/assets/data/country-svg-paths.json")
OUT_ASSET = Path("src/lib/assets/data/map-projection.json")

MIN_INSTS = 10
MAX_LON_SPREAD = 15.0
MAX_LAT_SPREAD = 12.0
ROBUST_ITERS = 3

_TOKEN = re.compile(r"([MmLlzZ])|(-?(?:\d+\.?\d*|\.\d+))")


@dataclass
class Anchor:
    name: str
    svg_x: float
    svg_y: float
    lat: float
    lon: float


@dataclass
class Fit:
    offset: float
    scale: float
    rms_px: float
    kept: int


def main(*, centroids: str | None = None) -> None:
    """Fit the map projection and write the frontend asset
    (--centroids: precomputed per-country JSON instead of $OA_ROOT CSVs)."""
    cents = (
        json.loads(Path(centroids).read_text()) if centroids else _compute_centroids()
    )
    anchors = _anchors(cents)
    if len(anchors) < 30:
        raise SystemExit(f"only {len(anchors)} usable country anchors; need >= 30")
    fx = _robust_fit([a.lon for a in anchors], [a.svg_x for a in anchors])
    fy = _robust_fit([a.lat for a in anchors], [a.svg_y for a in anchors])
    rms_km = _rms_km(fx, fy, anchors)
    out = {
        "xOffset": round(fx.offset, 4),
        "xPerLon": round(fx.scale, 6),
        "yOffset": round(fy.offset, 4),
        "yPerLat": round(fy.scale, 6),
        "fit": {
            "anchors": len(anchors),
            "keptX": fx.kept,
            "keptY": fy.kept,
            "rmsPxX": round(fx.rms_px, 2),
            "rmsPxY": round(fy.rms_px, 2),
            "rmsKm": round(rms_km),
        },
    }
    OUT_ASSET.write_text(json.dumps(out, indent="\t") + "\n")
    print(f"x = {fx.offset:.2f} + {fx.scale:.4f}*lon (rms {fx.rms_px:.1f}px)")
    print(f"y = {fy.offset:.2f} + {fy.scale:.4f}*lat (rms {fy.rms_px:.1f}px)")
    print(f"anchor rms ~{rms_km:.0f} km over {len(anchors)} countries -> {OUT_ASSET}")


def _compute_centroids() -> list[dict]:
    import pandas as pd

    parts = sorted(
        (Path(os.environ["OA_ROOT"]) / "entity-csvs" / "institutions").glob(
            "geo.part-*.csv.zst"
        )
    )
    if not parts:
        raise SystemExit("no geo CSVs under $OA_ROOT; pass --centroids instead")
    df = pd.concat([pd.read_csv(p) for p in parts])
    df = df.dropna(subset=["latitude", "longitude", "country"])
    grouped = df.groupby("country").agg(
        med_lat=("latitude", "median"),
        med_lon=("longitude", "median"),
        lat_spread=("latitude", lambda s: s.max() - s.min()),
        lon_spread=("longitude", lambda s: s.max() - s.min()),
        n=("latitude", "size"),
    )
    return [{"name": name, **row} for name, row in grouped.to_dict("index").items()]


def _anchors(cents: list[dict]) -> list[Anchor]:
    paths = json.loads(MAP_ASSET.read_text())
    by_name = {c["name"]: c for c in cents}
    anchors = []
    for key, path_list in paths.items():
        c = by_name.get(key)
        if (
            c is None
            or c["n"] < MIN_INSTS
            or c["lon_spread"] > MAX_LON_SPREAD
            or c["lat_spread"] > MAX_LAT_SPREAD
        ):
            continue
        polys = [poly for d in path_list for poly in _parse_polys(d)]
        x, y = _area_centroid(polys)
        if not math.isnan(x):
            anchors.append(Anchor(key, x, y, c["med_lat"], c["med_lon"]))
    return anchors


def _parse_polys(d: str) -> list[list[tuple[float, float]]]:
    polys: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    x = y = sx = sy = 0.0
    cmd = ""
    nums: list[float] = []
    for m in _TOKEN.finditer(d):
        if m.group(1):
            c = m.group(1)
            if c in "zZ":
                if cur:
                    polys.append(cur)
                    cur = []
                x, y = sx, sy
            else:
                cmd = c
            nums = []
            continue
        nums.append(float(m.group(2)))
        if len(nums) < 2:
            continue
        dx, dy = nums
        nums = []
        if cmd in "Mm":
            x, y = (dx, dy) if cmd == "M" else (x + dx, y + dy)
            sx, sy = x, y
            if cur:
                polys.append(cur)
            cur = [(x, y)]
            # implicit lineto pairs after a moveto keep the moveto's frame
            cmd = "L" if cmd == "M" else "l"
        else:
            x, y = (dx, dy) if cmd == "L" else (x + dx, y + dy)
            cur.append((x, y))
    if cur:
        polys.append(cur)
    return polys


def _area_centroid(polys: list[list[tuple[float, float]]]) -> tuple[float, float]:
    cx = cy = total = 0.0
    for poly in polys:
        if len(poly) < 3:
            continue
        a = px = py = 0.0
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            cross = x0 * y1 - x1 * y0
            a += cross
            px += (x0 + x1) * cross
            py += (y0 + y1) * cross
        if abs(a) < 1e-9:
            continue
        w = abs(a) / 2
        cx += (px / (3 * a)) * w
        cy += (py / (3 * a)) * w
        total += w
    return (cx / total, cy / total) if total else (math.nan, math.nan)


def _robust_fit(us: list[float], vs: list[float]) -> Fit:
    keep = list(range(len(us)))
    offset = scale = 0.0
    for _ in range(ROBUST_ITERS):
        offset, scale = _lin_fit([us[i] for i in keep], [vs[i] for i in keep])
        res = {i: vs[i] - (offset + scale * us[i]) for i in keep}
        rms = _rms(list(res.values()))
        keep = [i for i in keep if abs(res[i]) < 2 * rms]
    rms = _rms([vs[i] - (offset + scale * us[i]) for i in keep])
    return Fit(offset, scale, rms, len(keep))


def _lin_fit(us: list[float], vs: list[float]) -> tuple[float, float]:
    n = len(us)
    su, sv = sum(us), sum(vs)
    suu = sum(u * u for u in us)
    suv = sum(u * v for u, v in zip(us, vs))
    scale = (n * suv - su * sv) / (n * suu - su * su)
    return (sv - scale * su) / n, scale


def _rms(res: list[float]) -> float:
    return math.sqrt(sum(r * r for r in res) / len(res))


def _rms_km(fx: Fit, fy: Fit, anchors: list[Anchor]) -> float:
    errs = []
    for a in anchors:
        dlon = (a.svg_x - fx.offset) / fx.scale - a.lon
        dlat = (a.svg_y - fy.offset) / fy.scale - a.lat
        errs.append(
            math.hypot(dlat * 111.0, dlon * 111.0 * math.cos(math.radians(a.lat)))
        )
    return _rms(errs)
