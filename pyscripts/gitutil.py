"""Local-git plumbing shared by the recalc/deploy/fleet tooling."""

import subprocess
from pathlib import Path

# Must match rankless_server/build.rs's GIT_COMMIT bake (12-char short form).
HEAD_CMD = "git rev-parse --short=12 HEAD"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def git_out(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def git_lines(cwd: Path, *args: str) -> list[str]:
    return [line for line in git_out(cwd, *args).splitlines() if line.strip()]


def head_commit() -> str:
    return subprocess.check_output(HEAD_CMD.split(), text=True).strip()


def current_branch(cwd: Path = Path(".")) -> str:
    return git_out(cwd, "branch", "--show-current")


def assert_pushed(cwd: Path = Path(".")) -> None:
    branch = current_branch(cwd)
    git(cwd, "fetch", "origin", branch)
    if git_out(cwd, "rev-parse", "HEAD") != git_out(
        cwd, "rev-parse", f"origin/{branch}"
    ):
        raise SystemExit(f"HEAD != origin/{branch} — push (or pull) first")
