import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

NODE_MAP = {
    "authors": {
        "table": "work_authors",
        "column": "author",
    },
    "institutions": {
        "table": "work_authors",
        "column": "institution",
    },
    "countries": {
        "table": "work_authors",
        "column": "country_code",
    },
    "sources": {
        "table": "work_sources",
        "column": "source",
    },
    "subfields": {
        "table": "work_subfields",
        "column": "subfield",
    },
    "works": {
        "table": None,
        "column": "work_id",
    },
}


ROOT_COLUMN_MAP = {
    "authors": "author",
    "institutions": "institution",
    "countries": "country_code",
}

app = Flask(__name__)
engine = create_engine(os.environ["PG_CONSTR"])


def build_tree_query(root_type, root_id, breakdowns):
    select_parts = []
    group_parts = []
    join_parts = []

    level_aliases = []

    for i, bd in enumerate(breakdowns):
        alias = f"lvl{i}"
        level_aliases.append(alias)

        node = bd["node"]
        source_side = bd["sourceSide"]

        mapping = NODE_MAP[node]
        table = mapping["table"]
        column = mapping["column"]

        work_col = "source_work" if source_side else "citing_work"

        join_parts.append(
            f"""
            LEFT JOIN {table} {alias}
            ON {alias}.work_id = impact.{work_col}
        """
        )

        select_parts.append(f"{alias}.{column} AS level_{i}")
        group_parts.append(f"{alias}.{column}")

    root_column = ROOT_COLUMN_MAP[root_type]
    query = f"""
    WITH root_works AS (
        SELECT DISTINCT work_id
        FROM work_authors
        WHERE {root_column} = :root_id
    ),
    impact AS (
        SELECT
            ce.source_work,
            ce.citing_work
        FROM citation_edges ce
        JOIN root_works rw ON ce.source_work = rw.work_id
    )
    SELECT
        {", ".join(select_parts)},
        COUNT(DISTINCT impact.source_work) AS sourceCount,
        COUNT(*) AS linkCount
    FROM impact
    {" ".join(join_parts)}
    GROUP BY {", ".join(group_parts)}
    """

    return query


def rows_to_tree(rows, breakdowns):
    root = {}

    for row in rows:
        current = root

        for i in range(len(breakdowns)):
            key = row.get(f"level_{i}")
            if key is None:
                continue

            if key not in current:
                current[key] = {
                    "linkCount": 0,
                    "sourceCount": 0,
                    "children": {},
                }

            current[key]["linkCount"] += row["linkcount"]
            current[key]["sourceCount"] += row["sourcecount"]

            current = current[key]["children"]

    return root


@app.route("/impact-tree", methods=["POST"])
def impact():
    data = request.json
    root_type = data["root_type"]
    root_id = data["root_id"]
    breakdowns = data["breakdowns"]

    query = build_tree_query(root_type, root_id, breakdowns)

    with engine.connect() as conn:
        result = conn.execute(text(query), {"root_id": root_id})
        rows = result.mappings().all()

    tree = rows_to_tree(rows, breakdowns)

    return jsonify(tree)


if __name__ == "__main__":
    view_creator = Path("sql-yardstick/oai-views.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(view_creator))
    app.run(debug=True)
