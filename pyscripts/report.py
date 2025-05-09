import datetime as dt
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .deploy import SSHrer, Transper


def p99(s):
    return s.quantile(0.99)


def tryfloat(s):
    try:
        return float(s)
    except:
        return float("nan")


n = 100_000
# samp = "1min"
samp = "10min"
line_rex = re.compile(
    r'(.*?) \-.*\-.*\[(.*)\].*"([A-Z]+) (.*?)" (\d\d\d) (\d+) "(.*)" "(.*)"rt=(.*) uct="(.*)" uht="(.*)" urt="(.*)"'
)
line_cols = [
    "addr",
    "time",
    "r",
    "p",
    "code",
    "size",
    "referrer",
    "agent",
    "rt",
    "uct",
    "uht",
    "urt",
]


if __name__ == "__main__":

    gen_date = dt.datetime.now()
    rep_dir = gen_date.strftime("%Y-%m-%d-%H-%M")
    rep_dpath = Path("reports", rep_dir)
    rep_dpath.mkdir(exist_ok=True, parents=True)
    ssh_id = "rankless-live"

    tpr = Transper(SSHrer(ssh_id))
    logtail = tpr.ssh.run(f"tail -{n} /var/log/nginx/access.log")
    root = f"https://{tpr.get_dns()}"
    hour_df = (
        pd.DataFrame(
            map(
                lambda e: e[0], filter(None, map(line_rex.findall, logtail.split("\n")))
            ),
            columns=line_cols,  # pyright: ignore[reportArgumentType]
        )
        .assign(
            t=lambda df: df["time"].pipe(pd.to_datetime, format="%d/%b/%Y:%H:%M:%S %z"),
            urt=lambda df: df["urt"].apply(tryfloat),
            code=lambda df: df["code"].astype(int),
        )
        .loc[lambda df: df["t"] > (df["t"].max() - dt.timedelta(hours=1))]
    )
    err_df = hour_df.loc[lambda df: (df["code"] // 100) == 5]
    tdel = hour_df["t"].max() - hour_df["t"].min()
    miss_n = err_df.shape[0]
    miss_rate = miss_n / hour_df.shape[0]
    pct_miss = f"{round(miss_rate * 100, 2)}%"

    log_rec = {
        "period": f"{tdel}".split(" ")[-1],
        "uniqe_clients": hour_df["addr"].nunique(),
        "total_requests": hour_df.shape[0],
        "request_per_second": round(hour_df.shape[0] / tdel.total_seconds(), 3),
        "500_count": miss_n,
        "500_rate": miss_rate,
    } | dict(
        zip(
            ["resp_time_median", "resp_time_p99", "resp_time_p999"],
            hour_df["urt"].quantile([0.5, 0.99, 0.999]),
        )
    )

    misses = "\n".join(
        map(
            lambda ekv: f"<li><a href=\"{root}{ekv[0].split(' ')[0]}\">{ekv[0].split(' ')[0]} ({ekv[1]})</a></li>",
            err_df["p"].value_counts().head(50).items(),
        )
    )

    df = (
        hour_df.resample(samp, on="t")["urt"].agg([p99, "count"]).reset_index().tail(40)
    )

    fig, ax1 = plt.subplots()

    ax1.set_xlabel("Date")
    ax1.set_ylabel("P99 Response Time (s)", color="tab:blue")
    ax1.plot(df["t"], df["p99"], color="tab:blue", label="Response Time (P99)")
    ax1.tick_params(axis="y", labelcolor="tab:blue")

    ax2 = ax1.twinx()
    ax2.set_ylabel("Request Count", color="tab:red")
    ax2.plot(df["t"], df["count"], color="tab:red", label="Request Count")
    ax2.tick_params(axis="y", labelcolor="tab:red")

    ax1.set_xticks(df["t"])
    ax1.set_xticklabels(df["t"].dt.strftime("%H:%M"), rotation=90, ha="center")
    ax1.set_title(pct_miss)
    fig.tight_layout()
    plt.savefig(rep_dpath / "fig.png")
    try:
        files_table_str = tpr.get_backend_open_files_df().to_html()
    except Exception as e:
        print(e)
        files_table_str = str(e)

    html_str = f"""<body>
    <h1>{rep_dir} report</h1>
    <h3>{pct_miss} 500 rate</h3>
    <img src="fig.png" />
    <h3>Misses:</h3>
    <ul>{misses}</ul>
    <hr />
    {files_table_str}
    </body>
    """

    (rep_dpath / "index.html").write_text(html_str)
    (rep_dpath / "rec.json").write_text(json.dumps(log_rec))
    hour_df.to_csv(rep_dpath / "reqs.csv.gz", index=False)

    reps = []
    links = []
    for sd in rep_dpath.parent.iterdir():
        if sd.is_dir():
            rn = sd.name
            links.append(f'<li><a href="./{rn}/index.html">{rn}</a></li>')
            js_fp = sd / "rec.json"
            if js_fp.exists():
                reps.append({"report": rn} | json.loads(js_fp.read_text()))

    head_n = 48
    html_table = (
        pd.DataFrame(reps)
        .set_index("report")
        .sort_index(ascending=False)
        .head(head_n)
        .style.background_gradient(axis=0)
        .to_html()
    )

    (rep_dpath.parent / "index.html").write_text(
        f"""
    <head>
    <title>Access log report</title>
    </head>
    <body>
    <h1>Reports</h1>
            {html_table}
            <ul>
            {''.join(sorted(links)[-head_n:][::-1])}
            </ul>
    </body>
    """
    )
