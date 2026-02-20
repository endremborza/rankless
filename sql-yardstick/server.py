import os
from io import StringIO
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text

load_dotenv()

# (view_table, filter_column) for building root_works CTE
ROOT_MAP = {
    "authors": ("work_authors", "author"),
    "institutions": ("work_authors", "institution"),
    "countries": ("work_authors", "country_code"),
    "sources": ("work_sources", "source"),
    "subfields": ("work_subfields", "subfield"),
}

# dm_table: mapping table for OA→DM translation (None for works breakdown)
NODE_MAP = {
    "authors": {"table": "work_authors", "column": "author", "dm_table": "dm_authors"},
    "institutions": {"table": "work_authors", "column": "institution", "dm_table": "dm_institutions"},
    "countries": {"table": "work_authors", "column": "country_code", "dm_table": "dm_countries"},
    "sources": {"table": "work_sources", "column": "source", "dm_table": "dm_sources"},
    "subfields": {"table": "work_subfields", "column": "subfield", "dm_table": "dm_subfields"},
    "topics": {"table": "work_topics", "column": "topic", "dm_table": "dm_topics"},
    "works": {"table": None, "column": None, "dm_table": "dm_works"},
}

app = Flask(__name__)
engine = create_engine(os.environ["PG_CONSTR"])

OA_ROOT = os.environ.get("OA_ROOT", "")
MAPPING_DIR = Path(OA_ROOT, "a1_entity_mapping")

# Entity types that use integer OA IDs
INT_ENTITIES = ["authors", "institutions", "sources", "subfields", "topics", "works"]


def id_to_cc(val: int) -> str:
    chars = []
    while val > 0:
        chars.append(chr(val & 0xFF))
        val >>= 8
    return "".join(chars)


def load_dm_mappings(conn):
    for ent in INT_ENTITIES:
        blob = Path(MAPPING_DIR, ent).read_bytes()
        pairs = np.frombuffer(blob, dtype=np.dtype(np.uint64).newbyteorder(">")).reshape(-1, 2)
        conn.execute(text(f"DROP TABLE IF EXISTS dm_{ent} CASCADE"))
        conn.execute(text(f"CREATE TABLE dm_{ent} (oa_id BIGINT PRIMARY KEY, dm_id BIGINT)"))

        buf = StringIO()
        for oa, dm in pairs:
            buf.write(f"{oa}\t{dm}\n")
        buf.seek(0)
        raw = conn.connection.driver_connection
        with raw.cursor() as cur:
            cur.copy_from(buf, f"dm_{ent}", columns=("oa_id", "dm_id"))

    # Countries: mapping file uses cc_to_id encoded integers, PG has country_code text
    blob = Path(MAPPING_DIR, "countries").read_bytes()
    pairs = np.frombuffer(blob, dtype=np.dtype(np.uint64).newbyteorder(">")).reshape(-1, 2)
    conn.execute(text("DROP TABLE IF EXISTS dm_countries CASCADE"))
    conn.execute(text(
        "CREATE TABLE dm_countries (country_code TEXT PRIMARY KEY, dm_id BIGINT)"
    ))
    buf = StringIO()
    for cc_int, dm in pairs:
        cc = id_to_cc(int(cc_int))
        if cc:
            buf.write(f"{cc}\t{dm}\n")
    buf.seek(0)
    raw = conn.connection.driver_connection
    with raw.cursor() as cur:
        cur.copy_from(buf, "dm_countries", columns=("country_code", "dm_id"))


def build_root_query(root_type: str) -> str:
    root_table, root_column = ROOT_MAP[root_type]
    return f"""
    WITH root_works AS (
        SELECT DISTINCT work_id FROM {root_table} WHERE {root_column} = :root_id
    ),
    impact AS (
        SELECT ce.source_work, ce.citing_work
        FROM citation_edges ce
        JOIN root_works rw ON ce.source_work = rw.work_id
    ),
    per_source AS (
        SELECT source_work, COUNT(DISTINCT citing_work) AS work_links
        FROM impact
        GROUP BY source_work
    ),
    top_source AS (
        SELECT source_work, work_links FROM per_source ORDER BY work_links DESC LIMIT 1
    )
    SELECT
        COUNT(DISTINCT i.source_work) AS sourcecount,
        COUNT(DISTINCT (i.source_work, i.citing_work)) AS linkcount,
        (SELECT dw.dm_id FROM top_source ts JOIN dm_works dw ON dw.oa_id = ts.source_work) AS top_source_id,
        (SELECT ts.work_links FROM top_source ts) AS top_source_links
    FROM impact i
    """


