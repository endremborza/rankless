import gzip
import json
import re
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd
from aswan import get_soup
from ccl_science_data.common import EntC, get_dl_arr, load_map
from ccl_science_data.gen_reader_ext import GenReaderExt
from rapidfuzz import fuzz
from sklearn.metrics.pairwise import cosine_similarity
from unidecode import unidecode

WIKI_CSV = Path("extern/wiki-nobel.csv")
REPORT_PATH = Path("extern/nobel-matching-report.md")
MATCHES_PATH = Path("extern/nobel-matches.csv")

CANDIDATE_LIMIT = 300
NAME_SCORE_THRESHOLD = 0.55
FINAL_SCORE_THRESHOLD = 0.5
ITERATIONS = 3

W_NAME = 0.55
W_SUBFIELD = 0.25
W_BOOST = 0.20

SUFFIX_TOKENS = {"jr", "sr", "junior", "senior", "ii", "iii", "iv", "v"}
COMMON_SURNAMES = {
    "smith",
    "johnson",
    "robinson",
    "brown",
    "williams",
    "diamond",
    "lee",
    "kim",
    "li",
    "wang",
}

SCIENCE_CATEGORIES = {"Physics", "Chemistry", "Physiology or Medicine", "Economics"}

# (surname, wrong_first_name): known false matches where two different people
# share the same surname and first initial, evading automated checks.
KNOWN_FALSE_FIRST_NAMES = {
    ("kantorovich", "lev"),  # Leonid Kantorovich ≠ Lev Kantorovich
    ("boyle", "william"),  # Willard S. Boyle ≠ William S. Boyle
}


class NameVariant(TypedDict):
    surname: str
    tokens: list[str]
    initials: set[str]
    firstname: str


class Candidate(TypedDict):
    imp_pos: int
    name_score: float


