import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, text

app = Flask(__name__)

load_dotenv()

con = os.environ["PG_CONSTR"]
engine = create_engine(con)


def build_tree(df, breakdown_cols):
    """
    Recursively builds the tree from a grouped dataframe.
    """
    if not breakdown_cols:
        return None

    current_col = breakdown_cols[0]
    remaining_cols = breakdown_cols[1:]

    # Group by the current level
    # sourceCount: unique source works at this level
    # linkCount: total number of citation links (rows)
    grouped = df.groupby(current_col).agg(
        source_count=("src_work_id", "nunique"), link_count=("cit_work_id", "count")
    )

    result = {}
    for key, row in grouped.iterrows():
        node = {
            "sourceCount": int(row["source_count"]),
            "linkCount": int(row["link_count"]),
        }

        if remaining_cols:
            # Filter df for the next level of recursion
            sub_df = df[df[current_col] == key]
            children = build_tree(sub_df, remaining_cols)
            if children:
                node["children"] = children

        result[str(key)] = node

    return result


@app.route("/impact-tree", methods=["POST"])
def get_impact_tree():
    data = request.json
    root_type = data["root_type"]
    breakdowns = data["breakdowns"]
    root_id = data.get("root_id")  # Assuming you need a specific entity ID to start

    # Map API types to View Columns
    col_map = {
        "authors": "authors",
        "institutions": "institutions",
        "countries": "countries",
        "sources": "sources",
        "subfields": "subfields",
        "topics": "topics",
        "works": "work_id",
    }

    # Determine columns to select
    query_cols = ["src_work_id", "cit_work_id"]
    breakdown_path = []

    for b in breakdowns:
        prefix = "src_" if b["sourceSide"] else "cit_"
        col_name = prefix + col_map[b["node"]]
        query_cols.append(col_name)
        breakdown_path.append(col_name)

    # Filtering by the Root Entity
    root_col = f"src_{col_map[root_type]}"

    # Construct SQL
    sql = f"""
        SELECT {', '.join(set(query_cols))}
        FROM impact_denormalized
        WHERE {root_col} = :root_id
    """

    df = pd.read_sql(text(sql), engine, params={"root_id": root_id})

    # Clean data (remove rows where breakdown keys are null if necessary)
    df = df.dropna(subset=breakdown_path)

    # Build the tree
    tree = build_tree(df, breakdown_path)

    # Calculate global root stats
    response = {
        "sourceCount": int(df["src_work_id"].nunique()),
        "linkCount": int(df["cit_work_id"].count()),
        "children": tree,
    }

    return jsonify(response)


if __name__ == "__main__":
    view_creator = Path("sql-yardstick/gemini-views.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text(view_creator))
    app.run(debug=True)
