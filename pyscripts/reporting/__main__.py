import argparse
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path

from . import aggregate, archive, config, parse, paths, pull, render, sessions, state
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
        "--mode",
        choices=("local", "public", "both"),
        default="both",
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
        else:
            if not args.no_pull:
                _do_pull_and_archive(run_record)
            _do_aggregate(run_record)
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


def _do_dry_run(rec: dict) -> None:
    s = state.load()
    fetched = pull.fetch_new_lines(s)
    df, fail = parse.parse_lines(fetched.lines)
    rec["lines_fetched"] = len(fetched.lines)
    rec["events_parsed"] = len(df)
    rec["parse_failures"] = fail
    rec["rotated"] = fetched.rotated
    if not df.empty:
        rec["t_min"] = str(df["t"].min())
        rec["t_max"] = str(df["t"].max())
    unmatched = paths.collect_unmatched(df["path"]) if not df.empty else {}
    rec["top_unmatched"] = list(unmatched.most_common(20))


def _do_pull_and_archive(rec: dict) -> None:
    s = state.load()
    fetched = pull.fetch_new_lines(s)
    df, fail = parse.parse_lines(fetched.lines)
    rec["lines_fetched"] = len(fetched.lines)
    rec["events_parsed"] = len(df)
    rec["parse_failures"] = fail
    rec["rotated"] = fetched.rotated
    if df.empty:
        s.last_inode = fetched.new_inode
        s.last_size = fetched.new_size
        s.last_run = state.now_iso()
        s.lines_pulled_last_run = len(fetched.lines)
        s.parse_failures_last_run = fail
        state.save(s)
        return

    df = archive.annotate_routes(df)
    df = sessions.assign_sessions(df)
    sess_df = classify_sessions(df)
    aggregate.write_sessions(sess_df)
    df = annotate_events(df, sess_df)
    written = archive.write_events(df)
    rec["written_per_day"] = written
    cold = archive.compress_cold(today=dt.date.today())
    if cold:
        rec["cold_compaction"] = cold

    unmatched = paths.collect_unmatched(df["path"])
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


def _do_aggregate(rec: dict) -> None:
    res = aggregate.rebuild()
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

        try:
            publish.publish_to_ghpages(Path("."))
            rec["published"] = True
        except Exception as exc:
            rec["published"] = False
            rec["publish_error"] = repr(exc)


if __name__ == "__main__":
    sys.exit(main())
