from pathlib import Path

import sqlalchemy as sa
import yaml
from ccl_science_data.common import *
from tqdm import tqdm

MAINS = [
    EntC.WORKS,
    EntC.AUTHORS,
    EntC.INSTITUTIONS,
    EntC.SOURCES,
    EntC.TOPICS,
]

FMAINS = [
    EntC.DOMAINS,
    EntC.FIELDS,
    EntC.SUBFIELDS,
]

SUBS = [
    (EntC.WORKS, "referenced_works"),
    (EntC.WORKS, EntC.AUTHORSHIPS),
    (EntC.WORKS, "locations"),
    (EntC.WORKS, "topics"),
]

TAKEN_COLS = [PARID, IDC, DN]

SCHEMA_PATH = Path("sql-yardstick/schemas.yaml")
con = os.environ["PG_CONSTR"]


def field_id_parser(col: pd.Series):
    return col.str.split("/").str[-1].astype(int)


def parse_ships(df):
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


engine = sa.create_engine(con)
meta = sa.MetaData()
meta.reflect(bind=engine, views=True)


def print_schema(meta=meta):
    lines = []
    for table in meta.sorted_tables:
        lines.append(sa.schema.CreateTable(table).compile(engine))

    for table in meta.tables.values():
        for c in table.constraints:
            if isinstance(c, (sa.ForeignKeyConstraint, sa.PrimaryKeyConstraint)):
                # lines.append(sa.schema.AddConstraint(c).compile(engine))
                pass
    sch_printed = "\n".join([str(e).strip() + ";" for e in lines])
    return sch_printed


def add_index(name):
    meta.reflect(bind=engine, views=True)
    table = meta.tables[name]
    pk = sa.PrimaryKeyConstraint(table.c.id, name=f"{name}_pkey")
    return sa.schema.AddConstraint(pk)


def get_fk(name, col, target):
    meta.reflect(bind=engine, views=True)
    table = meta.tables[name]
    return sa.schema.AddConstraint(
        sa.ForeignKeyConstraint(
            [col], [f"{target}.{IDC}"], table=table, name=f"{name}_{col}_{target}_fkey"
        )
    )


def get_filt(ent):
    try:
        return get_last_filter(ent)
    except:
        return None


def do_fltering(df: pd.DataFrame, col, filt, leave_zeroes=False):
    if filt is None:
        return df
    if leave_zeroes:
        return df.assign(**{col: np.where(df[col].isin(filt), df[col], 0)})
    return df.loc[df[col].isin(filt), :]


# %%
with engine.connect() as conn:
    conn.execute(sa.text("DROP SCHEMA public CASCADE"))
    conn.execute(sa.text("CREATE SCHEMA public"))
    conn.commit()

meta.reflect(bind=engine, views=True)


schemas_ext = yaml.load(SCHEMA_PATH.read_bytes())


def df_fixer(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if PARID in df.columns:
        df.loc[:, PARID] = parse_id(df[PARID]).astype(int)
    if IDC in df.columns:
        pfun = field_id_parser if name in FMAINS else parse_id
        df.loc[:, IDC] = pfun(df.loc[:, IDC]).astype(int)
    ext_cols = []
    for k, v_full in schemas_ext.get(name, {}).items():
        v = v_full.split("-")[0]
        if v == "id":
            df = df.dropna(subset=k)
            df.loc[:, k] = parse_id(df[k]).astype(int)
        if v == "fid":
            df.loc[:, k] = field_id_parser(df.loc[:, k])
        ext_cols.append(k)
    return df.loc[:, df.columns.intersection(TAKEN_COLS + ext_cols)]


pk_constraints = []
fk_constraints = []


def iter_fks(name):
    for k, v_full in schemas_ext.get(name, {}).items():
        v_elems = v_full.split("-")
        if len(v_elems) > 1:
            yield k, v_elems[1]


def add_fk(name):
    for col, target in iter_fks(name):
        fk_constraints.append(get_fk(name, col, target))


filter_dic = {k: get_filt(k) for k in MAINS}

for ent in MAINS + FMAINS:
    filt = filter_dic.get(ent)
    for df in tqdm(iter_dfs(ent, chunk=100_000), desc=ent):
        fdf = df_fixer(df, ent).set_index(IDC)
        if filt is not None:
            fdf = fdf.loc[fdf.index.isin(filt)]
        fdf.to_sql(ent, con, if_exists="append")
    pd.DataFrame({IDC: [0], DN: ["Unknown"]}).to_sql(
        ent, con, if_exists="append", index=False
    )
    pk_constraints.append(add_index(ent))
    add_fk(ent)


_ik = "institution"
wfilt = get_last_filter(EntC.WORKS)
for ent, sub in SUBS:
    name = f"{ent}-{sub}"
    cols = []
    for df in tqdm(iter_dfs(ent, sub, chunk=100_000), desc=name):
        fdf = df_fixer(df, name)
        for col, target in iter_fks(name):
            fdf = do_fltering(
                fdf, col, filter_dic.get(target), leave_zeroes=sub == EntC.AUTHORSHIPS
            )
        fdf = do_fltering(fdf, PARID, filter_dic.get(ent))
        if sub == EntC.AUTHORSHIPS:
            fdf = parse_ships(fdf).assign(
                **{
                    _ik: lambda df: np.where(
                        df[_ik].isin(filter_dic[EntC.INSTITUTIONS]), df[_ik], 0
                    )
                }
            )
        cols = fdf.columns
        fdf.to_sql(name, con, if_exists="append", index=False)
    add_fk(name)
    if sub == EntC.AUTHORSHIPS:
        fk_constraints.append(get_fk(name, _ik, EntC.INSTITUTIONS))
    if PARID in cols:
        fk_constraints.append(get_fk(name, PARID, ent))

with engine.begin() as conn:
    for c in pk_constraints + fk_constraints:
        conn.execute(c)

# %%

engine = sa.create_engine(con)
meta = sa.MetaData()
meta.reflect(bind=engine, views=True)
schema_in_sql = print_schema(meta)
Path(SCHEMA_PATH.parent / "schema.sql").write_text(schema_in_sql)
print(schema_in_sql)

# %%


def print_dump():
    schemas = {}
    for ent in MAINS:
        df = next(iter_dfs(ent, chunk=1000))
        # parse_id()
        schemas[ent] = {k: str(v) for k, v in df.dtypes.items()}
    for ent, sub in SUBS:
        df = next(iter_dfs(ent, sub, chunk=1000))
        schemas[f"{ent}-{sub}"] = {k: str(v) for k, v in df.dtypes.items()}
    schema_dump_path = Path("sql-yardstick/schemas-dump.yaml")
    schema_dump_path.write_text(yaml.dump(schemas))


# %%
columbia_id = 78577930
inst_id = columbia_id
# pd.read_sql_query(f"SELECT * FROM INSTITUTIONS WHERE id={inst_id} LIMIT 100", con=con)
# pd.read_sql_query("SELECT * FROM INSTITUTIONS LIMIT 100", con=con)
wids = pd.read_sql_query(
    f'SELECT * FROM "works-authorships" WHERE institution={inst_id}', con=con
)[PARID].unique()
ship_df = pd.read_sql_query(
    f'SELECT * FROM "works-authorships" wa LEFT JOIN "works-referenced_works" wr ON wr.referenced_work_id=wa.{PARID} WHERE institution={inst_id}',
    con=con,
)

print(len(wids))
print(ship_df.shape)
ship_df.nunique().to_dict()
