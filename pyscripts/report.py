import datetime as dt
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


if __name__ == "__main__":

    gen_date = dt.datetime.now()
    rep_dir = gen_date.strftime("%Y-%m-%d-%H-%M")
    rep_dpath = Path("reports", rep_dir)
    rep_dpath.mkdir(exist_ok=True, parents=True)

    tpr = Transper(SSHrer("rankless-live"))

    logtail = tpr.ssh.run(f"tail -{n} /var/log/nginx/access.log")

    line_rex = re.compile(
        r'(.*?) \-.*\-.*\[(.*)\].*"([A-Z]+) (.*?)".*rt=(.*) uct="(.*)" uht="(.*)" urt="(.*)"'
    )

    root = f"https://{tpr.get_dns()}"

    code_df = pd.DataFrame(
        re.findall(r'"GET (.*?)" (\d\d\d)', logtail), columns=["endp", "code"]
    ).assign(code=lambda df: df["code"].astype(int))

    err_df = code_df.loc[lambda df: (df["code"] // 100) == 5]

    pct_miss = f"{round((err_df.shape[0] / code_df.shape[0]) * 100, 2)}%"

    misses = "\n".join(
        map(
            lambda ep: f"<li><a href=\"{root}{ep.split(' ')[0]}\">{ep.split(' ')[0]}</a></li>",
            err_df["endp"].drop_duplicates().head(50),
        )
    )

    ldf = pd.DataFrame(
        map(lambda e: e[0], filter(None, map(line_rex.findall, logtail.split("\n")))),
        columns=["addr", "time", "r", "p", "rt", "uct", "uht", "urt"],
    ).assign(
        t=lambda df: df["time"].pipe(pd.to_datetime, format="%d/%b/%Y:%H:%M:%S %z"),
        urt=lambda df: df["urt"].apply(tryfloat),
    )

    df = ldf.resample(samp, on="t")["urt"].agg([p99, "count"]).reset_index().tail(40)

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

    html_str = f"""<body>
    <h1>{rep_dir} report</h1>
    <h3>{n} lines in {ldf["t"].max() - ldf["t"].min()}</h3>
    <h3>{pct_miss} 500 rate</h3>
    <img src="fig.png" />
    <h3>Misses:</h3>
    <ul>{misses}</ul>
    </body>
    """

    (rep_dpath / "index.html").write_text(html_str)

    reps = []
    for sd in rep_dpath.parent.iterdir():
        if sd.is_dir():
            rn = sd.name
            subtitle = re.findall("<h3>(.*)</h3>", (sd / "index.html").read_text())[0]
            reps.append(f'<li><a href="./{rn}/index.html">{rn}</a> {subtitle}</li>')

    (rep_dpath.parent / "index.html").write_text(
        f"""
    <body>
    <h1>Reports</h1>
    <ul>
    {''.join(sorted(reps))}
    </ul>
    </body>
    """
    )
