import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import requests

GET_COMM = ["ssh", "rankless-live", "cat /tmp/survey-logs.jsonl"]
WEB_PUBLISH_DIR = os.environ["WEB_PUBLISH_DIR"]


def get_ipmap(ips):
    ipfile = Path("/tmp/ipmap.json")
    if ipfile.exists():
        ipmap = json.loads(ipfile.read_text())
    else:
        ipmap = {}
    for ip in ips:
        if ip not in ipmap.keys():
            ipmap[ip] = requests.get(f"http://ipwho.is/{ip}").json()
    ipfile.write_text(json.dumps(ipmap))
    return ipmap


if __name__ == "__main__":
    recs = list(
        map(
            json.loads,
            subprocess.check_output(GET_COMM).strip().split(b"\n"),
        )
    )
    filldf = pd.DataFrame(
        e["payload"]
        | {"ip": e["fwIp"]}
        | {d["id"]: d["score"] for d in e["payload"]["scores"]}
        for e in filter(lambda r: r["type"] == "submit", recs)
    ).drop("scores", axis=1)
    rejdf = pd.DataFrame(filter(lambda r: r["type"] != "submit", recs))
    ipmap = get_ipmap(rejdf.loc[:, "fwIp"].tolist() + filldf["ip"].tolist())
    ipcous = pd.DataFrame(ipmap.values()).set_index("ip")["country"]
    fill_exp = (
        filldf.assign(country_by_ip=lambda df: ipcous.reindex(df["ip"]).values)
        .drop(["ip"], axis=1)
        .drop(0)
    )
    country_counts = (
        pd.DataFrame(ipmap.values())
        .groupby("country")[["ip"]]
        .count()
        .sort_values("ip", ascending=False)
    )
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
            <div>
            <h2>IP Distribution</h2>
                    {country_counts.to_html()}
            </div>
            <div>
            <h2>Sum</h2>
                    {int(country_counts.sum().iloc[0])}
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
    print("-" * 20, "\n")
    print(country_counts)
