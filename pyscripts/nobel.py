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


impact_matrix = impact_df[sf_cols].fillna(0).astype(float).to_numpy()
impact_totals = impact_matrix.sum(axis=1)
impact_boost = np.log1p(impact_totals) / np.log1p(impact_totals.max())


def normalize_name(s):
    s = unidecode(s).lower()
    s = re.sub(r"[,\(\)\"'\[\]\:\;]", " ", s)
    s = re.sub(r"[-/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_suffix_tokens(tokens):
    while tokens and tokens[-1].strip(".") in SUFFIX_TOKENS:
        tokens = tokens[:-1]
    return tokens


def parse_name_variants(raw_name):
    s = normalize_name(raw_name)
    parts = strip_suffix_tokens(s.split())
    if not parts:
        return [{"surname": "", "tokens": [], "initials": set(), "firstname": ""}]
    variants = []
    if len(parts) == 1:
        variants.append(
            {
                "surname": parts[0],
                "tokens": parts,
                "initials": set(),
                "firstname": parts[0],
            }
        )
    elif len(parts) == 2:
        p0, p1 = parts
        variants.append(
            {"surname": p1, "tokens": [p0, p1], "initials": {p0[0]}, "firstname": p0}
        )
        variants.append(
            {"surname": p0, "tokens": [p1, p0], "initials": {p1[0]}, "firstname": p1}
        )
    else:
        surname = parts[-1]
        firstname = parts[0]
        initials = {p[0] for p in parts[:-1] if p}
        variants.append(
            {
                "surname": surname,
                "tokens": parts,
                "initials": initials,
                "firstname": firstname,
            }
        )
    return variants


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


def name_components_score(nobel_variant, imp_pos):
    imp_tokens_set = impact_token_sets[imp_pos]
    imp_initials = impact_initials[imp_pos]
    imp_name_norm = impact_names_norm[imp_pos]
    imp_firstname = impact_firstnames[imp_pos]
    imp_surname = parse_name_variants(impact_names[imp_pos])[0]["surname"]

    # surname exact
    surname_exact = 1.0 if nobel_variant["surname"] == imp_surname else 0.0

    # token overlap
    nob_tokens = set(nobel_variant["tokens"])
    tok_overlap = (
        len(nob_tokens & imp_tokens_set) / len(nob_tokens) if nob_tokens else 0.0
    )

    # initials
    nob_inits = nobel_variant["initials"]
    init_overlap = len(nob_inits & imp_initials) / len(nob_inits) if nob_inits else 0.0

    # fuzzy full
    fuzzy_full = (
        fuzz.token_sort_ratio(
            imp_name_norm, normalize_name(" ".join(nobel_variant["tokens"]))
        )
        / 100.0
    )

    # NEW: first-name fuzzy similarity
    first_sim = 0.0
    if nobel_variant["firstname"] and imp_firstname:
        first_sim = (
            fuzz.partial_ratio(nobel_variant["firstname"], imp_firstname) / 100.0
        )

    # if same initial but first names differ greatly, penalize
    if nobel_variant["firstname"] and imp_firstname:
        if nobel_variant["firstname"][0] == imp_firstname[0] and first_sim < 0.6:
            first_sim -= 0.3  # penalize misleading same-initials

    extra_init_penalty = 0.0
    if nob_inits and imp_initials:
        if len(imp_initials - nob_inits) > 0:
            extra_init_penalty = 0.05 * len(imp_initials - nob_inits)

    extra_token_penalty = 0.0
    if imp_tokens_set - nob_tokens:
        extra_token_penalty = 0.03 * len(imp_tokens_set - nob_tokens)

    # combine with tuned weights (strong preference for surname/token overlap)
    score = float(
        0.50 * surname_exact
        + 0.22 * tok_overlap
        + 0.18 * init_overlap
        + 0.10 * fuzzy_full
        - extra_init_penalty
        - extra_token_penalty
    )
    if imp_surname in COMMON_SURNAMES and score < 0.8:
        score *= 0.9

    return float(np.clip(score, 0, 1))


# -----------------------------
# Subfield similarity helper
# -----------------------------
def compute_subfield_similarity(imp_pos, category, prototypes):
    if category not in prototypes:
        return 0.0
    vec = impact_matrix[imp_pos].reshape(1, -1)
    proto = prototypes[category].reshape(1, -1)
    if np.all(proto == 0) or np.all(vec == 0):
        return 0.0
    return float(cosine_similarity(vec, proto)[0, 0])


# -----------------------------
# Initial matches (same as before)
# -----------------------------
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


def compute_prototypes(matches):
    protos = {}
    for cat in matches["category"].dropna().unique():
        ids = matches.loc[matches["category"] == cat, "impact_pos"].unique().tolist()
        if ids:
            protos[cat] = np.mean(impact_matrix[ids, :], axis=0)
    return protos


prototypes = compute_prototypes(initial_df)

# -----------------------------
# Final matching and refinement (same as before)
# -----------------------------
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
