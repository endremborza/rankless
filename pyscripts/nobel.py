import re
import unicodedata

import numpy as np
import pandas as pd
from aswan import get_soup
from ccl_science_data.common import EntC, GenReader, get_dl_arr
from rapidfuzz import fuzz, process
from sklearn.metrics.pairwise import cosine_similarity
from unidecode import unidecode

CANDIDATE_LIMIT = 300
NAME_SCORE_THRESHOLD = 0.55
FINAL_SCORE_THRESHOLD = 0.5
ITERATIONS = 3

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


def remove_diacritics(s):
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def dump_laureates():
    soup = get_soup("https://en.wikipedia.org/wiki/List_of_Nobel_laureates")
    table = soup.find("table")
    rows = []
    for tr in table.select("tbody > tr"):
        year_th = tr.find("th", scope="row")
        if not year_th:
            continue
        year = year_th.get_text(strip=True)

        tds = tr.find_all("td")
        if len(tds) < 6:
            continue  # skip malformed rows

        categories = [
            "Physics",
            "Chemistry",
            "Physiology or Medicine",
            "Literature",
            "Peace",
            "Economics",
        ]

        for cat, td in zip(categories, tds):
            # skip if the cell is just "—"
            if td.get_text(strip=True) in ["—", "-", ""]:
                continue

            # Find all laureate links
            for a in td.find_all("a", href=True):
                name = a.get_text(strip=True)
                link = a["href"]
                rows.append(
                    {"category": cat, "year": int(year), "name": name, "link": link}
                )
    pd.DataFrame(rows).to_csv("wiki-nobel.csv", index=False)


class NobelMatcher:

    def __init__(self, root="..") -> None:
        self.wiki_df = (
            pd.read_csv("wiki-nobel.csv")
            .loc[lambda df: ~df["category"].isin(["Peace", "Literature"]), :]
            .reset_index(drop=True)
        )
        gr = GenReader(root)

        anames = gr.get_names(EntC.AUTHORS)
        sfnames = gr.get_names(EntC.SUBFIELDS)
        sfn = len(sfnames)
        side = "cit"

        rarr = get_dl_arr(f"authors-{side}-subfields", 5, 16).reshape(-1, sfn)[:-1, :]
        self.sf_cols = [f"sf{i}" for i in range(sfn)]
        self.impact_df = (
            pd.DataFrame(rarr, columns=self.sf_cols).assign(name=anames).reset_index()
        )
        self.impact_df.loc[0, "name"] = "Unknown"

    def select_very_likelies():
        # name is very close,
        # seconds closest name is much further
        # has relatively very high impact in at least one subfied
        pass

    def revise():
        # iterate on these
        pass