def normalize_name(s: str) -> str:
    s = unidecode(s).lower()
    s = re.sub(r"[,\"()\'\[\]:;]", " ", s)
    s = re.sub(r"[-/]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def strip_suffix_tokens(tokens: list[str]) -> list[str]:
    while tokens and tokens[-1].strip(".") in SUFFIX_TOKENS:
        tokens = tokens[:-1]
    return tokens


def parse_name_variants(raw_name: str) -> list[NameVariant]:
    parts = strip_suffix_tokens(normalize_name(raw_name).split())
    if not parts:
        return [NameVariant(surname="", tokens=[], initials=set(), firstname="")]
    if len(parts) == 1:
        return [
            NameVariant(
                surname=parts[0],
                tokens=parts,
                initials=set(),
                firstname=parts[0],
            )
        ]
    if len(parts) == 2:
        p0, p1 = parts
        return [
            NameVariant(surname=p1, tokens=[p0, p1], initials={p0[0]}, firstname=p0),
            NameVariant(surname=p0, tokens=[p1, p0], initials={p1[0]}, firstname=p1),
        ]
    return [
        NameVariant(
            surname=parts[-1],
            tokens=parts,
            initials={p[0] for p in parts[:-1] if p},
            firstname=parts[0],
        )
    ]


def dump_laureates() -> None:
    soup = get_soup("https://en.wikipedia.org/wiki/List_of_Nobel_laureates")
    table = soup.find("table")
    categories = [
        "Physics",
        "Chemistry",
        "Physiology or Medicine",
        "Literature",
        "Peace",
        "Economics",
    ]
    rows: list[dict] = []
    for tr in table.select("tbody > tr"):
        year_th = tr.find("th", scope="row")
        if not year_th:
            continue
        year = int(year_th.get_text(strip=True))
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        for cat, td in zip(categories, tds):
            if td.get_text(strip=True) in ("\u2014", "-", ""):
                continue
            for a in td.find_all("a", href=True):
                rows.append(
                    {
                        "category": cat,
                        "year": year,
                        "name": a.get_text(strip=True),
                        "link": a["href"],
                    }
                )
    pd.DataFrame(rows).to_csv(WIKI_CSV, index=False)


class NobelMatcher:
    def __init__(self, root: str = ".") -> None:
        self.wiki_df = (
            pd.read_csv(WIKI_CSV)
            .loc[lambda df: df["category"].isin(SCIENCE_CATEGORIES)]
            .reset_index(drop=True)
        )
        self._load_impact_data(root)
        self._build_surname_index()

    def _load_impact_data(self, root: str) -> None:
        gr = GenReaderExt(root)
        anames = gr.get_names(EntC.AUTHORS)
        sfn = len(gr.get_names(EntC.SUBFIELDS))

        self.impact_matrix = (
            get_dl_arr("authors-cit-subfields", 5, 16)
            .reshape(-1, sfn)[:-1, :]
            .astype(float)
        )
        impact_totals = self.impact_matrix.sum(axis=1)
        self.impact_boost = np.log1p(impact_totals) / np.log1p(impact_totals.max())

        self.dm_to_oa: dict[int, int] = {
            v: k for k, v in load_map(EntC.AUTHORS).items()
        }
        self.impact_names: list[str] = ["Unknown"] + anames[1:]
        self.impact_names_norm = [normalize_name(n) for n in self.impact_names]
        self.impact_tokens = [
            strip_suffix_tokens(n.split()) for n in self.impact_names_norm
        ]
        self.impact_token_sets = [set(toks) for toks in self.impact_tokens]
        self.impact_initials = [
            {t[0] for t in toks if t} for toks in self.impact_tokens
        ]
        self.impact_firstnames = [
            toks[0] if toks else "" for toks in self.impact_tokens
        ]
        self.impact_surnames = [
            parse_name_variants(n)[0]["surname"] for n in self.impact_names
        ]

    def _build_surname_index(self) -> None:
        self.surname_index: dict[str, list[int]] = {}
        for pos, raw in enumerate(self.impact_names):
            for v in parse_name_variants(raw):
                if v["surname"]:
                    self.surname_index.setdefault(v["surname"], []).append(pos)

    def _name_score(self, variant: NameVariant, imp_pos: int) -> float:
        imp_surname = self.impact_surnames[imp_pos]
        surname_exact = 1.0 if variant["surname"] == imp_surname else 0.0

        nob_tokens = set(variant["tokens"])
        imp_tokens = self.impact_token_sets[imp_pos]
        tok_overlap = (
            len(nob_tokens & imp_tokens) / len(nob_tokens) if nob_tokens else 0.0
        )

        nob_inits = variant["initials"]
        imp_inits = self.impact_initials[imp_pos]
        init_overlap = len(nob_inits & imp_inits) / len(nob_inits) if nob_inits else 0.0

        fuzzy_full = (
            fuzz.token_sort_ratio(
                self.impact_names_norm[imp_pos],
                normalize_name(" ".join(variant["tokens"])),
            )
            / 100.0
        )

        imp_first = self.impact_firstnames[imp_pos]
        nob_first = variant["firstname"]
        first_sim = 0.0
        if nob_first and imp_first:
            first_sim = fuzz.partial_ratio(nob_first, imp_first) / 100.0
            if nob_first[0] == imp_first[0] and first_sim < 0.6:
                first_sim -= 0.3

        penalty = 0.0
        if nob_inits and imp_inits:
            penalty += 0.05 * len(imp_inits - nob_inits)
        if imp_tokens - nob_tokens:
            penalty += 0.03 * len(imp_tokens - nob_tokens)

        score = (
            0.50 * surname_exact
            + 0.22 * tok_overlap
            + 0.18 * init_overlap
            + 0.10 * fuzzy_full
            - penalty
        )
        if imp_surname in COMMON_SURNAMES and score < 0.8:
            score *= 0.9
        return float(np.clip(score, 0, 1))

    def _find_candidates(self, nobel_name: str) -> list[Candidate]:
        variants = parse_name_variants(nobel_name)
        positions: set[int] = set()
        for v in variants:
            if v["surname"] and v["surname"] in self.surname_index:
                positions.update(self.surname_index[v["surname"]])

        candidates: list[Candidate] = []
        for pos in positions:
            best = max(self._name_score(v, pos) for v in variants)
            if best >= NAME_SCORE_THRESHOLD:
                candidates.append(Candidate(imp_pos=pos, name_score=best))

        candidates.sort(key=lambda c: c["name_score"], reverse=True)
        return candidates[:CANDIDATE_LIMIT]

    def _subfield_sim(
        self,
        imp_pos: int,
        category: str,
        prototypes: dict[str, np.ndarray],
    ) -> float:
        if category not in prototypes:
            return 0.0
        vec = self.impact_matrix[imp_pos].reshape(1, -1)
        proto = prototypes[category].reshape(1, -1)
        if np.all(proto == 0) or np.all(vec == 0):
            return 0.0
        return float(cosine_similarity(vec, proto)[0, 0])

    def _compute_prototypes(self, matches: pd.DataFrame) -> dict[str, np.ndarray]:
        protos: dict[str, np.ndarray] = {}
        matched = matches.dropna(subset=["impact_pos"])
        for cat in matched["category"].unique():
            ids = (
                matched.loc[matched["category"] == cat, "impact_pos"]
                .astype(int)
                .unique()
            )
            if len(ids):
                protos[cat] = np.mean(self.impact_matrix[ids, :], axis=0)
        return protos

    def _validate_match(self, nobel_name: str, imp_pos: int) -> bool:
        """Reject matches where names are clearly incompatible.

        Three narrow checks, each targeting a specific failure mode:
        1. Name-reversal: "Jack Kilby" → "K.H. Jack" (surname index finds first name)
        2. Initial-mismatch: "Jerome Friedman" → "Daniel Friedman" (D ∉ {J,I,F})
        3. Deny-list: known same-initial false matches (Lev/Leonid, William/Willard)
        """
        nob_tokens = strip_suffix_tokens(normalize_name(nobel_name).split())
        if len(nob_tokens) < 2:
            return True

        imp_first = self.impact_firstnames[imp_pos]
        imp_surname = self.impact_surnames[imp_pos]

        # 1. Reject name-reversal: matched surname == Nobel first name
        if imp_surname == nob_tokens[0] and imp_surname != nob_tokens[-1]:
            return False

        # 2. Reject when matched full first name's initial is absent from all Nobel tokens
        if len(imp_first) >= 3:
            nob_initials = {t[0] for t in nob_tokens if t}
            if imp_first[0] not in nob_initials:
                return False

        # 3. Reject known false matches (same initial, different person)
        if (imp_surname, imp_first) in KNOWN_FALSE_FIRST_NAMES:
            return False

        return True

    def run(self) -> pd.DataFrame:
        laureate_candidates: list[tuple[int, str, str, list[Candidate]]] = []
        for idx, row in self.wiki_df.iterrows():
            cands = self._find_candidates(row["name"])
            laureate_candidates.append((idx, row["name"], row["category"], cands))

        matches = self._initial_matches(laureate_candidates)

        for _ in range(ITERATIONS):
            prototypes = self._compute_prototypes(matches)
            matches = self._score_iteration(laureate_candidates, prototypes)

        matches = matches.merge(
            self.wiki_df[["year", "category"]],
            left_index=True,
            right_index=True,
            suffixes=("", "_wiki"),
        ).drop(columns=["category_wiki"], errors="ignore")

        matches["dm_id"] = matches["impact_pos"]
        matches["oa_id"] = matches["dm_id"].map(self.dm_to_oa)
        matches.to_csv(MATCHES_PATH, index=False)

        self._write_report(matches)
        print(f"Matched {matches['impact_pos'].notna().sum()}/{len(matches)} laureates")
        print(f"Report: {REPORT_PATH}")
        print(f"Matches: {MATCHES_PATH}")
        return matches

    def _initial_matches(
        self,
        laureate_candidates: list[tuple[int, str, str, list[Candidate]]],
    ) -> pd.DataFrame:
        rows: list[dict] = []
        for idx, name, category, cands in laureate_candidates:
            best = self._pick_best(name, cands, category, {})
            rows.append(
                {
                    "nobel_name": name,
                    "category": category,
                    "matched_name": self.impact_names[best["imp_pos"]]
                    if best
                    else None,
                    "impact_pos": best["imp_pos"] if best else None,
                    "name_score": best["name_score"] if best else None,
                    "final_score": best["final_score"] if best else None,
                }
            )
        return pd.DataFrame(rows, index=[lc[0] for lc in laureate_candidates])

    def _score_iteration(
        self,
        laureate_candidates: list[tuple[int, str, str, list[Candidate]]],
        prototypes: dict[str, np.ndarray],
    ) -> pd.DataFrame:
        rows: list[dict] = []
        for idx, name, category, cands in laureate_candidates:
            best = self._pick_best(name, cands, category, prototypes)
            rows.append(
                {
                    "nobel_name": name,
                    "category": category,
                    "matched_name": self.impact_names[best["imp_pos"]]
                    if best
                    else None,
                    "impact_pos": best["imp_pos"] if best else None,
                    "name_score": best["name_score"] if best else None,
                    "final_score": best["final_score"] if best else None,
                }
            )
        return pd.DataFrame(rows, index=[lc[0] for lc in laureate_candidates])

    def _pick_best(
        self,
        nobel_name: str,
        candidates: list[Candidate],
        category: str,
        prototypes: dict[str, np.ndarray],
    ) -> dict | None:
        if not candidates:
            return None
        scored = []
        for c in candidates:
            sf_sim = self._subfield_sim(c["imp_pos"], category, prototypes)
            final = (
                W_NAME * c["name_score"]
                + W_SUBFIELD * sf_sim
                + W_BOOST * self.impact_boost[c["imp_pos"]]
            )
            ad = {
                "imp_pos": c["imp_pos"],
                "name_score": c["name_score"],
                "final_score": final,
            }
            scored.append(ad)
        scored.sort(key=lambda x: x["final_score"], reverse=True)
        for result in scored:
            if result["final_score"] < FINAL_SCORE_THRESHOLD:
                break
            if self._validate_match(nobel_name, result["imp_pos"]):
                return result
        return None

    def _write_report(self, matches: pd.DataFrame) -> None:
        total = len(matches)
        matched = matches["impact_pos"].notna()
        n_matched = matched.sum()
        n_unmatched = total - n_matched

        lines = [
            "# Nobel Laureate Matching Report\n",
            "## Summary\n",
            f"- **Total laureates** (science): {total}",
            f"- **Matched**: {n_matched} ({n_matched / total:.1%})",
            f"- **Unmatched**: {n_unmatched} ({n_unmatched / total:.1%})\n",
        ]

        lines.append("## Match Rate by Category\n")
        lines.append("| Category | Total | Matched | Rate |")
        lines.append("|----------|------:|--------:|-----:|")
        for cat in sorted(SCIENCE_CATEGORIES):
            cat_mask = matches["category"] == cat
            cat_total = cat_mask.sum()
            cat_matched = (cat_mask & matched).sum()
            rate = cat_matched / cat_total if cat_total else 0
            lines.append(f"| {cat} | {cat_total} | {cat_matched} | {rate:.1%} |")

        lines.append("\n## Match Rate by Decade\n")
        lines.append("| Decade | Total | Matched | Rate |")
        lines.append("|--------|------:|--------:|-----:|")
        matches["decade"] = (matches["year"] // 10) * 10
        for decade in sorted(matches["decade"].unique()):
            dec_mask = matches["decade"] == decade
            dec_total = dec_mask.sum()
            dec_matched = (dec_mask & matched).sum()
            rate = dec_matched / dec_total if dec_total else 0
            lines.append(f"| {decade}s | {dec_total} | {dec_matched} | {rate:.1%} |")
        matches.drop(columns=["decade"], inplace=True)

        uncertain = matches[matched].nsmallest(15, "final_score")[
            [
                "nobel_name",
                "matched_name",
                "category",
                "year",
                "name_score",
                "final_score",
            ]
        ]
        lines.append("\n## Lowest-Confidence Matches (sanity check)\n")
        lines.append(
            "| Nobel Name | Matched Name | Category | Year | Name Score | Final Score |"
        )
        lines.append(
            "|------------|-------------|----------|-----:|-----------:|------------:|"
        )
        for _, r in uncertain.iterrows():
            lines.append(
                f"| {r['nobel_name']} | {r['matched_name']} | {r['category']} "
                f"| {r['year']} | {r['name_score']:.3f} | {r['final_score']:.3f} |"
            )

        unmatched_df = matches[~matched][
            ["nobel_name", "category", "year"]
        ].sort_values("year")
        lines.append(f"\n## Unmatched Laureates ({n_unmatched})\n")
        if len(unmatched_df):
            lines.append("| Nobel Name | Category | Year |")
            lines.append("|------------|----------|-----:|")
            for _, r in unmatched_df.iterrows():
                lines.append(f"| {r['nobel_name']} | {r['category']} | {r['year']} |")
        else:
            lines.append("All laureates matched.\n")

        lines.append("\n## High-Confidence Samples (per category)\n")
        for cat in sorted(SCIENCE_CATEGORIES):
            cat_matched = matches[(matches["category"] == cat) & matched]
            if cat_matched.empty:
                continue
            sample = cat_matched.nlargest(5, "final_score")
            lines.append(f"### {cat}\n")
            lines.append("| Nobel Name | Matched Name | Year | Final Score |")
            lines.append("|------------|-------------|-----:|------------:|")
            for _, r in sample.iterrows():
                lines.append(
                    f"| {r['nobel_name']} | {r['matched_name']} "
                    f"| {r['year']} | {r['final_score']:.3f} |"
                )
            lines.append("")

        REPORT_PATH.write_text("\n".join(lines))


def main() -> None:
    if reform_df():
        return
    if not WIKI_CSV.exists():
        print("Scraping Nobel laureates from Wikipedia...")
        dump_laureates()
    matcher = NobelMatcher()
    matcher.run()


def reform_df() -> bool:
    if MATCHES_PATH.exists():
        nobel_df = (
            pd.read_csv(MATCHES_PATH).loc[:, ["oa_id", "category", "year"]].dropna()
        )
        nobel_recs = [
            {
                "category": gid,
                "winners": gdf.loc[:, ["year", "oa_id"]].astype(int).values.tolist(),
            }
            for gid, gdf in nobel_df.groupby("category")
        ]
        Path("nobel-to-oa.json.gz").write_bytes(
            gzip.compress(json.dumps({"winners": nobel_recs}).encode())
        )
        return True
    return False


if __name__ == "__main__":
    main()
