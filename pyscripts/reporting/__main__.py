import argparse
import datetime as dt
import json
import sys
import time
import traceback
from itertools import batched
from pathlib import Path

import polars as pl

from . import (
    aggregate,
    archive,
    config,
    parse,
    paths,
    pull,
    render,
    sessions,
    state,
    timing,
)
from .classify import annotate_events, classify_sessions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyscripts.reporting")
    parser.add_argument("--no-pull", action="store_true", help="Skip pulling new logs.")
    parser.add_argument(
        "--no-publish", action="store_true", help="Skip pushing to gh-pages."
    )
    parser.add_argument(
        "--render-only", action="store_true", help="Skip pull + archive + aggregate."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Pull + parse, no writes."
    )
    parser.add_argument(
        "--reclassify-all",
        action="store_true",
        help="Re-run classification on all hot archive days, rebuild aggregates, then render.",
    )
    parser.add_argument(
        "--mode",
        choices=("local", "public", "both"),
        default="public",
        help="Which site variant to render.",
    )
    args = parser.parse_args(argv)

    config.ensure_dirs()
    run_log = _open_run_log()
    run_record = {"ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")}
    started = time.time()
    try:
        if args.dry_run:
            _do_dry_run(run_record)
        elif args.render_only:
            _do_render(args.mode, args.no_publish, run_record)
        elif args.reclassify_all:
            _do_reclassify_all(run_record)
            _do_render(args.mode, args.no_publish, run_record)
        else:
            if not args.no_pull:
                affected_dates = _do_pull_and_archive(run_record)
                _do_aggregate(run_record, affected_dates)
            else:
                _do_aggregate(run_record, None)
            _do_render(args.mode, args.no_publish, run_record)
        run_record["status"] = "ok"
    except Exception as exc:
        run_record["status"] = "error"
        run_record["error"] = repr(exc)
        run_record["trace"] = traceback.format_exc()
        run_log(run_record)
        raise
    finally:
        run_record["duration_s"] = round(time.time() - started, 2)
        run_record["timings"] = timing.get()
        run_log(run_record)
    return 0


def _open_run_log():
    today = dt.date.today().isoformat()
    log_path = config.RUN_LOGS_DIR / f"run-{today}.log"

    def write(record: dict) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
        print(json.dumps(record, default=str), file=sys.stderr)

    return write


_RECLASSIFY_BATCH = 7


def _do_reclassify_all(rec: dict) -> None:
    all_dates = archive.list_hot_dates()
    n_sessions = 0
    aggregate.purge_sessions()
    with timing.timed("reclassify"):
        for batch in batched(all_dates, _RECLASSIFY_BATCH):
            df = archive.read_hot(date_from=batch[0], date_to=batch[-1])
            if df.is_empty() or "session_id" not in df.columns:
                continue
            sess_df = classify_sessions(df)
            annotated = annotate_events(df, sess_df)
            for d in batch:
                day_df = annotated.filter(pl.col("t").dt.date() == d)
                if not day_df.is_empty():
                    archive.rewrite_hot(d, day_df)
            n_sessions += len(sess_df)
            aggregate.update_sessions(sess_df)
    rec["reclassified_dates"] = len(all_dates)
    rec["reclassified_sessions"] = n_sessions
    with timing.timed("aggregate"):
        rec["aggregates"] = aggregate.rebuild()


def _do_dry_run(rec: dict) -> None:
    s = state.load()
    fetched = pull.fetch_new_lines(s)
    df, fail = parse.parse_lines(fetched.lines)
    rec["lines_fetched"] = len(fetched.lines)
    rec["events_parsed"] = len(df)
    rec["parse_failures"] = fail
    rec["rotated"] = fetched.rotated
    if not df.is_empty():
        rec["t_min"] = str(df["t"].min())
        rec["t_max"] = str(df["t"].max())
    unmatched = (
        paths.collect_unmatched(df["path"].to_list()) if not df.is_empty() else {}
    )
    rec["top_unmatched"] = list(unmatched.most_common(20))


def _do_pull_and_archive(rec: dict) -> list[dt.date]:
    s = state.load()

    with timing.timed("pull.fetch"):
        fetched = pull.fetch_new_lines(s)
    with timing.timed("pull.parse"):
        df, fail = parse.parse_lines(fetched.lines)

    rec["lines_fetched"] = len(fetched.lines)
    rec["events_parsed"] = len(df)
    rec["parse_failures"] = fail
    rec["rotated"] = fetched.rotated

    if df.is_empty():
        s.last_inode = fetched.new_inode
        s.last_size = fetched.new_size
        s.last_run = state.now_iso()
        s.lines_pulled_last_run = len(fetched.lines)
        s.parse_failures_last_run = fail
        state.save(s)
        return []

    with timing.timed("pull.annotate_routes"):
        df = archive.annotate_routes(df)
    with timing.timed("pull.assign_sessions"):
        df = sessions.assign_sessions(df)
    with timing.timed("pull.classify_sessions"):
        sess_df = classify_sessions(df)
    with timing.timed("pull.annotate_events"):
        aggregate.update_sessions(sess_df)
        df = annotate_events(df, sess_df)
    with timing.timed("pull.write_events"):
        written = archive.write_events(df)
    with timing.timed("pull.compress_cold"):
        cold = archive.compress_cold(today=dt.date.today())

    if cold:
        rec["cold_compaction"] = cold
    unmatched = paths.collect_unmatched(df["path"].to_list())
    if unmatched:
        rec["top_unmatched"] = list(unmatched.most_common(20))

    s.last_inode = fetched.new_inode
    s.last_size = fetched.new_size
    s.last_event_ts = str(df["t"].max())
    s.last_run = state.now_iso()
    s.salt_date = state.today_iso()
    s.lines_pulled_last_run = len(fetched.lines)
    s.parse_failures_last_run = fail
    state.save(s)
    rec["written_per_day"] = written
    return [dt.date.fromisoformat(d) for d in written]


def _do_aggregate(rec: dict, affected_dates: list[dt.date] | None) -> None:
    with timing.timed("aggregate"):
        if affected_dates is None:
            res = aggregate.rebuild()
        elif not affected_dates:
            rec["aggregates"] = {"skipped": True}
            return
        elif not aggregate.hourly_exists():
            res = aggregate.rebuild()
        else:
            res = aggregate.update(affected_dates)
    rec["aggregates"] = res


def _do_render(mode: str, no_publish: bool, rec: dict) -> None:
    rendered = []
    if mode in ("local", "both"):
        render.render_all("local")
        rendered.append("local")
    if mode in ("public", "both"):
        render.render_all("public")
        rendered.append("public")
    rec["rendered"] = rendered

    if "public" in rendered and not no_publish:
        from . import publish

        with timing.timed("publish"):
            try:
                publish.publish_to_ghpages(Path("."))
                rec["published"] = True
            except Exception as exc:
                rec["published"] = False
                rec["publish_error"] = repr(exc)


if __name__ == "__main__":
    sys.exit(main())
