import json
import os
import subprocess
from pathlib import Path

import pandas as pd

GET_COMM = ["ssh", "rankless-live", "cat /tmp/survey-logs.jsonl"]
WEB_PUBLISH_DIR = os.environ["WEB_PUBLISH_DIR"]


if __name__ == "__main__":
    recs = list(
        map(
            json.loads,
            subprocess.check_output(GET_COMM).strip().split(b"\n"),
        )
    )
    filldf = pd.DataFrame(
        e["payload"] | {d["id"]: d["score"] for d in e["payload"]["scores"]}
        for e in filter(lambda r: r["type"] == "submit", recs)
    ).drop("scores", axis=1)
    fill_exp = filldf.drop(0)
    means = fill_exp.loc[:, lambda df: df.dtypes.eq(int)].mean().to_frame()

    exp_txt = f"""
    <!DOCTYPE html>
    <html>
    <head>
            <title>Survey Results</title>
    </head>
    <body>
            <div>
            <h2>Responses</h2>
                    {fill_exp.to_html()}
            </div>
            <div>
            <h2>Means</h2>
                    {means.to_html()}
            </div>
    </body>
    <style>
            div {{
                    padding: 40px;
            }}
    </style>
    </html>
    """
    op = Path("rl-survey.html")
    op.write_text(exp_txt)
    subprocess.check_output(["scp", op.as_posix(), WEB_PUBLISH_DIR])
    print(fill_exp)
