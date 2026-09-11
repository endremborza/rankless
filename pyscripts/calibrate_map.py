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
    ("Portugal", "minx", 38.78, -9.50),
    ("Spain", "maxy", 36.01, -5.61),
    ("Spain", "minx", 43.05, -9.29),
    ("France", "minx", 48.41, -4.79),
    ("United Kingdom", "miny", 58.67, -3.37),
    ("United Kingdom", "maxy", 49.96, -5.20),
    ("Ireland", "minx", 52.12, -10.48),
    ("Ireland", "miny", 55.38, -7.37),
    ("Ireland", "maxy", 51.43, -9.83),
    ("Norway", "maxy", 57.98, 7.05),
    ("Italy", "maxy", 37.92, 15.65),
    ("Greece", "maxy", 36.39, 22.48),
    ("Denmark", "miny", 57.75, 10.62),
    ("Sweden", "maxy", 55.34, 13.36),
    ("Finland", "maxy", 59.81, 22.95),
    ("Iceland", "minx", 65.50, -24.53),
    ("Iceland", "maxx", 65.08, -13.50),
    ("Iceland", "miny", 66.53, -16.20),
    ("Iceland", "maxy", 63.40, -18.70),
    ("Australia", "minx", -26.15, 113.15),
    ("Australia", "maxx", -28.64, 153.64),
    ("Australia", "miny", -10.69, 142.53),
    ("Australia", "maxy", -39.14, 146.37),
    ("South Africa", "maxy", -34.83, 20.00),
    ("Chile", "maxy", -53.90, -71.30),
    ("Brazil", "maxx", -7.15, -34.79),
    ("Peru", "minx", -4.68, -81.33),
    ("United States", "minx", 48.16, -124.73),
    ("United States", "maxx", 44.82, -66.95),
    ("United States", "maxy", 25.12, -81.09),
    ("United States", "miny", 49.38, -95.15),
    ("Canada", "maxy", 41.91, -82.51),
    ("Mexico", "minx", 27.85, -115.08),
    ("Mexico", "maxy", 14.53, -92.23),
    ("India", "maxy", 8.08, 77.55),
    ("India", "minx", 23.70, 68.10),
    ("Sri Lanka", "maxy", 5.92, 80.59),
    ("Sri Lanka", "miny", 9.83, 80.25),
    ("Madagascar", "miny", -11.95, 49.26),
    ("Madagascar", "maxy", -25.60, 45.17),
    ("Taiwan", "maxy", 21.90, 120.85),
    ("Taiwan", "miny", 25.30, 121.53),
    ("Senegal", "minx", 14.74, -17.53),
    ("Tunisia", "miny", 37.35, 9.74),
    ("Greenland", "miny", 83.65, -33.40),
    ("Greenland", "maxy", 59.78, -43.93),
    ("New Zealand", "maxy", -46.67, 169.00),
    ("Japan", "miny", 41.55, 140.91),
    ("South Korea", "maxy", 34.30, 126.50),
    ("Egypt", "maxx", 22.00, 36.90),
]

# Coastal cities that must land on their country once fitted.
COAST_CHECK = [
    ("United States", "Seattle", 47.61, -122.33),
    ("United States", "San Francisco", 37.77, -122.42),
    ("United States", "Miami", 25.76, -80.19),
    ("Canada", "Vancouver", 49.28, -123.12),
    ("Japan", "Tokyo", 35.68, 139.69),
    ("Australia", "Perth", -31.95, 115.86),
    ("South Africa", "Cape Town", -33.93, 18.42),
    ("Iceland", "Reykjavik", 64.15, -21.94),
    ("New Zealand", "Auckland", -36.85, 174.76),
    ("Chile", "Santiago", -33.45, -70.67),
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
