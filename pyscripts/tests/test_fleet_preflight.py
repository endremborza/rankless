import json
import math

import pytest

from pyscripts.fleet import manifest, preflight
from pyscripts.fleet.config import Model, Worker
from pyscripts.fleet.preflight import GB, Primary
from pyscripts.fleet.remote import Host
from wire.rankless_server.consts import TREES_ONLY_FLAG

DIG = "f" * 64
PRIMARY = Primary(
    head="aaaabbbbcccc",
    rankless_env="full",
    oa_root="/p/data",
    stamp=f"r1:{DIG[: manifest.DIGEST_LEN]}",
    digest=DIG,
    data_size_gb=50.0,
    largest_file_gb=10.0,
)


class FakeHost(Host):
    """Canned responses keyed by first matching substring; records calls."""

    def __init__(self, responses: dict[str, str]):
        super().__init__("fake", "fake")
        self.responses = responses
        self.calls: list[str] = []

    def out(self, comm: str, check: bool = True) -> str:
        self.calls.append(comm)
        for key, val in self.responses.items():
            if key in comm:
                return val
        raise RuntimeError(f"no fake response for {comm!r}")


def _worker(**kwargs) -> Worker:
    defaults = dict(
        name="mid",
        host="mid-box",
        repo_dir="/home/x/rankless",
        data_root="/home/x/rankless-data",
        band=(14.0, 160.0),
        bins=[48.0],
        procs=[4, 1],
    )
    return Worker(**{**defaults, **kwargs})


def _green(w: Worker) -> dict[str, str]:
    return {
        "status --porcelain": "",
        "rev-parse": PRIMARY.head,
        ".env": f"OA_ROOT={w.data_root}\nRANKLESS_ENV=full\n",
        "df --output=avail": str(100 * GB),
        "du -sb": str(45 * GB),
        "free -b": str(200 * GB),
        "/stamp": PRIMARY.stamp,
        "sha256sum": DIG,
        "curl": json.dumps({"version": PRIMARY.version, "specs": {}}),
        "MemorySwapMax": f"MemoryMax={53 * GB}\nMemorySwapMax=0",
        "MainPID": "4242",
        "/cmdline": f"rankless-server\n{TREES_ONLY_FLAG}\n{w.data_root}",
    }


def _run_full(w: Worker, overrides: dict[str, str] | None = None) -> dict[str, bool]:
    host = FakeHost({**_green(w), **(overrides or {})})
    checks = preflight.full_checks(w, host, Model(), PRIMARY)
    return {c.name: c.ok for c in checks}


def test_all_green_passes_gate(capsys) -> None:
    w = _worker()
    host = FakeHost(_green(w))
    checks = preflight.full_checks(w, host, Model(), PRIMARY)
    assert [c.name for c in checks] == [
        "repo",
        "env",
        "disk",
        "memory",
        "stamp",
        "data",
        "version",
        "unit",
        "trees",
    ]
    preflight.gate(checks)  # must not raise
    assert f"all {len(checks)} checks passed" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("override", "failing"),
    [
        ({"status --porcelain": " M rankless_rs/src/lib.rs"}, "repo"),
        ({".env": "OA_ROOT=/somewhere/else\nRANKLESS_ENV=full"}, "env"),
        ({".env": "OA_ROOT=/home/x/rankless-data\nRANKLESS_ENV=mini"}, "env"),
        (
            {".env": "OA_ROOT=/home/x/rankless-data\nRANKLESS_ENV=full\nBIG_LIMIT=320"},
            "env",
        ),
        ({"df --output=avail": str(4 * GB)}, "disk"),
        ({"free -b": str(64 * GB)}, "memory"),
        ({"/stamp": "r0:" + "0" * manifest.DIGEST_LEN}, "stamp"),
        ({"sha256sum": "0" * 64}, "data"),
        ({"curl": json.dumps({"version": "bbbb|full|r1:ff", "specs": {}})}, "version"),
        ({"MemorySwapMax": "MemoryMax=infinity\nMemorySwapMax=infinity"}, "unit"),
        ({"MemorySwapMax": f"MemoryMax={53 * GB}\nMemorySwapMax=infinity"}, "unit"),
        ({"/cmdline": "rankless-server\n/home/x/rankless-data"}, "trees"),
    ],
)
def test_single_failure_isolated(override: dict, failing: str) -> None:
    oks = _run_full(_worker(), override)
    assert not oks.pop(failing)
    assert all(oks.values()), f"unexpected extra failures: {oks}"


