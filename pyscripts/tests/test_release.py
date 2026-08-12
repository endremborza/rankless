import subprocess
from pathlib import Path

import pytest

from pyscripts import release


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
    for rel in [f"{p}/keep.txt" for p in release.ARTIFACT_PATHS] + ["hand_written.rs"]:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("v1")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    _git(repo, "push", "-u", "origin", "main")
    return repo


def test_commit_artifacts_scopes_to_generated_paths(repo: Path) -> None:
    (repo / release.ARTIFACT_PATHS[0] / "keep.txt").write_text("v2")
    (repo / release.ARTIFACT_PATHS[1] / "new.json").write_text("{}")
    (repo / "hand_written.rs").write_text("v2")

    release.commit_artifacts(cwd=repo)

    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(committed) == sorted(
        [
            f"{release.ARTIFACT_PATHS[0]}/keep.txt",
            f"{release.ARTIFACT_PATHS[1]}/new.json",
        ]
    )
    # hand-written change untouched, commit pushed
    assert "hand_written.rs" in _git(repo, "status", "--porcelain")
    assert _git(repo, "rev-parse", "HEAD") == _git(repo, "rev-parse", "origin/main")


def test_commit_artifacts_aborts_on_staged_junk(repo: Path) -> None:
    (repo / "hand_written.rs").write_text("v2")
    _git(repo, "add", "hand_written.rs")
    with pytest.raises(SystemExit, match="staged"):
        release.commit_artifacts(cwd=repo)


def test_commit_artifacts_noop_when_clean(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    release.commit_artifacts(cwd=repo)
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

    (repo / release.ARTIFACT_PATHS[0] / "keep.txt").write_text("v2")
    with pytest.raises(SystemExit, match="behind"):
        release.commit_artifacts(cwd=repo)


def test_pipeline_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "LOCK_PATH", tmp_path / "lock")
    with release.pipeline_lock():
        with pytest.raises(SystemExit, match="lock held"):
            with release.pipeline_lock():
                pass
    assert not release.LOCK_PATH.exists()

    # a dead holder's lock is stolen
    dead = subprocess.Popen(["true"])
    dead.wait()
    release.LOCK_PATH.write_text(str(dead.pid))
    with release.pipeline_lock():
        assert release.LOCK_PATH.read_text() != str(dead.pid)
