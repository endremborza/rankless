import json
from pathlib import Path

import pandas as pd
import polars as pl
from ccl_science_data.common import (
    PUBY,
    get_csv_path,
    get_last_filter,
    parse_id,
    read_full_df,
)
from ccl_science_data.gen import ComC, EntC

_EXTERN = Path(__file__).parent.parent / "extern"

# Integer codes for Nobel categories — avoids repeating strings in the CSV.
# Only scientific categories that appear in nobel-matches.csv are listed.
NOBEL_CATEGORY_CODES = {
    "Physics": 1,
    "Chemistry": 2,
    "Physiology or Medicine": 3,
    "Economics": 4,
}

# link_frame = "https://tmp-borza-public-cyx.s3.amazonaws.com/{}.csv.gz"
link_frame = "s3://tmp-borza-public-cyx/{}.csv.gz"


def get_best_q_by_year():
    return pl.read_csv(link_frame.format("metascience/q-by-year"))


def write_csv(df: pd.DataFrame, main: str, sub: str):
    df.to_csv(get_csv_path(main, sub), index=False, compression="zstd")


if __name__ == "__main__":
    source_filter = get_last_filter(EntC.SOURCES)
    adf = pd.read_csv(link_frame.format("metascience/areas")).drop_duplicates()
    sodf = (
        read_full_df(EntC.SOURCES, "ids")
        .assign(id=lambda df: df["openalex"].pipe(parse_id))
        .loc[lambda df: df["id"].isin(source_filter), :]
        .set_index("id")
    )
    _isc = "issn"
    _issns = pd.concat(
        [
            sodf[_isc].dropna().apply(json.loads).explode().reset_index(),
            sodf["issn_l"].dropna().rename(_isc).reset_index(),
        ]
    ).drop_duplicates()

    _issns.merge(adf).drop(_isc, axis=1).drop_duplicates().assign(
        id=lambda df: ComC.ID_PREFIX + "S" + df["id"].astype(str)
    ).pipe(write_csv, EntC.SOURCES, EntC.AREA_FIELDS)
    q_matched_df = (
        get_best_q_by_year()
        .select(
            [
                pl.col(_isc),
                pl.col("year").cast(pl.UInt16).alias(PUBY),
                pl.col("best_q").str.slice(1, None).cast(pl.UInt8),
            ]
        )
        .join(pl.from_pandas(_issns).select(["id", pl.col(_isc)]), on=_isc)
        .drop(_isc)
        .unique()
    )
    q_matched_df.to_pandas().pipe(write_csv, EntC.SOURCES, EntC.QS)
    oa_to_slug = pd.read_csv(link_frame.format("oa-to-wiki-authors")).drop(
        "rl_i", axis=1
    )
    oa_to_slug.pipe(write_csv, EntC.AUTHORS, "wiki-slug")
    nobel_out = (
        pd.read_csv(_EXTERN / "nobel-matches.csv")
        .loc[lambda df: df["oa_id"].notna()]
        .assign(
            category=lambda df: df["category"].map(NOBEL_CATEGORY_CODES),
        )
        .loc[lambda df: df["category"].notna()]
        .loc[:, ["oa_id", "category", "year"]]
        .astype(int)
    )
    assert len(nobel_out) > 400, f"Expected 400+ Nobel matches, got {len(nobel_out)}"
    nobel_out.pipe(write_csv, EntC.AUTHORS, "nobel")
