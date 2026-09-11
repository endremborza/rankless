import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyscripts import deploy, migration_scripts, userdb
from pyscripts.fleet import manifest
from pyscripts.fleet.remote import Host

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


def test_push_peak_is_the_largest_pushed_file(tmp_path: Path) -> None:
    local = Host("t", None)
    assert manifest.largest_file(local, str(tmp_path)) == 0
    for rel, size in [("a1/names", 3), ("top.bin", 10), ("cache/x/resp", 100)]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\0" * size)
    # the per-box cache is seeded additively, never replaced: it is not the peak
    assert manifest.largest_file(local, str(tmp_path)) == 10


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


def test_release_tree_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy, "LOCAL_REPO", tmp_path)
    with pytest.raises(SystemExit, match="holds no users"):
        deploy._assert_release_tree()
    db = tmp_path / deploy.paths.DB_REL
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE users (orcid TEXT)")
    con.execute("INSERT INTO users VALUES ('a')")
    con.commit()
    con.close()
    monkeypatch.setattr(migration_scripts, "module_names", lambda: ["add_x"])
    with pytest.raises(SystemExit, match="add_x"):
        deploy._assert_release_tree()
    monkeypatch.setattr(migration_scripts, "module_names", list)
    deploy._assert_release_tree()


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


def test_nginx_conf_keys_on_the_visitor_and_caps_renders() -> None:
    conf = deploy.render_nginx_conf(
        "server_name www.x;", "server_name api.x;", "www.x", "/c/be", "/c/fe"
    )
    for line in [
        "set_real_ip_from 104.16.0.0/13;",
        "set_real_ip_from 2606:4700::/32;",
        "real_ip_header CF-Connecting-IP;",
        "limit_req_zone $binary_remote_addr zone=pagelimit:10m rate=2r/s;",
        "limit_req_zone $binary_remote_addr zone=apilimit:10m rate=10r/s;",
        "limit_conn_zone $binary_remote_addr zone=pageconn:10m;",
        "limit_conn_zone $server_name zone=pageload:1m;",
        "limit_req zone=pagelimit burst=20 nodelay;",
        "limit_conn pageconn 8;",
        "limit_conn pageload 96;",
        "limit_conn_status 503;",
        "proxy_read_timeout 30s;",
        "proxy_next_upstream error invalid_header;",
        "proxy_next_upstream_tries 2;",
        "limit_req zone=apilimit burst=50 nodelay;",
        '"~MSIE [5-9]\\." 1;',
    ]:
        assert line in conf, line
    assert "baselimit" not in conf
    assert "$lt_" not in conf
    # hashed assets are cached and never draw on the page budget
    assets = conf[
        conf.index("location ^~ /_app/immutable/ {") : conf.index("location / {")
    ]
    assert "proxy_cache fe-cache;" in assets and "limit_" not in assets
    # the load-test lane swaps every key for the token maps
    lt = deploy.render_nginx_conf(
        "server_name www.x;", "server_name api.x;", "www.x", "/c/be", "/c/fe", "tok"
    )
    assert "limit_req_zone $lt_limit_key zone=pagelimit" in lt
    assert "limit_conn_zone $lt_global_key zone=pageload" in lt
    assert "proxy_no_cache $lt_skip_cache;" in lt
    # a slow worker is retried, never marked dead; the single backend keeps the default
    assert list(deploy.UpstreamConf([4200, 4201]).fe_servers()) == [
        "server 127.0.0.1:4200 max_fails=0;",
        "server 127.0.0.1:4201 max_fails=0;",
    ]
    assert (
        deploy.UpstreamConf([4200]).be_server()
        == f"server 127.0.0.1:{deploy.DEFAULT_RS_PORT};"
    )


def test_ops_plan_is_ordered_and_gated_on_the_spec() -> None:
    names = [s.name for s in deploy.OPS_STEPS]
    assert names.index("fe_units") < names.index("site")  # site reads the FE domain
    assert names.index("certs") < names.index("site")  # site conf names the cert files
    assert names.index("python_env") < names.index("mcp_units")
    full = deploy.BoxSpec("www.x", 12, backend=True)
    small = deploy.BoxSpec("alpha.x", 2, backend=False)
    assert dict((s.name, ok) for s, ok in deploy.ops_plan(full))["backend_unit"]
    assert not dict((s.name, ok) for s, ok in deploy.ops_plan(small))["backend_unit"]
    assert small.mcp_backend == "live" and full.mcp_backend == "local"
    assert [s.name for s, _ in deploy.ops_plan(full, "site")] == ["site"]
    with pytest.raises(SystemExit, match="unknown ops step"):
        deploy.ops_plan(full, "nope")


def test_apply_ops_explains_without_touching_the_box(capsys) -> None:
    class Untouchable:
        def __getattr__(self, name):
            raise AssertionError(f"explain touched the box: {name}")

    spec = deploy.BoxSpec("alpha.x", 2, backend=False)
    deploy.apply_ops(Untouchable(), spec, explain=True)
    out = capsys.readouterr().out.splitlines()
    assert len(out) == len(deploy.OPS_STEPS)
    assert any(line.startswith("skip backend_unit") for line in out)
    assert all(line.startswith(("ops ", "skip ")) for line in out)


def test_apply_ops_runs_the_applicable_steps_in_order() -> None:
    calls: list[str] = []
    steps = [
        deploy.BoxStep("a", "", lambda t, s: calls.append("a")),
        deploy.BoxStep("b", "", lambda t, s: calls.append("b"), when=lambda s: False),
        deploy.BoxStep("c", "", lambda t, s: calls.append("c")),
    ]
    spec = deploy.BoxSpec("alpha.x", 2, backend=False)
    orig = deploy.OPS_STEPS
    deploy.OPS_STEPS = steps
    try:
        deploy.apply_ops(None, spec)
        assert calls == ["a", "c"]
        deploy.apply_ops(None, spec, only="c")
        assert calls == ["a", "c", "c"]
    finally:
        deploy.OPS_STEPS = orig
