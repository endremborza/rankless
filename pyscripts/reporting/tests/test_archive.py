import datetime as dt
import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from pyscripts.reporting import archive, config
from pyscripts.reporting.archive import COLD_COLUMNS
from pyscripts.reporting.parse import parse_lines

from .fixtures import ALL


def _setup_tmp_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="reports-v2-test-"))
    config.REPORTS_ROOT = tmp
    config.ARCHIVE_DIR = tmp / "archive"
    config.ARCHIVE_COLD_DIR = tmp / "archive-cold"
    archive.ARCHIVE_DIR = config.ARCHIVE_DIR
    archive.ARCHIVE_COLD_DIR = config.ARCHIVE_COLD_DIR
    config.ensure_dirs()
    return tmp


def test_write_events_idempotent():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = archive.annotate_routes(df)
        n1 = archive.write_events(df.copy())
        n2 = archive.write_events(df.copy())
        assert sum(n1.values()) == len(df)
        assert sum(n2.values()) == 0  # nothing new on second write

        all_back = archive.read_hot()
        assert len(all_back) == len(df)
        # Verify route_template was annotated
        assert (all_back["route_template"] != "_unknown").any()
    finally:
        shutil.rmtree(tmp)


def test_write_events_dedupes_within_batch():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL + ALL)  # duplicate every line
        df = archive.annotate_routes(df)
        archive.write_events(df)
        all_back = archive.read_hot()
        assert len(all_back) == len(ALL)
    finally:
        shutil.rmtree(tmp)


def test_compress_cold_skips_unannotated():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = archive.annotate_routes(df)
        # Backdate to 100 days ago.
        df["t"] = df["t"] - pd.Timedelta(days=100)
        archive.write_events(df)
        # Cold compaction should refuse since session_id/ua_family/etc. missing.
        result = archive.compress_cold(today=dt.date.today())
        assert any("skipped" in k for k in result)
        # Hot file still present.
        assert archive.read_hot().shape[0] == len(df)
    finally:
        shutil.rmtree(tmp)


def test_compress_cold_compacts_when_annotated():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = archive.annotate_routes(df)
        df["t"] = df["t"] - pd.Timedelta(days=100)
        # Manually inject required cold columns.
        df["session_id"] = "s0"
        df["ua_family"] = "test"
        df["bot_class"] = "unknown"
        df["referrer_domain"] = ""
        archive.write_events(df)
        n_before = len(archive.read_hot())
        result = archive.compress_cold(today=dt.date.today())
        assert sum(v for k, v in result.items() if "skipped" not in k) >= 1
        # Hot rows for compacted day are gone.
        assert archive.read_hot().shape[0] == 0
        # Cold rows have all expected cold columns and same row count.
        cold = archive.read_cold()
        assert set(COLD_COLUMNS).issubset(cold.columns)
        assert len(cold) == n_before
    finally:
        shutil.rmtree(tmp)
