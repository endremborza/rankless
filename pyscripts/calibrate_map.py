"""Fit the world-map asset's projection so lat/lon lands on the drawn coast.

`country-svg-paths.json` is a Robinson map (its parallels shorten and crowd
toward the poles), so the fit is Robinson's tabulated parallel length and
spacing with a scale and offset per axis, anchored on coastline landmarks: an
extreme vertex of a country's mainland polygon (its westernmost, northernmost,
...) against the landmark's known coordinates. Writes
`src/lib/assets/data/map-projection.json`, read by `src/lib/utils/geo.ts`.
Re-run only if the map asset itself changes.
"""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

MAP_ASSET = Path("src/lib/assets/data/country-svg-paths.json")
OUT_ASSET = Path("src/lib/assets/data/map-projection.json")

ROBUST_ITERS = 4
MIN_RESIDUAL_PX = 3.0

# Robinson's parallel length and distance from the equator per 5° of latitude.
PARALLEL_LENGTH = [
    1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427, 0.9216, 0.8962,
    0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322,
]  # fmt: skip
PARALLEL_DISTANCE = [
    0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340, 0.4958, 0.5571,
    0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0000,
]  # fmt: skip

# (country key in the asset, extreme of its largest polygon, lat, lon): the
# vertex that is the country's westernmost (minx), easternmost (maxx),
# northernmost (miny) or southernmost (maxy) point of the mainland.
LANDMARKS = [
    ("PT", "minx", 38.78, -9.50),
    ("ES", "maxy", 36.01, -5.61),
    ("ES", "minx", 43.05, -9.29),
    ("FR", "minx", 48.41, -4.79),
    ("GB", "miny", 58.67, -3.37),
    ("GB", "maxy", 49.96, -5.20),
    ("IE", "minx", 52.12, -10.48),
    ("IE", "miny", 55.38, -7.37),
    ("IE", "maxy", 51.43, -9.83),
    ("NO", "maxy", 57.98, 7.05),
    ("IT", "maxy", 37.92, 15.65),
    ("GR", "maxy", 36.39, 22.48),
    ("DK", "miny", 57.75, 10.62),
    ("SE", "maxy", 55.34, 13.36),
    ("FI", "maxy", 59.81, 22.95),
    ("IS", "minx", 65.50, -24.53),
    ("IS", "maxx", 65.08, -13.50),
    ("IS", "miny", 66.53, -16.20),
    ("IS", "maxy", 63.40, -18.70),
    ("AU", "minx", -26.15, 113.15),
    ("AU", "maxx", -28.64, 153.64),
    ("AU", "miny", -10.69, 142.53),
    ("AU", "maxy", -39.14, 146.37),
    ("ZA", "maxy", -34.83, 20.00),
    ("CL", "maxy", -53.90, -71.30),
    ("BR", "maxx", -7.15, -34.79),
    ("PE", "minx", -4.68, -81.33),
    ("US", "minx", 48.16, -124.73),
    ("US", "maxx", 44.82, -66.95),
    ("US", "maxy", 25.12, -81.09),
    ("US", "miny", 49.38, -95.15),
    ("CA", "maxy", 41.91, -82.51),
    ("MX", "minx", 27.85, -115.08),
    ("MX", "maxy", 14.53, -92.23),
    ("IN", "maxy", 8.08, 77.55),
    ("IN", "minx", 23.70, 68.10),
    ("LK", "maxy", 5.92, 80.59),
    ("LK", "miny", 9.83, 80.25),
    ("MG", "miny", -11.95, 49.26),
    ("MG", "maxy", -25.60, 45.17),
    ("TW", "maxy", 21.90, 120.85),
    ("TW", "miny", 25.30, 121.53),
    ("SN", "minx", 14.74, -17.53),
    ("TN", "miny", 37.35, 9.74),
    ("GL", "miny", 83.65, -33.40),
    ("GL", "maxy", 59.78, -43.93),
    ("NZ", "maxy", -46.67, 169.00),
    ("JP", "miny", 41.55, 140.91),
    ("KR", "maxy", 34.30, 126.50),
    ("EG", "maxx", 22.00, 36.90),
]

# Coastal cities that must land on their country once fitted.
COAST_CHECK = [
    ("US", "Seattle", 47.61, -122.33),
    ("US", "San Francisco", 37.77, -122.42),
    ("US", "Miami", 25.76, -80.19),
    ("CA", "Vancouver", 49.28, -123.12),
    ("JP", "Tokyo", 35.68, 139.69),
    ("AU", "Perth", -31.95, 115.86),
    ("ZA", "Cape Town", -33.93, 18.42),
    ("IS", "Reykjavik", 64.15, -21.94),
    ("NZ", "Auckland", -36.85, 174.76),
    ("CL", "Santiago", -33.45, -70.67),
]

