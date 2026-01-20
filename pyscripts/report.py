import datetime as dt
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .deploy import SSHrer, Transper


def p99(s):
    return s.quantile(0.99)


samp = "10min"


if __name__ == "__main__":
    rep_dir = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
    rep_dpath = Path("reports", rep_dir)
    rep_dpath.mkdir(exist_ok=True, parents=True)
    ssh_id = "rankless-live"
    tpr = Transper(SSHrer(ssh_id, reset=True))
    hour_df = tpr.get_nginx_logs_df(60, 100_000)
    hn = hour_df.shape[0]
    err_df = hour_df.loc[lambda df: (df["code"] // 100) == 5]
    tdel = hour_df["t"].max() - hour_df["t"].min()
    miss_n = err_df.shape[0]
    c429 = int((hour_df["code"] == 429).sum())
    miss_rate = miss_n / hn
    pct_miss = f"{round(miss_rate * 100, 2)}%"

    log_rec = {
        "period": f"{tdel}".split(" ")[-1],
        "uniqe_clients": hour_df["addr"].nunique(),
        "total_requests": hn,
        "request_per_second": round(hour_df.shape[0] / tdel.total_seconds(), 3),
        "429_count": c429,
        "429_rate": c429 / hn,
        "500_count": miss_n,
        "500_rate": miss_rate,
    } | dict(
        zip(
            ["resp_time_median", "resp_time_p99", "resp_time_p999"],
            hour_df["urt"].quantile([0.5, 0.99, 0.999]),
        )
    )

    def make_line(kv):
        return f"<li><a href=\"{root}{kv[0].split(' ')[0]}\">{kv[0].split(' ')[0]} ({kv[1]})</a></li>"

    root = f"https://{tpr.get_domain()}"
    misses = "\n".join(map(make_line, err_df["p"].value_counts().head(50).items()))
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
