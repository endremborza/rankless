import json
import subprocess
from pathlib import Path

import pytest

from pyscripts import recalc
from pyscripts.fleet.manifest import STAMP_NAME


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "remote", "add", "origin", str(origin))
    for rel in [f"{p}/keep.txt" for p in recalc.ARTIFACT_PATHS] + ["hand_written.rs"]:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("v1")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    _git(repo, "push", "-u", "origin", "main")
    return repo


def test_commit_artifacts_scopes_to_generated_paths(repo: Path) -> None:
    (repo / recalc.ARTIFACT_PATHS[0] / "keep.txt").write_text("v2")
    (repo / recalc.ARTIFACT_PATHS[1] / "new.json").write_text("{}")
    (repo / "hand_written.rs").write_text("v2")

    recalc.commit_artifacts(cwd=repo)

    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(committed) == sorted(
        [
            f"{recalc.ARTIFACT_PATHS[0]}/keep.txt",
            f"{recalc.ARTIFACT_PATHS[1]}/new.json",
        ]
    )
    # hand-written change untouched, commit pushed
    assert "hand_written.rs" in _git(repo, "status", "--porcelain")
    assert _git(repo, "rev-parse", "HEAD") == _git(repo, "rev-parse", "origin/main")


def test_commit_artifacts_aborts_on_staged_junk(repo: Path) -> None:
    (repo / "hand_written.rs").write_text("v2")
    _git(repo, "add", "hand_written.rs")
    with pytest.raises(SystemExit, match="staged"):
        recalc.commit_artifacts(cwd=repo)


def test_commit_artifacts_noop_when_clean(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    recalc.commit_artifacts(cwd=repo)
    assert _git(repo, "rev-parse", "HEAD") == head


def test_commit_artifacts_aborts_when_behind(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", str(tmp_path / "origin.git"), str(other)], check=True
    )
    _git(other, "config", "user.email", "o@o.o")
    _git(other, "config", "user.name", "o")
    (other / "hand_written.rs").write_text("upstream")
    _git(other, "commit", "-am", "upstream")
    _git(other, "push")

    (repo / recalc.ARTIFACT_PATHS[0] / "keep.txt").write_text("v2")
    with pytest.raises(SystemExit, match="behind"):
        recalc.commit_artifacts(cwd=repo)


def test_pipeline_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recalc, "LOCK_PATH", tmp_path / "lock")
    with recalc.pipeline_lock():
        with pytest.raises(SystemExit, match="lock held"):
            with recalc.pipeline_lock():
                pass
    assert not recalc.LOCK_PATH.exists()

    # a dead holder's lock is stolen
    dead = subprocess.Popen(["true"])
    dead.wait()
    recalc.LOCK_PATH.write_text(str(dead.pid))
    with recalc.pipeline_lock():
        assert recalc.LOCK_PATH.read_text() != str(dead.pid)


def test_deploy_primitives_derived() -> None:
    from pyscripts import deploy

    prims = deploy.primitives()
    assert {"new_large_alpha", "merge_db_from_live", "ship_alpha", "promote"} <= set(
        prims
    )
    # helpers with required args, privates, and the shim itself stay out
    assert not {"run_logged", "primitives", "_last_vns"} & set(prims)


def _seed_sidecars(root: Path, run_id: str = "2026-08-12T10:00:00Z") -> None:
    ul = root / "user-ledger"
    ul.mkdir(parents=True)
    (ul / "snapshot_manifest.json").write_text(
        json.dumps({"run_id": run_id, "event_ids": [1, 2, 3], "sources": {"site": 3}})
    )
    (ul / "applied_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "applied_keys": [
                    "0000-1|disown_paper|aa",
                    "0000-1|merge_papers|bb",
                    "0000-2|disown_paper|cc",
                ],
                "skipped": [
                    {
                        "key": "0000-3|claim_paper|dd",
                        "reason": "claimant_not_attributed",
                    },
                    {
                        "key": "0000-4|merge_authors|ee",
                        "reason": "oa_id_not_in_dataset",
                    },
                    {
                        "key": "0000-5|merge_authors|ff",
                        "reason": "oa_id_not_in_dataset",
                    },
                ],
            }
        )
    )
    (ul / "forced_works.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "cohort": 2,
                "forced_total": 40,
                "outside_standard": 12,
                "outside_type": 9,
                "outside_citations": 5,
                "claim_auto": 1,
                "claim_merged": 0,
                "author_rescues": 1,
                "outside_wids": [3, 5, 8],
            }
        )
    )
    (root / STAMP_NAME).write_text(f"{run_id}:abcdef123456\n")
    for step, entities in (
        ("10", {"works": 100}),
        ("11", {"works": 80}),
        ("20", {"authors": 7}),
    ):
        d = root / "filter-steps" / step
        d.mkdir(parents=True)
        for name, n in entities.items():
            (d / name).write_bytes(b"\0" * 8 * n)


def test_release_manifest_assembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_sidecars(tmp_path)
    monkeypatch.setenv("OA_SNAPSHOT", "/somewhere/openalex-snapshot-2026-06")
    monkeypatch.setenv("RANKLESS_ENV", "mini")

    out = recalc.write_release_manifest(tmp_path)
    assert out == tmp_path / "releases" / "2026-08-12T10:00:00Z.json"
    m = json.loads(out.read_text())
    assert m == json.loads((tmp_path / "releases" / "release.json").read_text())

    assert m["stamp"] == "2026-08-12T10:00:00Z:abcdef123456"
    assert m["rankless_env"] == "mini"
    assert len(m["git_commit"]) == 12
    assert m["snapshot"] == {"name": "openalex-snapshot-2026-06", "date": "2026-06"}
    assert m["ledger"] == {"site": 3}
    assert m["applied"] == {"disown_paper": 2, "merge_papers": 1}
    assert m["skipped"] == {
        "claimant_not_attributed": 1,
        "oa_id_not_in_dataset": 2,
    }
    # aggregates only — the private wid list never enters the release record
    assert m["forced_works"] == {
        "cohort": 2,
        "forced_total": 40,
        "outside_standard": 12,
        "outside_type": 9,
        "outside_citations": 5,
        "claim_auto": 1,
        "claim_merged": 0,
        "author_rescues": 1,
    }
    assert m["filter_counts"]["10"]["works"] == {"in": None, "kept": 100}
    assert m["filter_counts"]["11"]["works"] == {"in": 100, "kept": 80}
    assert m["filter_counts"]["20"]["authors"] == {"in": None, "kept": 7}


def test_release_manifest_torn_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_sidecars(tmp_path)
    monkeypatch.setenv("OA_SNAPSHOT", "/somewhere/snap-2026-06")
    (tmp_path / STAMP_NAME).write_text("2000-01-01T00:00:00Z:000000000000\n")
    with pytest.raises(SystemExit, match="torn state"):
        recalc.build_release_manifest(tmp_path)