def build_level_query(root_type: str, breakdowns: list, depth: int) -> str:
    root_table, root_column = ROOT_MAP[root_type]
    select_parts = []
    join_parts = []
    group_parts = []
    where_parts = []
    join_aliases: dict[tuple[str, str], str] = {}
    dm_join_counter = 0

    for i in range(depth + 1):
        bd = breakdowns[i]
        mapping = NODE_MAP[bd["node"]]
        table = mapping["table"]
        dm_table = mapping["dm_table"]
        work_col = "source_work" if bd["sourceSide"] else "citing_work"

        if table is None:
            # "works" breakdown: map work ID through dm_works
            dm_alias = f"dm{dm_join_counter}"
            dm_join_counter += 1
            join_parts.append(
                f"JOIN {dm_table} {dm_alias} ON {dm_alias}.oa_id = impact.{work_col}"
            )
            col_expr = f"{dm_alias}.dm_id"
        else:
            join_key = (table, work_col)
            if join_key not in join_aliases:
                alias = f"lvl{i}"
                join_aliases[join_key] = alias
                join_parts.append(
                    f"JOIN {table} {alias} ON {alias}.work_id = impact.{work_col}"
                )
            else:
                alias = join_aliases[join_key]

            raw_col = f"{alias}.{mapping['column']}"
            where_parts.append(f"{raw_col} IS NOT NULL")

            # Source-side breakdown from root table: scope to root-affiliated rows
            # Only when grouping by a different column than the root (e.g. authors
            # of an institution) — not when grouping by the root column itself or
            # peer columns like country_code
            if (
                bd["sourceSide"]
                and table == root_table
                and mapping["column"] != root_column
                and mapping["column"] not in ("country_code",)
            ):
                where_parts.append(f"{alias}.{root_column} = :root_id")

            # Join through DM mapping table
            dm_alias = f"dm{dm_join_counter}"
            dm_join_counter += 1
            if bd["node"] == "countries":
                join_parts.append(
                    f"JOIN {dm_table} {dm_alias} ON {dm_alias}.country_code = {raw_col}"
                )
            else:
                join_parts.append(
                    f"JOIN {dm_table} {dm_alias} ON {dm_alias}.oa_id = {raw_col}"
                )
            col_expr = f"{dm_alias}.dm_id"

        select_parts.append(f"{col_expr} AS level_{i}")
        group_parts.append(col_expr)

    joins = "\n        ".join(join_parts)
    level_selects = ", ".join(select_parts)
    group_aliases = ", ".join(f"level_{i}" for i in range(depth + 1))
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    join_condition = " AND ".join(f"g.level_{i} = ts.level_{i}" for i in range(depth + 1))

    return f"""
    WITH root_works AS (
        SELECT DISTINCT work_id FROM {root_table} WHERE {root_column} = :root_id
    ),
    impact AS (
        SELECT ce.source_work, ce.citing_work
        FROM citation_edges ce
        JOIN root_works rw ON ce.source_work = rw.work_id
    ),
    expanded AS (
        SELECT
            {level_selects},
            source_work,
            citing_work
        FROM impact
        {joins}
        {where_clause}
    ),
    grouped AS (
        SELECT
            {group_aliases},
            COUNT(DISTINCT source_work) AS sourcecount,
            COUNT(DISTINCT (source_work, citing_work)) AS linkcount
        FROM expanded
        GROUP BY {group_aliases}
    ),
    per_source AS (
        SELECT
            {group_aliases},
            source_work,
            COUNT(DISTINCT citing_work) AS work_links
        FROM expanded
        GROUP BY {group_aliases}, source_work
    ),
    top_source AS (
        SELECT DISTINCT ON ({group_aliases})
            {group_aliases},
            source_work AS top_source_work,
            work_links AS top_source_links
        FROM per_source
        ORDER BY {group_aliases}, work_links DESC
    )
    SELECT
        g.*,
        dw.dm_id AS top_source_id,
        ts.top_source_links
    FROM grouped g
    JOIN top_source ts ON {join_condition}
    JOIN dm_works dw ON dw.oa_id = ts.top_source_work
    """


def build_tree(level_results: list) -> dict:
    tree: dict = {}
    n = len(level_results)

    for depth, rows in enumerate(level_results):
        for row in rows:
            node = tree
            for i in range(depth):
                node = node[str(row[f"level_{i}"])]["children"]

            key = str(row[f"level_{depth}"])
            node[key] = {
                "linkCount": row["linkcount"],
                "sourceCount": row["sourcecount"],
                "topSourceId": row["top_source_id"],
                "topSourceLinks": row["top_source_links"],
            }
            if depth < n - 1:
                node[key]["children"] = {}

    return tree


@app.route("/impact-tree", methods=["POST"])
def impact():
    data = request.json
    root_type = data["root_type"]
    root_id = data["root_id"]
    breakdowns = data["breakdowns"]

    with engine.connect() as conn:
        root_row = conn.execute(
            text(build_root_query(root_type)), {"root_id": root_id}
        ).mappings().one()
        level_results = [
            conn.execute(
                text(build_level_query(root_type, breakdowns, depth)),
                {"root_id": root_id},
            ).mappings().all()
            for depth in range(len(breakdowns))
        ]

    return jsonify({
        "linkCount": root_row["linkcount"],
        "sourceCount": root_row["sourcecount"],
        "topSourceId": root_row["top_source_id"],
        "topSourceLinks": root_row["top_source_links"],
        "children": build_tree(level_results),
    })


if __name__ == "__main__":
    view_sql = Path("sql-yardstick/views.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(view_sql))
        load_dm_mappings(conn)
    app.run(debug=True, host=os.environ.get("FLASK_HOST", "127.0.0.1"))
