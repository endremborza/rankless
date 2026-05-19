import shutil
import tempfile
from pathlib import Path

import polars as pl

from pyscripts.reporting import aggregate, archive, config
from pyscripts.reporting.archive import annotate_routes
from pyscripts.reporting.classify import annotate_events, classify_sessions
from pyscripts.reporting.parse import parse_lines
from pyscripts.reporting.render import render_all
from pyscripts.reporting.sessions import assign_sessions

from .fixtures import ALL


def _setup_tmp_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="reports-v2-test-"))
    config.REPORTS_ROOT = tmp
    config.ARCHIVE_DIR = tmp / "archive"
    config.ARCHIVE_COLD_DIR = tmp / "archive-cold"
    config.AGGREGATES_DIR = tmp / "aggregates"
    config.SITE_LOCAL_DIR = tmp / "site"
    config.SITE_PUBLIC_DIR = tmp / "site-public"
    config.RUN_LOGS_DIR = tmp / "logs"
    config.SALTS_PATH = tmp / "salts.json"
    config.STATE_PATH = tmp / "state.json"
    archive.ARCHIVE_DIR = config.ARCHIVE_DIR
    archive.ARCHIVE_COLD_DIR = config.ARCHIVE_COLD_DIR
    aggregate.AGGREGATES_DIR = config.AGGREGATES_DIR
    from pyscripts.reporting import state as state_mod

    state_mod.SALTS_PATH = config.SALTS_PATH
    state_mod.STATE_PATH = config.STATE_PATH
    config.ensure_dirs()
    return tmp


def _populate(tmp: Path):
    import datetime as dt

    df, _ = parse_lines(ALL)
    now_utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    base = now_utc.replace(minute=0, second=0) - dt.timedelta(hours=1)
    new_ts = [base + dt.timedelta(seconds=i) for i in range(len(df))]
    df = df.with_columns(pl.Series("t", new_ts, dtype=pl.Datetime("us", "UTC")))
    df = annotate_routes(df)
    df = assign_sessions(df)
    sessions = classify_sessions(df)
    aggregate.write_sessions(sessions)
    df = annotate_events(df, sessions)
    archive.write_events(df)
    aggregate.rebuild()


def test_render_local_mode():
    tmp = _setup_tmp_root()
    try:
        _populate(tmp)
        ctx = render_all("local")
        assert (ctx.out_dir / "index.html").exists()
        assert (ctx.out_dir / "traffic.html").exists()
        assert (ctx.out_dir / "performance.html").exists()
        assert (ctx.out_dir / "errors.html").exists()
        assert (ctx.out_dir / "sessions" / "index.html").exists()
        assert (ctx.out_dir / "classification.html").exists()
        assert (ctx.out_dir / "runs" / "index.html").exists()
        assert (ctx.out_dir / "assets" / "style.css").exists()
        landing = (ctx.out_dir / "index.html").read_text()
        assert "<title>" in landing
    finally:
        shutil.rmtree(tmp)


def test_render_public_mode_anonymizes():
    import re

    tmp = _setup_tmp_root()
    try:
        _populate(tmp)
        ctx = render_all("public")
        ip_re = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
        for f in ctx.out_dir.rglob("*.html"):
            text = f.read_text()
            assert not ip_re.search(text), (
                f"raw IP leaked in {f}: {ip_re.search(text).group(0)}"
            )
    finally:
        shutil.rmtree(tmp)
