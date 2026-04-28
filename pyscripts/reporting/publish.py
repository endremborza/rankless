import subprocess
from pathlib import Path

from .config import GHPAGES_BRANCH, GHPAGES_REMOTE, GHPAGES_WORKTREE, SITE_PUBLIC_DIR


def publish_to_ghpages(repo_dir: Path = Path("."), commit_msg: str | None = None) -> None:
    """Push SITE_PUBLIC_DIR to the gh-pages branch via a worktree."""
    repo_dir = repo_dir.resolve()
    worktree = GHPAGES_WORKTREE
    _ensure_worktree(repo_dir, worktree)
    _git(repo_dir, "-C", worktree.as_posix(), "reset", "--hard")
    _clean_worktree(worktree)
    _rsync(SITE_PUBLIC_DIR, worktree)
    (worktree / ".nojekyll").touch()
    _git(repo_dir, "-C", worktree.as_posix(), "add", "-A")
    if not _has_changes(repo_dir, worktree):
        return
    msg = commit_msg or _default_msg()
    _git(repo_dir, "-C", worktree.as_posix(), "commit", "-m", msg)
    _git(repo_dir, "-C", worktree.as_posix(), "push", GHPAGES_REMOTE, GHPAGES_BRANCH)


def _ensure_worktree(repo: Path, worktree: Path) -> None:
    if worktree.exists() and (worktree / ".git").exists():
        return
    worktree.parent.mkdir(parents=True, exist_ok=True)
    remote_branch = f"{GHPAGES_REMOTE}/{GHPAGES_BRANCH}"
    has_remote_branch = (
        subprocess.run(
            ["git", "-C", repo.as_posix(), "ls-remote", "--exit-code",
             "--heads", GHPAGES_REMOTE, GHPAGES_BRANCH],
            capture_output=True,
        ).returncode
        == 0
    )
    if has_remote_branch:
        subprocess.run(
            ["git", "-C", repo.as_posix(), "fetch", GHPAGES_REMOTE, GHPAGES_BRANCH],
            check=True,
        )
        subprocess.run(
            [
                "git", "-C", repo.as_posix(),
                "worktree", "add", "-B", GHPAGES_BRANCH,
                worktree.as_posix(), remote_branch,
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                "git", "-C", repo.as_posix(),
                "worktree", "add", "--orphan",
                "-b", GHPAGES_BRANCH, worktree.as_posix(),
            ],
            check=True,
        )


def _clean_worktree(worktree: Path) -> None:
    for child in worktree.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            subprocess.run(["rm", "-rf", child.as_posix()], check=True)
        else:
            child.unlink()


def _rsync(src: Path, dst: Path) -> None:
    src_str = src.as_posix().rstrip("/") + "/"
    subprocess.run(["rsync", "-a", "--delete", "--exclude=.git", src_str, dst.as_posix()], check=True)


def _has_changes(repo: Path, worktree: Path) -> bool:
    out = subprocess.run(
        ["git", "-C", worktree.as_posix(), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    return bool(out.strip())


def _default_msg() -> str:
    import datetime as dt
    return "report " + dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], check=True)