_TOKEN = re.compile(r"([MmLlzZ])|(-?(?:\d+\.?\d*|\.\d+))")
_EXTREME = {
    "minx": lambda p: p[0],
    "maxx": lambda p: -p[0],
    "miny": lambda p: p[1],
    "maxy": lambda p: -p[1],
}

Point = tuple[float, float]


@dataclass
class Fit:
    offset: float
    scale: float
    rms_px: float
    kept: int


def main() -> None:
    """Fit the map projection and write the frontend asset."""
    paths = json.loads(MAP_ASSET.read_text())
    anchors = [
        (lat, lon, *_extreme_vertex(paths[country], ext))
        for country, ext, lat, lon in LANDMARKS
    ]
    fx = _robust_fit(
        [parallel_length(lat) * lon for lat, lon, _, _ in anchors],
        [x for _, _, x, _ in anchors],
    )
    fy = _robust_fit(
        [parallel_distance(lat) for lat, _, _, _ in anchors],
        [y for _, _, _, y in anchors],
    )
    out = {
        "projection": "robinson",
        "xOffset": round(fx.offset, 2),
        "xScale": round(fx.scale, 4),
        "yOffset": round(fy.offset, 2),
        "yScale": round(fy.scale, 3),
        "fit": {
            "landmarks": len(anchors),
            "keptX": fx.kept,
            "keptY": fy.kept,
            "rmsPxX": round(fx.rms_px, 1),
            "rmsPxY": round(fy.rms_px, 1),
        },
    }
    OUT_ASSET.write_text(json.dumps(out, indent="\t") + "\n")
    print(
        f"x = {fx.offset:.2f} + {fx.scale:.4f} * length(lat) * lon (rms {fx.rms_px:.1f}px)"
    )
    print(
        f"y = {fy.offset:.2f} + {fy.scale:.3f} * distance(lat) (rms {fy.rms_px:.1f}px)"
    )
    for country, city, lat, lon in COAST_CHECK:
        pt = (
            fx.offset + fx.scale * parallel_length(lat) * lon,
            fy.offset + fy.scale * parallel_distance(lat),
        )
        on_land = any(_inside(pt, poly) for poly in _polygons(paths[country]))
        print(f"  {city}: {'on land' if on_land else 'OFFSHORE'}")
    print(f"-> {OUT_ASSET}")


def parallel_length(lat: float) -> float:
    return _tabulated(PARALLEL_LENGTH, lat)


def parallel_distance(lat: float) -> float:
    return math.copysign(_tabulated(PARALLEL_DISTANCE, lat), lat)


def _tabulated(table: list[float], lat: float) -> float:
    t = min(abs(lat), 90.0) / 5
    i = min(int(t), len(table) - 2)
    return table[i] + (table[i + 1] - table[i]) * (t - i)


def _extreme_vertex(path_list: list[str], ext: str) -> Point:
    polys = sorted(_polygons(path_list), key=_area, reverse=True)
    return min(polys[0], key=_EXTREME[ext])


def _polygons(path_list: list[str]) -> list[list[Point]]:
    return [poly for d in path_list for poly in _parse_polys(d) if len(poly) > 2]


def _parse_polys(d: str) -> list[list[Point]]:
    polys: list[list[Point]] = []
    cur: list[Point] = []
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


def _area(poly: list[Point]) -> float:
    return (
        abs(
            sum(
                x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])
            )
        )
        / 2
    )


def _inside(pt: Point, poly: list[Point]) -> bool:
    px, py = pt
    ins = False
    j = len(poly) - 1
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[j]
        if (y0 > py) != (y1 > py) and px < (x1 - x0) * (py - y0) / (y1 - y0) + x0:
            ins = not ins
        j = i
    return ins


def _robust_fit(us: list[float], vs: list[float]) -> Fit:
    keep = list(range(len(us)))
    offset = scale = 0.0
    for _ in range(ROBUST_ITERS):
        offset, scale = _lin_fit([us[i] for i in keep], [vs[i] for i in keep])
        res = {i: vs[i] - (offset + scale * us[i]) for i in keep}
        rms = _rms(list(res.values()))
        keep = [i for i in keep if abs(res[i]) < max(2 * rms, MIN_RESIDUAL_PX)]
    offset, scale = _lin_fit([us[i] for i in keep], [vs[i] for i in keep])
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
