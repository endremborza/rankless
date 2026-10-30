"""The OpenAlex snapshot the pipeline reads, and the download of each new release.

A box that follows OpenAlex's releases sets `PREFIX_VAR`: the release of date D lands in the
directory `<prefix>D`, and the pipeline reads the newest of them, which `download` marks complete
once every part matches its entity's `manifest.json`. `SNAPSHOT_VAR` instead names one snapshot
directory (a dev box's nano, a test set, a pinned release) and wins when set. `to-csv` records the
snapshot it flattened beside the entity CSVs, which is what the release manifest names.

    uv run -m pyscripts snapshot download   # the newest release, unless it is complete here
    uv run -m pyscripts snapshot path       # the snapshot `to-csv` would read
    uv run -m pyscripts snapshot to-csv     # flatten it into $OA_ROOT's entity CSVs
"""

import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

from ccl_science_data.gen import StowC
from dotenv import load_dotenv
from protocli import Dispatcher

load_dotenv()

SNAPSHOT_VAR = "OA_SNAPSHOT"
PREFIX_VAR = "OA_SNAPSHOT_PREFIX"
BUCKET = "s3://openalex"
RELEASE_NOTES_URL = "https://openalex.s3.amazonaws.com/RELEASE_NOTES.txt"
SYNC_EXCLUDES = ("legacy-data/*", "data/parquet/*")
JSONL = Path("data", "jsonl")
MANIFEST_NAME = "manifest.json"
COMPLETE_NAME = ".complete"
RECORD_NAME = "snapshot.json"
SHOWN_MISMATCHES = 20

RELEASE_RE = re.compile(r"^RELEASE (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NAME_DATE_RE = re.compile(r"\d{4}-\d{2}(-\d{2})?")


def latest_release(notes: str) -> str:
    """The newest release date the release notes list."""
    dates = RELEASE_RE.findall(notes)
    if not dates:
        raise SystemExit(f"no release listed in {RELEASE_NOTES_URL}")
    return max(dates)


def release_notes(notes: str, date: str) -> str:
    """The release notes' entry for `date`."""
    return notes.split(f"RELEASE {date}", 1)[1].split("\nRELEASE ", 1)[0].strip()


def releases(prefix: str) -> list[Path]:
    """The release directories under `prefix`, oldest first."""
    base = Path(prefix)
    return sorted(
        (
            d
            for d in base.parent.glob(f"{base.name}*")
            if d.is_dir() and DATE_RE.fullmatch(d.name[len(base.name) :])
        ),
        key=lambda d: d.name,
    )


def current() -> Path:
    """The snapshot the pipeline reads: `SNAPSHOT_VAR` when set, else the newest release."""
    if one := os.environ.get(SNAPSHOT_VAR):
        return Path(one)
    found = releases(_prefix())
    if not found:
        raise SystemExit(f"no release under {_prefix()}: `make download-snapshot`")
    if not (found[-1] / COMPLETE_NAME).exists():
        raise SystemExit(
            f"{found[-1]} is not complete: `make download-snapshot` resumes it"
        )
    return found[-1]


def mismatches(snapshot: Path) -> list[str]:
    """Where the downloaded parts differ from their entities' manifests."""
    jsonl = snapshot / JSONL
    entities = (
        sorted(d for d in jsonl.iterdir() if d.is_dir()) if jsonl.is_dir() else []
    )
    if not entities:
        return [f"no entity under {jsonl}"]
    out = []
    for entity in entities:
        manifest = entity / MANIFEST_NAME
        if not manifest.exists():
            out.append(f"{manifest} missing")
            continue
        listed = {
            snapshot / f["url"].removeprefix(f"{BUCKET}/"): f["meta"]["content_length"]
            for f in json.loads(manifest.read_text())["files"]
        }
        for part, size in listed.items():
            if not part.exists():
                out.append(f"{part} missing")
            elif (got := part.stat().st_size) != size:
                out.append(f"{part}: {got} of {size} bytes")
        out += [
            f"{part} is in no manifest"
            for part in entity.glob("updated_date=*/*.gz")
            if part not in listed
        ]
    return out


def download() -> None:
    """Download the newest release the OpenAlex release notes list, unless it is complete here."""
    notes = _fetch(RELEASE_NOTES_URL)
    date = latest_release(notes)
    target = Path(_prefix() + date)
    if (target / COMPLETE_NAME).exists():
        print(f"release {date} is complete in {target}: nothing to download")
        return
    print(f"release {date} → {target}\n{release_notes(notes, date)}\n")
    excludes = [arg for pattern in SYNC_EXCLUDES for arg in ("--exclude", pattern)]
    subprocess.run(
        ["aws", "s3", "sync", BUCKET, str(target), "--no-sign-request", *excludes],
        check=True,
    )
    if found := mismatches(target):
        raise SystemExit(
            f"{target} differs from its manifests in {len(found)} place(s), rerun to resume:\n"
            + "\n".join(found[:SHOWN_MISMATCHES])
        )
    (target / COMPLETE_NAME).write_text(f"{date}\n")
    print(f"release {date} complete in {target}")


def path() -> None:
    """Print the snapshot `to-csv` would read."""
    print(current())


def to_csv() -> None:
    """Flatten the snapshot into $OA_ROOT's entity CSVs, recording which snapshot they are."""
    snapshot, root = current(), Path(os.environ["OA_ROOT"])
    subprocess.run(
        ["cargo", "run", "--release", "-p", "rankless-rs", "--", "to-csv"]
        + [str(root), str(snapshot / JSONL)],
        check=True,
    )
    record(root, snapshot)


def record(root: Path, snapshot: Path) -> None:
    date = NAME_DATE_RE.search(snapshot.name)
    described = {"name": snapshot.name, "date": date[0] if date else None}
    (root / StowC.entity_csvs / RECORD_NAME).write_text(json.dumps(described) + "\n")


def recorded(root: Path) -> dict[str, str | None]:
    """The snapshot the entity CSVs under `root` were flattened from."""
    file = root / StowC.entity_csvs / RECORD_NAME
    if not file.exists():
        raise SystemExit(f"{file} missing: rerun `make to-csv`")
    return json.loads(file.read_text())


def _prefix() -> str:
    prefix = os.environ.get(PREFIX_VAR)
    if not prefix:
        raise SystemExit(
            f"set {PREFIX_VAR}, or {SNAPSHOT_VAR} for one snapshot directory"
        )
    return prefix


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()


_dispatcher = Dispatcher(
    "pyscripts snapshot", {"download": download, "path": path, "to-csv": to_csv}
)
