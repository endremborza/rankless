import gzip
import subprocess
from dataclasses import dataclass

from .config import LIVE_SSH_ID, NGINX_LOG, NGINX_LOG_ROTATED
from .state import State


@dataclass
class FetchResult:
    lines: list[str]
    new_inode: int
    new_size: int
    rotated: bool


def fetch_new_lines(state: State, ssh_host: str = LIVE_SSH_ID) -> FetchResult:
    """SSH-pull new log lines starting from state.last_size byte offset.

    Handles rotation: if the inode changed, also pulls the unread tail of
    `${NGINX_LOG}.1` (the rotated file) before reading the new active log.
    """
    inode, size = _stat(ssh_host, NGINX_LOG)
    rotated = state.last_inode and inode != state.last_inode

    if state.last_inode == 0:
        # First run ever: only ingest the most recent ~200k lines so we don't
        # try to fetch a multi-gigabyte log.
        lines = _ssh_lines(ssh_host, f"tail -n 200000 {NGINX_LOG}")
        return FetchResult(lines=lines, new_inode=inode, new_size=size, rotated=False)

    if rotated:
        rot_inode, rot_size = _stat_or_none(ssh_host, NGINX_LOG_ROTATED)
        old_tail: list[str] = []
        if rot_inode == state.last_inode and rot_size and rot_size > state.last_size:
            old_tail = _ssh_lines(
                ssh_host,
                f"tail -c +{state.last_size + 1} {NGINX_LOG_ROTATED}",
            )
        new_full = _ssh_lines(ssh_host, f"cat {NGINX_LOG}")
        return FetchResult(
            lines=old_tail + new_full,
            new_inode=inode,
            new_size=size,
            rotated=True,
        )

    if size < state.last_size:
        # Truncated without rotation; treat as fresh.
        new_full = _ssh_lines(ssh_host, f"cat {NGINX_LOG}")
        return FetchResult(lines=new_full, new_inode=inode, new_size=size, rotated=True)

    if size == state.last_size:
        return FetchResult(lines=[], new_inode=inode, new_size=size, rotated=False)

    tail = _ssh_lines(ssh_host, f"tail -c +{state.last_size + 1} {NGINX_LOG}")
    return FetchResult(lines=tail, new_inode=inode, new_size=size, rotated=False)


def fetch_full_log(ssh_host: str = LIVE_SSH_ID) -> list[str]:
    """Pull the entire active access.log (gzip-compressed on the wire). One-off use
    for history surgery; the routine path is the incremental `fetch_new_lines`.

    Snapshots the log first so gzip sees a static file (the live log grows mid-read,
    which would otherwise make gzip exit non-zero and raise)."""
    snap = "/tmp/rl_access_snapshot.log"
    cmd = f"cp {NGINX_LOG} {snap} && gzip -cn {snap}; rm -f {snap}"
    raw = subprocess.check_output(
        ["ssh", "-o", "StrictHostKeyChecking=no", ssh_host, cmd],
    )
    return gzip.decompress(raw).decode("utf-8", "replace").split("\n")


def _ssh(host: str, cmd: str) -> str:
    return subprocess.check_output(
        ["ssh", "-o", "StrictHostKeyChecking=no", host, cmd],
        text=True,
    )


def _ssh_lines(host: str, cmd: str) -> list[str]:
    out = _ssh(host, cmd)
    return out.split("\n")


def _stat(host: str, path: str) -> tuple[int, int]:
    out = _ssh(host, f"stat -c '%i %s' {path}").strip().split()
    return int(out[0]), int(out[1])


def _stat_or_none(host: str, path: str) -> tuple[int | None, int | None]:
    try:
        return _stat(host, path)
    except subprocess.CalledProcessError:
        return None, None
