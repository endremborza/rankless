import shutil
import tempfile
from pathlib import Path

from pyscripts.reporting import aggregate, archive, config
from pyscripts.reporting.archive import annotate_routes
from pyscripts.reporting.classify import annotate_events, classify_sessions
from pyscripts.reporting.parse import parse_lines
from pyscripts.reporting.sessions import assign_sessions

from .fixtures import ALL


def _setup_tmp_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="reports-v2-test-"))
    config.REPORTS_ROOT = tmp
    config.ARCHIVE_DIR = tmp / "archive"
    config.ARCHIVE_COLD_DIR = tmp / "archive-cold"
    config.AGGREGATES_DIR = tmp / "aggregates"
    config.SALTS_PATH = tmp / "salts.json"
    config.STATE_PATH = tmp / "state.json"
    archive.ARCHIVE_DIR = config.ARCHIVE_DIR
    archive.ARCHIVE_COLD_DIR = config.ARCHIVE_COLD_DIR
    aggregate.AGGREGATES_DIR = config.AGGREGATES_DIR
    aggregate.HOURLY_PATH = config.AGGREGATES_DIR / "hourly.parquet"
    aggregate.DAILY_PATH = config.AGGREGATES_DIR / "daily.parquet"
    aggregate.SESSIONS_PATH = config.AGGREGATES_DIR / "sessions.parquet"
    from pyscripts.reporting import state as state_mod
    state_mod.SALTS_PATH = config.SALTS_PATH
    state_mod.STATE_PATH = config.STATE_PATH
    config.ensure_dirs()
    return tmp


def test_aggregate_consistency():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = annotate_routes(df)
        df = assign_sessions(df)
        sessions = classify_sessions(df)
        df = annotate_events(df, sessions)
        archive.write_events(df)
        result = aggregate.rebuild()
        assert result["rows"] == len(df)

        hourly = aggregate.load_hourly()
        daily = aggregate.load_daily()
        assert hourly["n"].sum() == len(df)
        assert daily["n"].sum() == len(df)
    finally:
        shutil.rmtree(tmp)


def test_aggregate_empty():
    tmp = _setup_tmp_root()
    try:
        result = aggregate.rebuild()
        assert result["rows"] == 0
        assert aggregate.load_hourly().is_empty()
    finally:
        shutil.rmtree(tmp)