def test_env_parse_tolerates_shell_syntax() -> None:
    env = (
        'export OA_ROOT="/home/x/rankless-data"\n'
        "# stale knobs live in comments without failing\n"
        "RANKLESS_ENV='full'\n"
        "RL_LIVE_IP=1.2.3.4\n"  # live deploy var, not a stale cache knob
    )
    assert _run_full(_worker(), {".env": env})["env"]


def test_push_needs_the_delta_plus_one_file_in_flight() -> None:
    # 45G on the box, 50G to push: the 5G delta alone is not enough — rsync
    # writes each replacement beside the old file and renames, so the largest
    # file (10G) is in flight on top, before the 5G margin.
    assert not _run_full(_worker(), {"df --output=avail": str(12 * GB)})["disk"]
    assert _run_full(_worker(), {"df --output=avail": str(21 * GB)})["disk"]


def test_gate_aborts_naming_failures(capsys) -> None:
    w = _worker()
    host = FakeHost({**_green(w), "curl": json.dumps({"version": "stale"})})
    checks = preflight.full_checks(w, host, Model(), PRIMARY)
    with pytest.raises(SystemExit, match="mid/version"):
        preflight.gate(checks)


def test_dead_host_fails_every_check_without_raising() -> None:
    w = _worker()
    checks = preflight.full_checks(w, FakeHost({}), Model(), PRIMARY)
    assert checks and all(not c.ok for c in checks)
    assert all("probe failed" in c.detail for c in checks)


def test_local_worker_check_set() -> None:
    w = Worker(name="local", band=(0.0, 14.0), bins=[6.0], procs=[16, 8])
    host = FakeHost(_green(w))
    pre = preflight.pre_checks(w, host, Model(), PRIMARY)
    post = preflight.post_checks(w, host, PRIMARY)
    assert [c.name for c in pre] == ["repo", "memory"]
    assert [c.name for c in post] == ["version", "unit", "trees"]


def test_dirty_local_driver_fails_repo() -> None:
    # The handshake's blind spot: a dirty driver runs code no commit describes
    # while reporting a matching GIT_COMMIT — the repo row must catch it.
    w = Worker(name="local", band=(0.0, 14.0), bins=[6.0], procs=[16, 8])
    host = FakeHost({**_green(w), "status --porcelain": " M src/lib/App.svelte"})
    oks = {c.name: c.ok for c in preflight.pre_checks(w, host, Model(), PRIMARY)}
    assert not oks["repo"] and oks["memory"]


def test_est_peak_uses_worst_bin() -> None:
    model = Model(mem_base_gb=37.0, gb_per_mcut=0.25)
    w = _worker()  # bins: (14,48]×4 procs, (48,160]×1 proc
    assert preflight.est_peak_gb(w, model) == 37.0 + max(4 * 48, 1 * 160) * 0.25


def test_est_peak_skips_the_open_bin() -> None:
    model = Model(mem_base_gb=37.0, gb_per_mcut=0.25)
    w = _worker(band=(14.0, math.inf))  # bins: (14,48]×4 procs, (48,∞)×1 proc
    assert preflight.est_peak_gb(w, model) == 37.0 + 4 * 48 * 0.25
    single = _worker(band=(160.0, math.inf), bins=[], procs=[1])
    assert preflight.est_peak_gb(single, model) == 37.0
