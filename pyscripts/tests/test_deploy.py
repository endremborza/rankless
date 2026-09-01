import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyscripts import deploy, migration_scripts, userdb
from pyscripts.fleet import manifest

SS_TUNNEL = (
    'LISTEN 0 128 127.0.0.1:3038 0.0.0.0:* users:(("sshd",pid=1201,fd=9))\n'
    'LISTEN 0 128 [::1]:3038 [::]:* users:(("sshd",pid=1201,fd=8))\n'
)
SS_OWN = 'LISTEN 0 4096 127.0.0.1:3038 0.0.0.0:* users:(("rankless-server",pid=2210,fd=12))\n'


def _box(ss_output: str):
    return SimpleNamespace(
        ssh=SimpleNamespace(run=lambda comm: ss_output, full_host="ubuntu@box")
    )


def test_listeners_name_the_socket_owner() -> None:
    assert deploy.listeners(SS_TUNNEL, 3038) == [
        ("127.0.0.1:3038", "sshd"),
        ("[::1]:3038", "sshd"),
    ]
    assert deploy.listeners(SS_OWN, 3038) == [("127.0.0.1:3038", "rankless-server")]
    assert deploy.listeners(SS_OWN, 3039) == []
    assert deploy.listeners("LISTEN 0 128 127.0.0.1:3038 0.0.0.0:*\n", 3038) == [
        ("127.0.0.1:3038", "")
    ]


def test_backend_port_gate_rejects_a_tunnel_and_an_empty_port() -> None:
    deploy.Transper.assert_backend_owns_port(_box(SS_OWN))
    with pytest.raises(SystemExit, match="sshd"):
        deploy.Transper.assert_backend_owns_port(_box(SS_TUNNEL))
    with pytest.raises(SystemExit, match="nobody"):
        deploy.Transper.assert_backend_owns_port(_box(""))


def test_push_data_is_the_fleet_definition() -> None:
    calls = []

    def rsync(src, dst, excludes=(), delete=False):
        calls.append((src, dst, tuple(excludes), delete))

    manifest.push_data(rsync, "/oa", "box:/data")
    assert calls == [
        ("/oa/", "box:/data/", manifest.PUSH_EXCLUDES, True),
        ("/oa/cache/", "box:/data/cache/", (), False),
    ]
    # the digest set ships whole: ledger + stamp ride along, per-box dirs stay put
    assert "user-ledger" not in manifest.PUSH_EXCLUDES
    assert manifest.STAMP_NAME not in manifest.PUSH_EXCLUDES
    assert "cache" in manifest.PUSH_EXCLUDES


def test_migration_scripts_are_enumerated_in_order() -> None:
    names = migration_scripts.module_names()
    assert names == sorted(names) and "__init__" not in names
    for name in names:
        assert (Path(migration_scripts.__file__).parent / f"{name}.py").exists()


def test_run_migrations_runs_each_script_once_a_db_exists() -> None:
    ran: list[str] = []
    box = SimpleNamespace(
        ssh=SimpleNamespace(remote_exists=lambda p: False),
        deploy_dir="/home/ubuntu/rankless-deploy",
        venv_python="/venv/bin/python",
        _depcomm=ran.append,
    )
    deploy.Transper.run_migrations(box)
    assert ran == []
    box.ssh.remote_exists = lambda p: True
    deploy.Transper.run_migrations(box)
    assert ran == [
        f"/venv/bin/python -m pyscripts.migration_scripts.{n}"
        for n in migration_scripts.module_names()
    ]


def test_user_count(tmp_path: Path) -> None:
    db = tmp_path / "u.sqlite"
    assert userdb.user_count(str(db)) == 0
    assert not db.exists()
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE users (orcid TEXT)")
    con.commit()
    assert userdb.user_count(str(db)) == 0
    con.executemany("INSERT INTO users VALUES (?)", [("a",), ("b",)])
    con.commit()
    con.close()
    assert userdb.user_count(str(db)) == 2