def main():
    impact_matrix = impact_df[sf_cols].fillna(0).astype(float).to_numpy()
    impact_totals = impact_matrix.sum(axis=1)
    impact_boost = np.log1p(impact_totals) / np.log1p(impact_totals.max())
    impact_names = impact_df["name"].fillna("").astype(str).tolist()
    impact_names_norm = [normalize_name(n) for n in impact_names]
    impact_tokens = [strip_suffix_tokens(n.split()) for n in impact_names_norm]
    impact_token_sets = [set(toks) for toks in impact_tokens]
    impact_initials = [{t[0] for t in toks if t} for toks in impact_tokens]
    impact_firstnames = [toks[0] if toks else "" for toks in impact_tokens]

    surname_index = {}
    for pos, raw in enumerate(impact_names):
        for v in parse_name_variants(raw):
            if v["surname"]:
                surname_index.setdefault(v["surname"], []).append(pos)
    surname_keys = list(surname_index.keys())
    initial_matches = []
    for n_idx, nrow in nobel_df.iterrows():
        name, cat, year = nrow["name"], nrow.get("category"), nrow.get("year")
        variants = parse_name_variants(name)
        for v in variants:
            surname = v["surname"]
            poss = list(surname_index.get(surname, []))
            if not poss:
                cand_surnames = process.extract(
                    surname, surname_keys, scorer=fuzz.ratio, limit=3, score_cutoff=85
                )
                for cand, s, _ in cand_surnames:
                    poss.extend(surname_index.get(cand, []))
            if len(poss) > CANDIDATE_LIMIT:
                poss_scores = [
                    (p, fuzz.token_sort_ratio(impact_names_norm[p], normalize_name(name)))
                    for p in poss
                ]
                poss_scores.sort(key=lambda x: x[1], reverse=True)
                poss = [p for p, _ in poss_scores[:CANDIDATE_LIMIT]]
            for p in poss:
                ns = name_components_score(v, p)
                if ns >= NAME_SCORE_THRESHOLD:
                    initial_matches.append(
                        {
                            "nobel_idx": n_idx,
                            "nobel_name": name,
                            "impact_pos": p,
                            "impact_name": impact_df.loc[p, "name"],
                            "name_score": ns,
                            "category": cat,
                            "year": year,
                        }
                    )
    initial_df = pd.DataFrame(initial_matches)
    prototypes = compute_prototypes(initial_df)
    final_candidates = []
    for n_idx, nrow in nobel_df.iterrows():
        name, cat, year = nrow["name"], nrow.get("category"), nrow.get("year")
        variants = parse_name_variants(name)
        candidate_positions = set()
        for v in variants:
            surname = v["surname"]
            poss = list(surname_index.get(surname, []))
            if not poss:
                cand_surnames = process.extract(
                    surname, surname_keys, scorer=fuzz.ratio, limit=3, score_cutoff=85
                )
                for cand, s, _ in cand_surnames:
                    poss.extend(surname_index.get(cand, []))
            if len(poss) > CANDIDATE_LIMIT:
                poss_scores = [
                    (p, fuzz.token_sort_ratio(impact_names_norm[p], normalize_name(name)))
                    for p in poss
                ]
                poss_scores.sort(key=lambda x: x[1], reverse=True)
                poss = [p for p, _ in poss_scores[:CANDIDATE_LIMIT]]
            candidate_positions.update(poss)

        prior_hits = (
            initial_df.loc[initial_df["nobel_idx"] == n_idx, "impact_pos"].unique().tolist()
            if not initial_df.empty
            else []
        )
        candidate_positions.update(prior_hits)

        best_for_nobel = []
        for p in candidate_positions:
            ns = max(name_components_score(v, p) for v in variants)
            if ns < 0.15:
                continue
            sub_sim = compute_subfield_similarity(p, cat, prototypes)
            iboost = float(impact_boost[p])
            total = 0.65 * ns + 0.25 * sub_sim + 0.10 * iboost
            if total >= 0.15:
                best_for_nobel.append(
                    {
                        "nobel_idx": n_idx,
                        "nobel_name": name,
                        "impact_pos": p,
                        "impact_name": impact_df.loc[p, "name"],
                        "name_score": ns,
                        "subfield_sim": sub_sim,
                        "impact_boost": iboost,
                        "total_score": total,
                        "category": cat,
                        "year": year,
                    }
                )
        if best_for_nobel:
            best_for_nobel.sort(key=lambda x: x["total_score"], reverse=True)
            best = best_for_nobel[0]
            if (
                best["name_score"] >= NAME_SCORE_THRESHOLD
                or best["total_score"] >= FINAL_SCORE_THRESHOLD
            ):
                final_candidates.append(best)

    final_df = pd.DataFrame(final_candidates)
    for it in range(ITERATIONS):
        if final_df.empty:
            break
        prototypes = compute_prototypes(final_df)
        recomputed = []
        for row in final_df.to_dict("records"):
            p = row["impact_pos"]
            ns = row["name_score"]
            ss = compute_subfield_similarity(p, row["category"], prototypes)
            ib = float(impact_boost[p])
            total = 0.65 * ns + 0.25 * ss + 0.10 * ib
            row.update({"subfield_sim": ss, "impact_boost": ib, "total_score": total})
            recomputed.append(row)
        final_df = (
            pd.DataFrame(recomputed)
            .sort_values("total_score", ascending=False)
            .groupby("nobel_idx", as_index=False)
            .first()
        )
        print(f"Refinement pass {it+1}: {len(final_df)} matches")

    final_df["impact_id"] = final_df["impact_pos"]
    out = final_df[
        [
            "nobel_idx",
            "nobel_name",
            "category",
            "year",
            "impact_id",
            "impact_name",
            "name_score",
            "subfield_sim",
            "impact_boost",
            "total_score",
        ]
    ].sort_values("total_score", ascending=False)
    print(out)


if __name__ == "__main__":
    # dump_laureates()
    main()
