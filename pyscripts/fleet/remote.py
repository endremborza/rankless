"""Command transport for fleet machines: one surface over ssh and local exec.

Everything the driver, preflight and calibrator do on a box goes through a
`Host`, so behavior is uniform (profile sourcing, error shape, log prefixes)
and tests can substitute a fake by overriding `out`/`stream`.
"""

import subprocess

SSH_OPTS = (
    "-o",
    "ServerAliveInterval=60",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
)


class Host:
    """One machine; host=None means this one (runs through bash, not ssh)."""

    def __init__(self, name: str, host: str | None):
        self.name = name
        self.host = host

    def out(self, comm: str, check: bool = True) -> str:
        r = subprocess.run(self._argv(comm), capture_output=True, text=True)
        if check and r.returncode != 0:
            raise RuntimeError(f"[{self.name}] `{comm}` failed: {r.stderr.strip()}")
        return r.stdout

    def stream(self, comm: str) -> None:
        stream(self._argv(comm), self.name)

    def _argv(self, comm: str) -> list[str]:
        if self.host is None:
            return ["bash", "-c", comm]
        return ["ssh", *SSH_OPTS, self.host, f"source ~/.profile; {comm}"]


def rsync(
    src: str,
    dst: str,
    prefix: str,
    excludes: tuple[str, ...] = (),
    delete: bool = False,
) -> None:
    cmd = ["rsync", "-a", *(f"--exclude={e}" for e in excludes)]
    if delete:
        cmd.append("--delete")
    stream([*cmd, src, dst], prefix)


def stream(cmd: list[str], prefix: str) -> None:
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(f"[{prefix}] {line}", end="")
    if proc.wait() != 0:
        raise RuntimeError(
            f"[{prefix}] `{' '.join(cmd[:3])}…` exited {proc.returncode}"
        )


def log(name: str, msg: str) -> None:
    print(f"[{name}] {msg}", flush=True)
