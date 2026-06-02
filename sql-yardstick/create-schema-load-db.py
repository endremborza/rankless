import os
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import sqlalchemy as sa
from ccl_science_data.common import (
    DN,
    EntC,
    IDC,
    PARID,
    get_last_filter,
    iter_dfs,
    parse_id,
)
from dotenv import load_dotenv
from sqlmermaid import to_file
from tqdm import tqdm

load_dotenv()

MAINS = [EntC.WORKS, EntC.AUTHORS, EntC.INSTITUTIONS, EntC.SOURCES, EntC.TOPICS]
FMAINS = [EntC.DOMAINS, EntC.FIELDS, EntC.SUBFIELDS]
SUBS = [
    (EntC.WORKS, "referenced_works"),
    (EntC.WORKS, EntC.AUTHORSHIPS),
    (EntC.WORKS, "locations"),
    (EntC.WORKS, "topics"),
]
TAKEN_COLS = [PARID, IDC, DN]
SCHEMA_PATH = Path("sql-yardstick/schemas.toml")
SCHEMAS_EXT = tomllib.loads(SCHEMA_PATH.read_text())


def field_id_parser(col: pd.Series) -> pd.Series:
    return col.str.split("/").str[-1].astype(int)


def parse_ships(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.set_index([PARID, "author"])["institutions"]
        .str.split(";", expand=True)
        .melt(ignore_index=False)
        .loc[:, "value"]
        .dropna()
        .rename("institution")
        .pipe(parse_id)
        .astype(int)
        .reset_index()
    )


def get_filt(ent):
    try:
        return get_last_filter(ent)
    except Exception:
        return None


def do_filtering(
    df: pd.DataFrame, col: str, filt, leave_zeroes: bool = False
) -> pd.DataFrame:
    if filt is None:
        return df
    if leave_zeroes:
        return df.assign(**{col: np.where(df[col].isin(filt), df[col], 0)})
    return df.loc[df[col].isin(filt)]


def df_fixer(df: pd.DataFrame, name: str) -> pd.DataFrame:
    updates: dict = {}
    if PARID in df.columns:
        updates[PARID] = parse_id(df[PARID]).astype(int)
    if IDC in df.columns:
        pfun = field_id_parser if name in FMAINS else parse_id
        updates[IDC] = pfun(df[IDC]).astype(int)
    if updates:
        df = df.assign(**updates)
    ext_cols = []
    for k, v_full in SCHEMAS_EXT.get(name, {}).items():
        v = v_full.split("-")[0]
        if v == "id":
            df = df.dropna(subset=k).assign(**{k: lambda d: parse_id(d[k]).astype(int)})
        elif v == "fid":
            df = df.assign(**{k: lambda d: field_id_parser(d[k])})
        ext_cols.append(k)
    return df.loc[:, df.columns.intersection(TAKEN_COLS + ext_cols)]


def iter_fks(name: str):
    for k, v_full in SCHEMAS_EXT.get(name, {}).items():
        v_elems = v_full.split("-")
        if len(v_elems) > 1:
            yield k, v_elems[1]


def make_pk(name: str, meta: sa.MetaData) -> sa.schema.AddConstraint:
    table = meta.tables[name]
    return sa.schema.AddConstraint(
        sa.PrimaryKeyConstraint(table.c.id, name=f"{name}_pkey")
    )


def make_fk(
    name: str, col: str, target: str, meta: sa.MetaData
) -> sa.schema.AddConstraint:
    table = meta.tables[name]
    return sa.schema.AddConstraint(
        sa.ForeignKeyConstraint(
            [col], [f"{target}.{IDC}"], table=table, name=f"{name}_{col}_{target}_fkey"
        )
    )


def dump_schema(con: str) -> str:
    engine = sa.create_engine(con)
    meta = sa.MetaData()
    meta.reflect(bind=engine, views=True)
    return "\n".join(
        str(sa.schema.CreateTable(t).compile(engine)).strip() + ";"
        for t in meta.sorted_tables
    )


def main():
    con = os.environ["PG_CONSTR"]
    engine = sa.create_engine(con)
    filter_dic = {k: get_filt(k) for k in MAINS}
    _ik = "institution"

    with engine.connect() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
        conn.commit()

    loaded_ids: dict[str, set] = {}
    for ent in MAINS + FMAINS:
        filt = filter_dic.get(ent)
        ids: set = set()
        for df in tqdm(iter_dfs(ent, chunk=100_000), desc=ent):
            fdf = df_fixer(df, ent).set_index(IDC)
            if filt is not None:
                fdf = fdf.loc[fdf.index.isin(filt)]
            ids.update(fdf.index)
            fdf.to_sql(ent, con, if_exists="append")
        ids.add(0)
        pd.DataFrame({IDC: [0], DN: ["Unknown"]}).to_sql(
            ent, con, if_exists="append", index=False
        )
        loaded_ids[ent] = ids

    sub_cols: dict[str, list] = {}
    for ent, sub in SUBS:
        name = f"{ent}-{sub}"
        cols: list = []
        for df in tqdm(iter_dfs(ent, sub, chunk=100_000), desc=name):
            fdf = df_fixer(df, name)
            for col, target in iter_fks(name):
                fdf = do_filtering(
                    fdf,
                    col,
                    loaded_ids.get(target),
                    leave_zeroes=sub == EntC.AUTHORSHIPS,
                )
            fdf = do_filtering(fdf, PARID, loaded_ids.get(ent))
            if sub == EntC.AUTHORSHIPS:
                fdf = parse_ships(fdf).assign(
                    **{
                        _ik: lambda df: np.where(
                            df[_ik].isin(loaded_ids[EntC.INSTITUTIONS]), df[_ik], 0
                        )
                    }
                )
            cols = list(fdf.columns)
            fdf.to_sql(name, con, if_exists="append", index=False)
        sub_cols[name] = cols

    meta = sa.MetaData()
    meta.reflect(bind=engine, views=True)

    pk_constraints = [make_pk(ent, meta) for ent in MAINS + FMAINS]
    fk_constraints = [
        make_fk(ent, col, target, meta)
        for ent in MAINS + FMAINS
        for col, target in iter_fks(ent)
    ]
    for ent, sub in SUBS:
        name = f"{ent}-{sub}"
        fk_constraints.extend(
            make_fk(name, col, target, meta) for col, target in iter_fks(name)
        )
        if sub == EntC.AUTHORSHIPS:
            fk_constraints.append(make_fk(name, _ik, EntC.INSTITUTIONS, meta))
        if PARID in sub_cols.get(name, []):
            fk_constraints.append(make_fk(name, PARID, ent, meta))

    with engine.begin() as conn:
        for c in pk_constraints + fk_constraints:
            conn.execute(c)

    schema_sql = dump_schema(con)
    Path(SCHEMA_PATH.parent / "schema.sql").write_text(schema_sql)
    print(schema_sql)
    to_file(con, "sql-yardstick/schema.md")


if __name__ == "__main__":
    main()
