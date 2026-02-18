import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text

load_dotenv()

# (view_table, filter_column) for building root_works CTE
ROOT_MAP = {
    "authors": ("work_authors", "author"),
    "institutions": ("work_authors", "institution"),
    "countries": ("work_authors", "country_code"),
}

# table=None means the work id itself is the breakdown key (no join needed)
NODE_MAP = {
    "authors": {"table": "work_authors", "column": "author"},
    "institutions": {"table": "work_authors", "column": "institution"},
    "countries": {"table": "work_authors", "column": "country_code"},
    "sources": {"table": "work_sources", "column": "source"},
    "subfields": {"table": "work_subfields", "column": "subfield"},
    "works": {"table": None, "column": None},
}

app = Flask(__name__)
engine = create_engine(os.environ["PG_CONSTR"])


def build_level_query(root_type: str, breakdowns: list, depth: int) -> str:
    """
    Build a query that groups the impact body by all breakdown keys from 0..depth
    and returns COUNT(DISTINCT source_work) and COUNT(DISTINCT (source_work, citing_work)).

    Running one query per depth level gives correct distinct counts at every node
    because each level's counts come directly from the raw edge set, not from summing
    children (which over-counts when works map to multiple breakdown keys).
    """
    root_table, root_column = ROOT_MAP[root_type]
    select_parts = []
    join_parts = []
    group_parts = []

    for i in range(depth + 1):
        bd = breakdowns[i]
        alias = f"lvl{i}"
        mapping = NODE_MAP[bd["node"]]
        table = mapping["table"]
        work_col = "source_work" if bd["sourceSide"] else "citing_work"

        if table is None:
            col_expr = f"impact.{work_col}"
        else:
            col_expr = f"{alias}.{mapping['column']}"
            join_parts.append(
                f"JOIN {table} {alias} ON {alias}.work_id = impact.{work_col}"
            )

        select_parts.append(f"{col_expr} AS level_{i}")
        group_parts.append(col_expr)

    joins = "\n    ".join(join_parts)
    selects = ", ".join(select_parts)
    groups = ", ".join(group_parts)

    return f"""
    WITH root_works AS (
        SELECT DISTINCT work_id FROM {root_table} WHERE {root_column} = :root_id
    ),
    impact AS (
        SELECT ce.source_work, ce.citing_work
        FROM citation_edges ce
        JOIN root_works rw ON ce.source_work = rw.work_id
    )
    SELECT
        {selects},
        COUNT(DISTINCT source_work) AS sourcecount,
        COUNT(DISTINCT (source_work, citing_work)) AS linkcount
    FROM impact
    {joins}
    GROUP BY {groups}
    """


def build_tree(level_results: list) -> dict:
    """
    Assemble a tree from per-depth query results. Each depth's rows carry
    the counts for that level directly — no summation from children.
    """
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
        level_results = [
            conn.execute(
                text(build_level_query(root_type, breakdowns, depth)),
                {"root_id": root_id},
            ).mappings().all()
            for depth in range(len(breakdowns))
        ]

    return jsonify(build_tree(level_results))


if __name__ == "__main__":
    view_creator = Path("sql-yardstick/views.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(view_creator))
    app.run(debug=True)
