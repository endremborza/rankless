import datetime as dt
import os
import re
import shutil
import subprocess
import time
from functools import cache
from dataclasses import dataclass
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from pyscripts import mcp_db, paths, services

load_dotenv()

SERIVCE_DIR = ".config/systemd/user"
BUN_PATH = "/.bun/bin/bun"
SSL_ETC_DIR = "/etc/letsencrypt/live"
LOCAL_SSL_TAR = "ssl_dir.tar.gz"
AMI_IMG_CSV = "ami-imgs.csv"

MAIN_DOMAIN = "rankless.org"

APTS = [
    "curl",
    "unzip",
    "certbot",
    "build-essential",
    "python3-certbot-nginx",
    "nginx",
    "btop",
    "systemd-oomd",
    # rsvg-convert rasterizes the OG share cards at runtime; fontconfig (fc-cache) registers the
    # vendored brand fonts so the rasterizer uses them.
    "librsvg2-bin",
    "fontconfig",
]


def subd(sub):
    return f"{sub}.{MAIN_DOMAIN}"


ALPHA_DOMAIN = subd("alpha")
LIVE_DOMAIN = subd("www")
FW_DOMAIN = MAIN_DOMAIN
ALPHA_BACKEND = subd("alpha-api")
LIVE_BACKEND = subd("api")

FE_UPSTREAM = "rankless_frontend"
BE_UPSTREAM = "rankless_backend"

BE_URL_VAR = "PUBLIC_BACKEND_URL"
PUB_URL_VAR = "PUBLIC_ORIGIN"
OA_ROOT_VAR = "OA_ROOT"
# ORCID login creds + the admin allowlist — read from the deploy host's env and written into
# the deployed frontend's .env so `$env/dynamic/private` can see them at runtime.
ORCID_VARS = {
    k: os.environ.get(k)
    for k in ["ORCID_CLIENT_ID", "ORCID_CLIENT_SECRET", "ADMIN_ORCIDS"]
}

BIG16 = "c6a.4xlarge"
BIG16 = "c6a.8xlarge"
SMALL = "c6a.large"

LARGE_INSTANCE_TYPE = BIG16
LARGE_STORAGE_GB = 300
LARGE_FE_PROCS = 12
DEFAULT_RS_PORT = 3038

# Systemd unit shapes live in deploy/ (rendered by pyscripts/services.py); this
# module only feeds them remote-instance values and ships them over SSH.
FE_BUILD_NAMES = services.FE_BUILD_NAMES
FE_BUILD_PORTS_STARTS = [4000, 4200]
NGINX_AVDIR, NGINX_ENDIR = [f"/etc/nginx/sites-{s}" for s in ["available", "enabled"]]
UPSTREAM_ETC_FNAME = "app_upstreams"

be_service_name = services.BACKEND_UNIT
tunnel_service_name = "rankless-tunnel.service"
fe_service_template_frame = services.FE_UNIT_FRAME

local_tmp_home = Path("/tmp/rls-services")
local_service_path = local_tmp_home / SERIVCE_DIR
local_service_path.mkdir(exist_ok=True, parents=True)

local_data_root = os.environ[OA_ROOT_VAR]
data_subdirs = [
    "a1_entity_mapping",
    "a2_init_atts",
    "derive_links1",
    "derive_links2",
    "derive_links3",
    "derive_links4",
    "derive_links5",
    "cache",
]
ignores = [
    "source-pairs-by-path",
]

# MCP + ledger transfer (sync/merge_db_*): curated tables move via pyscripts.mcp_db,
# the artifact dirs via rsync. Same relative layout (paths.py) on both ends.
LOCAL_REPO = services.REPO_ROOT
DB_XFER_TMP = f"{paths.DATA_DIR}/_dbxfer"


@cache
def key_name() -> str:
    return os.environ["RL_KEY_ID"]


@cache
def key_path() -> str:
    return os.environ["RL_KEY_PATH"]


ubuntu24_image_id = "ami-0f67ca03a667867bb"

line_rex = re.compile(
    r'(.*?) \-.*\-.*\[(.*)\].*"([A-Z]+) (.*?)" (\d\d\d) (\d+) "(.*)" "(.*)"rt=(.*) uct="(.*)" uht="(.*)" urt="(.*)"'
)

line_cols = [
    "addr",
    "time",
    "r",
    "p",
    "code",
    "size",
    "referrer",
    "agent",
    "rt",
    "uct",
    "uht",
    "urt",
]


@dataclass
class IpAlloc:
    ip: str
    alloc_id: str


@dataclass
class UpstreamConf:
    fe_ports: list[int]
    ip: str = "127.0.0.1"
    be_port: int = DEFAULT_RS_PORT
    fe_timeout: int = 1
    suffix: str = ""

    def be_server(self):
        self.suffix = ""
        return self.sconf(self.be_port)

    def fe_servers(self):
        # self.suffix = f" max_fails=1 fail_timeout={self.fe_timeout}s"
        return map(self.sconf, self.fe_ports)

    def sconf(self, port):
        return f"server {self.ip}:{port}{self.suffix};"


@dataclass
class FrontendServiceConf:
    start_port: int
    n_procs: int
    suffix: str

    def template_fname(self):
        return fe_service_template_frame.format(self.suffix)

    def build_dir(self):
        return f"built-{self.suffix}"


def get_ip_alloc(live: bool):
    mode = "LIVE" if live else "ALPHA"
    return IpAlloc(os.environ[f"RL_{mode}_IP"], os.environ[f"RL_{mode}_ALLOC_ID"])


def get_tpr(inst):
    return Transper(SSHrer(inst.public_ip_address, "ubuntu", key_path(), True))


@cache
def live_ip_alloc() -> IpAlloc:
    return get_ip_alloc(True)


@cache
def alpha_ip_alloc() -> IpAlloc:
    return get_ip_alloc(False)


@cache
def session() -> "boto3.Session":
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE"))


@cache
def ec2():
    return session().resource("ec2")


@cache
def ec2c():
    return session().client("ec2")


def get_running_inst(live: bool):
    ip_alloc = live_ip_alloc() if live else alpha_ip_alloc()
    ip = ip_alloc.ip
    for inst in ec2().instances.all():  # pyright: ignore[reportAttributeAccessIssue]
        if inst.public_ip_address == ip:
            return inst


def get_dangling_instances():
    ips = [live_ip_alloc().ip, alpha_ip_alloc().ip]
    all_insts = ec2().instances.all()  # pyright: ignore[reportAttributeAccessIssue]

    def filt(inst):
        return inst.public_ip_address not in ips

    return list(filter(filt, all_insts))


def get_block_device(size, upgraded: bool = False):
    ext = {"Throughput": 500, "Iops": 16000} if upgraded else {}
    return {
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "VolumeSize": size,
            "VolumeType": "gp3",
            **ext,
            "DeleteOnTermination": True,
        },
    }


def get_new_inst(vol_size: int, itype: str, img: str = ubuntu24_image_id, ext=False):
    block_device = get_block_device(vol_size, ext)
    inst = ec2().create_instances(  # pyright: ignore[reportAttributeAccessIssue]
        ImageId=img,
        InstanceType=itype,
        KeyName=key_name(),
        MinCount=1,
        MaxCount=1,
        BlockDeviceMappings=[block_device],
    )[0]

    inst.wait_until_running()
    inst.reload()
    return inst


def run_logged(cmd: list[str], label: str | None = None, verbose: bool = False) -> str:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {label or ' '.join(cmd)}")
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        print(f"  failed (exit {e.returncode}):\n{e.output}")
        raise
    if verbose:
        print(out, end="")
    return out


class SSHrer:
    def __init__(self, host, user=None, key_path=None, reset=False, port=None):
        if reset:
            hp = Path.home() / ".ssh" / "known_hosts"
            phost = host if port is None else f"[{host}]:{port}"
            subprocess.check_output(["ssh-keygen", "-f", hp.as_posix(), "-R", phost])
        self.basis = ["ssh", "-o", "StrictHostKeyChecking=no"]
        self.key_extend = []
        self.rsync_basis = ["rsync", "-rav", "-z"]
        if key_path:
            self.key_extend.extend(["-i", key_path])
        self.rsync_basis.extend(
            ["-e", f"ssh -i {key_path or '~/.ssh/id_rsa'} -p {port or 22}"]
        )
        if port:
            self.basis.extend(["-p", str(port)])
            # self.rsync_basis.append(f"--port={port}")
        self.basis.extend(self.key_extend)
        self.full_host = host if user is None else f"{user}@{host}"
        self.basis.append(self.full_host)

    def run(self, comm, verbose=False):
        return run_logged([*self.basis, comm], comm, verbose)

    def rsync(self, src, target, excludes=[], verbose=False, delete=False):
        comm = self.rsync_basis + self._rsync_opts(excludes, delete)
        comm += [src, f"{self.full_host}:{target}/"]
        return run_logged(comm, verbose=verbose)

    def rsync_from(self, src, target, excludes=[], verbose=False, delete=False):
        comm = self.rsync_basis + self._rsync_opts(excludes, delete)
        comm += [f"{self.full_host}:{src}", target]
        return run_logged(comm, verbose=verbose)

    def _rsync_opts(self, excludes, delete):
        return (["--delete"] if delete else []) + [f"--exclude={e}" for e in excludes]

    def download(self, fpath):
        return run_logged(["scp", *self.basis[1:-1], f"{self.full_host}:{fpath}", "./"])


class ServiceMan:
    def __init__(self, name, ssh: SSHrer) -> None:
        self.name = name
        self.ssh = ssh

    def restart(self):
        self._run("restart")

    def start(self):
        self._run("start")

    def stop(self):
        self._run("stop")

    def status(self):
        self._run("status")

    def enable(self):
        self._run("enable")

    def disable(self):
        self._run("disable")

    def daemon_reload(self):
        self.ssh.run("systemctl daemon-reload")

    def _run(self, comm):
        self.ssh.run(f"systemctl {comm} --user {self.name}")


class Transper:
    def __init__(self, sshc: SSHrer):
        self.ssh = sshc
        for _ in range(12):
            try:
                sshc.run("echo working")
                self.inst_home = sshc.run("pwd").strip()
                break
            except Exception as e:
                print(e)
                time.sleep(5)
        else:
            raise RuntimeError(f"could not establish ssh to {sshc.full_host}")
        self.deploy_dir = self.inst_home + "/rankless-deploy"
        self.data_dir = self.inst_home + "/rankless-data"
        self.systemd_dir = f"{self.inst_home}/{SERIVCE_DIR}/"
        cache_dir = "/var/cache"
        self.be_cache_dir = f"{cache_dir}/rankless-be"
        self.fe_cache_dir = f"{cache_dir}/rankless-fe"
        self.ssh.run(f"mkdir -p {self.data_dir} {self.deploy_dir} {self.systemd_dir}")
        for cd in [self.be_cache_dir, self.fe_cache_dir]:
            self.ssh.run(f"sudo mkdir -p {cd}")
            self.ssh.run(f"sudo chown -R www-data:www-data {cd}")
        self.be_service = ServiceMan(be_service_name, sshc)
        self.sync_txt("test", "___test", self.inst_home)
        self.bun_exc = f"{self.inst_home}{BUN_PATH}"

    def bun_run(self, comm):
        self.ssh.run(f"{self.bun_exc} {comm}")

    def validate(self, backend=True):
        self.bun_run("--version")
        if backend:
            self.ssh.run("source .profile;cargo --version")

    def clean_caches(self):
        self.ssh.run(f"rm -rf {self.data_dir}/cache")
        self.ssh.run(f"sudo rm -rf {self.be_cache_dir}/*")
        self.ssh.run(f"sudo rm -rf {self.fe_cache_dir}/*")

    def install_apts(self):
        self.ssh.run("sudo apt update")
        self.ssh.run(
            f"sudo DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt install {' '.join(APTS)} -y"
        )

    def install_fonts(self):
        # Register the vendored brand fonts (static/fonts/) into the deploy user's fontconfig so the
        # share-card rasterizer (rsvg-convert) renders them. No-op on a checkout without the fonts.
        font_dir = f"{self.inst_home}/.local/share/fonts/rankless"
        self.ssh.run(
            f"if ls {self.deploy_dir}/static/fonts/*.ttf >/dev/null 2>&1; then "
            f"mkdir -p {font_dir} && cp {self.deploy_dir}/static/fonts/*.ttf {font_dir}/ && "
            f"fc-cache -f {font_dir}; fi"
        )

    def setup(self, backend=True):
        self.install_apts()
        if backend:
            self.ssh.run(
                "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
            )
        self.ssh.run("sudo systemctl enable --now systemd-oomd")
        self.ssh.run("curl -fsSL https://bun.sh/install | bash")
        # uv drives the python side (mcp server + worker) on the instance.
        self.ssh.run("curl -LsSf https://astral.sh/uv/install.sh | sh")

    def sync_txt(self, txt, name, dir):
        p = Path(name)
        existed = p.exists()
        past_blob = b""
        if existed:
            past_blob = p.read_bytes()
        p.write_text(txt)
        self.ssh.rsync(p.as_posix(), dir)
        p.unlink()
        if existed:
            p.write_bytes(past_blob)

    def sync_service(self, txt, name):
        self.sync_txt(txt, name, self.systemd_dir)

    def setup_be_service(self):
        be_service_txt = services.render_backend(self.deploy_dir, self.data_dir)
        self.sync_service(be_service_txt, be_service_name)
        self.be_service.enable()
        self.be_service.start()

    def setup_mcp_services(self, mcp_backend: str = "local"):
        """MCP server + worker units on the instance (venv must be synced)."""
        python = f"{self.deploy_dir}/.venv/bin/python"
        be_url = services.resolve_mcp_backend(mcp_backend)
        self.sync_service(
            services.render_mcp_server(self.deploy_dir, python, be_url),
            services.MCP_SERVER_UNIT,
        )
        self.sync_service(
            services.render_mcp_worker(self.deploy_dir, python),
            services.MCP_WORKER_UNIT,
        )
        self.reload_systemctl()
        for name in (services.MCP_SERVER_UNIT, services.MCP_WORKER_UNIT):
            man = ServiceMan(name, self.ssh)
            man.enable()
            man.restart()

    def setup_fe_services(self, inst_domain: str, procs: int = 2):
        confs = [
            FrontendServiceConf(sport, procs, suff)
            for sport, suff in zip(FE_BUILD_PORTS_STARTS, FE_BUILD_NAMES)
        ]
        for conf in confs:
            fe_service_txt = services.render_frontend(
                self.deploy_dir,
                inst_domain,
                conf.suffix,
                conf.build_dir(),
                f"%h{BUN_PATH}",
            )
            self.sync_service(fe_service_txt, conf.template_fname())
            for service in self._iter_conf_services(conf):
                service.enable()
                service.stop()
        self.reload_systemctl()

    def get_fe_systems(self):
        fe_rex = fe_service_template_frame.format("([a-z]+)").replace("@", r"@(\d+)")
        out = []
        for name, port in sorted(
            re.findall(fe_rex, self.ssh.run(f"ls {SERIVCE_DIR}/default.target.wants/"))
        ):
            if len(out) == 0 or out[-1][0] != name:
                out.append((name, [int(port)]))
            else:
                out[-1][1].append(int(port))
        confiter = [
            FrontendServiceConf(ports[0], len(ports), name) for name, ports in out
        ]
        active_start_port = 0
        try:
            usconf = self.ssh.run(f"cat {NGINX_AVDIR}/{UPSTREAM_ETC_FNAME}")
            upnext = False
            for line in usconf.split("\n"):
                if upnext:
                    found = re.findall(r"server \d+\.\d+\.\d+\.\d+\:(\d+)", line)
                    active_start_port = int(found[0])
                    break
                if FE_UPSTREAM in line:
                    upnext = True
        except Exception:
            pass
        return sorted(confiter, key=lambda c: c.start_port == active_start_port)

    def get_domain(self):
        fname_wc = fe_service_template_frame.format("*")
        cato = self.ssh.run(f"cat ~/{SERIVCE_DIR}/{fname_wc}")
        return re.findall("ORIGIN=https://(.*) ", cato)[0]

    def get_backend_domain(self):
        domain = self.get_domain()
        if domain == ALPHA_DOMAIN:
            return ALPHA_BACKEND
        if domain == LIVE_DOMAIN:
            return LIVE_BACKEND
        raise ValueError(f"{domain} is not recognized")

    def setup_nginx(self, inst_domain=None, cert=True):
        if inst_domain is None:
            inst_domain = self.get_domain()
        if cert:
            self.get_cert(inst_domain)
        self._add_upstreams_from_conf(self.get_fe_systems()[1])
        security_headers = """
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;"""
        server_prefix = f"""
    listen 443 ssl;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1000;   

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    access_log /var/log/nginx/access.log upstream_time;
{security_headers}"""
        loc_suffix = """
        proxy_cache_use_stale error timeout http_500 http_502 http_503 http_504;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        limit_req zone=baselimit burst=55 nodelay;
        limit_req_status 429;"""

        nginx_conf = f"""
proxy_cache_path {self.be_cache_dir} levels=1:2 keys_zone=be-cache:50m max_size=20g;
proxy_cache_path {self.fe_cache_dir} levels=1:2 keys_zone=fe-cache:50m max_size=10g;
limit_req_zone $binary_remote_addr zone=baselimit:10m rate=2r/s;

log_format upstream_time '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent"'
                         'rt=$request_time uct="$upstream_connect_time" uht="$upstream_header_time" urt="$upstream_response_time" cs=$upstream_cache_status host=$host';

server {{

    {self.get_server_prefix(inst_domain)}
    {server_prefix}

    location / {{
        proxy_pass http://{FE_UPSTREAM};
        proxy_cache fe-cache;
        {loc_suffix}
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
        proxy_next_upstream_tries 5;
    }}
}}

server {{
    {self.get_server_prefix(self.get_backend_domain())}
    {server_prefix}

    location / {{
        proxy_pass http://{BE_UPSTREAM};
        proxy_cache be-cache;
        {loc_suffix}
        add_header Access-Control-Allow-Origin *;
        {security_headers}
    }}

    {services.render_nginx_mcp()}
}}

server {{
   listen 80;
   server_name {inst_domain};
   return 301 https://$server_name$request_uri;
}}

server {{
    listen 5566;

    location /status {{
        default_type application/json;
        alias /tmp/status_cache.json;
    }}
}}

        """
        self._send_nginx_conf(nginx_conf, inst_domain)

    def get_server_prefix(self, domain):
        cert_dir = f"{SSL_ETC_DIR}/{domain}"
        suffix = ""
        try:
            self.ssh.run(f"sudo ls {cert_dir}")
            suffix = f"""ssl_certificate {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;"""
        except Exception:
            pass

        return f"""
    server_name {domain};
    {suffix}"""

    def clean_cert_default(self):
        self._send_nginx_conf("", "default")

    def get_cert(self, domain):
        self.ssh.run(
            f"sudo certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d {domain}"
        )
        self.clean_cert_default()

    def pull_certs(self):
        self.ssh.run(f"sudo tar zpcvf {LOCAL_SSL_TAR} /etc/letsencrypt/")
        self.ssh.download(f"{self.inst_home}/{LOCAL_SSL_TAR}")

    def push_certs(self):
        self.ssh.rsync(LOCAL_SSL_TAR, self.inst_home)
        self.ssh.run(f"sudo tar zxvf {LOCAL_SSL_TAR} -C /")

    def refresh_certs(self, *other_domains):
        for domain in [self.get_domain(), self.get_backend_domain(), *other_domains]:
            self.get_cert(domain)

    def add_domain_fw(self, domain_to_fw: str, cert=True):
        orig_domain = self.get_domain()
        nginx_conf = f"""
server {{
    listen 80;
    listen [::]:80;
    server_name {domain_to_fw};
    return 301 https://{orig_domain}$request_uri;
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    {self.get_server_prefix(domain_to_fw)}
    
    include /etc/letsencrypt/options-ssl-nginx.conf;
    return 301 https://{orig_domain}$request_uri;
}}
"""
        self._send_nginx_conf(nginx_conf, domain_to_fw)
        if cert:
            self.get_cert(domain_to_fw)

    def nginx_add_upstreams(self, upstreams: list[UpstreamConf]):
        fe_servers = []
        be_servers = []
        for conf in upstreams:
            fe_servers.extend(conf.fe_servers())
            be_servers.append(conf.be_server())

        fe_conf = "\n    ".join(fe_servers)
        be_conf = "\n    ".join(be_servers)
        conf_txt = f"""
upstream {FE_UPSTREAM} {{
    {fe_conf}
}}

upstream {BE_UPSTREAM} {{
     {be_conf}
}}
"""
        self._send_nginx_conf(conf_txt, UPSTREAM_ETC_FNAME)

    def restart_nginx(self):
        self._nginx_run(["reload", "restart", "status"])

    def reload_nginx(self):
        self._nginx_run(["reload", "status"])

    def sync_data_to(self):
        for subdir in tqdm(data_subdirs):
            self.ssh.rsync(f"{local_data_root}/{subdir}", self.data_dir, ignores)

    # MCP + ledger movement. `merge` unions rows (source never clobbers target);
    # `sync` mirrors — the target's copy of these tables becomes an exact copy of
    # the source's. Both carry the data/mcp-sessions/ artifact dirs along; auth
    # `sessions` are never touched (see pyscripts.mcp_db).
    def merge_db_to(self):
        self._push_db(mirror=False)

    def sync_db_to(self):
        # Destructive on a live box: REPLACES its ledger_events/mcp_sessions with
        # the local copy. Use merge_db_to to publish without clobbering.
        self._push_db(mirror=True)

    def merge_db_from(self):
        self._pull_db(mirror=False)

    def sync_db_from(self):
        self._pull_db(mirror=True)

    def _push_db(self, mirror):
        mode = "mirror" if mirror else "merge"
        (LOCAL_REPO / paths.MCP_SESSIONS_REL).mkdir(parents=True, exist_ok=True)
        tmp = f"{self.deploy_dir}/{DB_XFER_TMP}"
        incoming = f"{tmp}/{Path(paths.DB_REL).name}"
        self.ssh.run(f"rm -rf {tmp} && mkdir -p {tmp}")
        self.ssh.rsync(str(LOCAL_REPO / paths.DB_REL), tmp)
        self._depcomm(
            f".venv/bin/python -m pyscripts.mcp_db {self.deploy_dir}/{paths.DB_REL} {incoming} {mode}"
        )
        self.ssh.run(f"rm -rf {tmp}")
        self.ssh.rsync(
            str(LOCAL_REPO / paths.MCP_SESSIONS_REL),
            f"{self.deploy_dir}/{paths.DATA_DIR}",
            delete=mirror,
        )

    def _pull_db(self, mirror):
        mode = "mirror" if mirror else "merge"
        tmp = LOCAL_REPO / DB_XFER_TMP
        tmp.mkdir(parents=True, exist_ok=True)
        self.ssh.rsync_from(f"{self.deploy_dir}/{paths.DB_REL}", str(tmp))
        incoming = str(tmp / Path(paths.DB_REL).name)
        mcp_db.transfer(str(LOCAL_REPO / paths.DB_REL), incoming, mode)
        shutil.rmtree(tmp)
        self.ssh.rsync_from(
            f"{self.deploy_dir}/{paths.MCP_SESSIONS_REL}",
            str(LOCAL_REPO / paths.DATA_DIR),
            delete=mirror,
        )

    def setup_code(self, branch=None):
        self.ssh.run(f"rm -rf {self.deploy_dir}")
        self.ssh.run(
            f"git clone https://github.com/endremborza/rankless {self.deploy_dir}"
        )
        # Deploy whatever the caller is on, not the remote's default branch — the
        # branch must be pushed to origin first.
        self._depcomm(f"git checkout {branch or _current_branch()}")
        self.update_env()

    def sync_code(self):
        self._depcomm("git pull")
        self.update_env()

    def build_js(self):
        self._depcomm(f"{self.bun_exc} install;{self.bun_exc} run build")

    def build_rs(self):
        self._depcomm("cargo build --release")

    def sync_py(self):
        # Serving box: MCP runtime only. `--no-default-groups` drops the
        # `pipeline` group (which pins the `libs/ccl-science-data` path source,
        # absent here) + `dev`; `--frozen` uses the committed lock without a
        # re-resolve that would still try to read that missing path.
        self._depcomm("~/.local/bin/uv sync --frozen --no-default-groups")

    def update_env(self):
        domain = self.get_domain()
        be_url = "https://" + self.get_backend_domain()
        txt = f"{PUB_URL_VAR}=https://{domain}\n{BE_URL_VAR}={be_url}\n{OA_ROOT_VAR}={self.data_dir}\n"
        txt += "\n".join(f"{k}={v}" for k, v in ORCID_VARS.items() if v is not None)
        self.sync_txt(txt, ".env", self.deploy_dir)

    def update_fe(self):
        self.sync_code()
        self.install_fonts()
        self.build_js()
        stage_conf, live_conf = self.get_fe_systems()
        self._depcomm(f"rm -rf {stage_conf.build_dir()}")
        self._depcomm(f"cp -r build {stage_conf.build_dir()}")
        for service in self._iter_conf_services(stage_conf):
            service.restart()
        while self._validate_fe(stage_conf):
            pass
        self._add_upstreams_from_conf(stage_conf)
        self.reload_nginx()
        self.ssh.run(f"sudo rm -rf {self.fe_cache_dir}/*")
        time.sleep(10)
        for service in self._iter_conf_services(live_conf):
            service.stop()

    def update_data(self):
        self.sync_code()
        self.build_rs()
        self.sync_data_to()
        self.be_service.restart()

    def rolling_restart_live_fe(self):
        _stage_conf, live_conf = self.get_fe_systems()
        for service in self._iter_conf_services(live_conf):
            service.restart()
            time.sleep(20)
            service.status()

    def reload_systemctl(self):
        self.ssh.run("sudo systemctl daemon-reload")

    def get_backend_open_files_df(self):
        comm = f"cat /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/{be_service_name}/cgroup.procs"
        fdfs = []
        for pid in self.ssh.run(comm).strip().split():
            fdfs.append(
                pd.DataFrame(
                    map(
                        lambda s: s.split(),
                        self.ssh.run(f"ls -l /proc/{pid}/fd").strip().split("\n")[1:],
                    )
                )
                .assign(n=lambda df: df.loc[:, 8].astype(int))
                .loc[:, [7, "n", 10]]
                .sort_values("n")
            )
        return pd.concat(fdfs, ignore_index=True)

    def get_free_memory(self):
        ks = ["total", "used", "free", "shared", "buff/cache", "available"]
        vs = re.findall(
            r"Mem: +(\d+) +(\d+) +(\d+) +(\d+) +(\d+) +(\d+)", self.ssh.run("free")
        )[0]
        return dict(zip(ks, map(int, vs)))

    def get_unit_props(self, unit: str, props: list[str]) -> dict[str, str]:
        out = self.ssh.run(f"systemctl --user show {unit} -p {','.join(props)}")
        parsed = dict(re.findall(r"^([A-Za-z]+)=(.*)$", out, re.M))
        return {p: parsed.get(p, "") for p in props}

    def get_fe_memory_df(self):
        # Per-FE-proc cgroup memory + restart state — the runtime view that pins which worker grows
        # (MemoryPeak is the high-water mark since start, MemoryCurrent the live footprint).
        props = [
            "ActiveState",
            "SubState",
            "MemoryCurrent",
            "MemoryPeak",
            "MemoryHigh",
            "MemoryMax",
            "OOMPolicy",
            "NRestarts",
        ]
        rows = []
        for conf in self.get_fe_systems():
            for service in self._iter_conf_services(conf):
                rows.append(
                    {"unit": service.name, **self.get_unit_props(service.name, props)}
                )
        return pd.DataFrame(rows)

    def get_storage_stats(self):
        cmatch = re.findall(r"/dev/root.*?(\d+)\s+(\d+)% /\n", self.ssh.run("df"))[0]
        rem_bytes, full_pct = map(int, cmatch)
        return rem_bytes, full_pct

    def get_nginx_logs_df(self, minutes=3, n=10_000):
        logtail = self.ssh.run(f"tail -{n} /var/log/nginx/access.log")
        return (
            pd.DataFrame(
                map(
                    lambda e: e[0],
                    filter(None, map(line_rex.findall, logtail.split("\n"))),
                ),
                columns=line_cols,  # pyright: ignore[reportArgumentType]
            )
            .assign(
                t=lambda df: df["time"].pipe(
                    pd.to_datetime, format="%d/%b/%Y:%H:%M:%S %z"
                ),
                urt=lambda df: df["urt"].apply(tryfloat),
                code=lambda df: df["code"].astype(int),
            )
            .loc[lambda df: df["t"] > (df["t"].max() - dt.timedelta(minutes=minutes))]
        )

    def _depcomm(self, comm: str):
        self.ssh.run(f"cd {self.deploy_dir};source ~/.profile;{comm}")

    def _get_fe_service(self, conf: FrontendServiceConf, port):
        return ServiceMan(conf.template_fname().replace("@", f"@{port}"), self.ssh)

    def _validate_fe(self, conf: FrontendServiceConf):
        time.sleep(0.5)
        for i in range(conf.n_procs):
            port = conf.start_port + i
            try:
                self.ssh.run(
                    'curl -s -o /dev/null -w "%{http_code}" localhost:' + str(port)
                )
            except Exception:
                return True
        return False

    def _add_upstreams_from_conf(self, conf: FrontendServiceConf):
        ports = [conf.start_port + i for i in range(conf.n_procs)]
        self.nginx_add_upstreams([UpstreamConf(ports)])

    def _iter_conf_services(self, conf: FrontendServiceConf):
        for i in range(conf.n_procs):
            yield self._get_fe_service(conf, conf.start_port + i)

    def _nginx_run(self, comms):
        self.ssh.run("sudo nginx -t")
        self.reload_systemctl()
        for comm in comms:
            self.ssh.run(f"sudo systemctl {comm} nginx")

    def _send_nginx_conf(self, conf_txt, slug):
        self.ssh.run(f"sudo rm -f {NGINX_AVDIR}/{slug} {NGINX_ENDIR}/{slug}")
        if conf_txt:
            self.sync_txt(conf_txt, slug, self.inst_home)
            self.ssh.run(f"sudo mv {self.inst_home}/{slug} {NGINX_AVDIR}/")
            self.ssh.run(f"sudo ln -s {NGINX_AVDIR}/{slug} {NGINX_ENDIR}/")


def pull_live_certs():
    get_tpr(get_running_inst(True)).pull_certs()


def get_running_tpr(live: bool):
    return get_tpr(get_running_inst(live))


def sync_fe_to_alpha():
    get_running_tpr(False).update_fe()


def sync_fe_to_local():
    _local_tpr().update_fe()


def sync_fe_to_live():
    get_running_tpr(True).update_fe()


def sync_data_to_alpha():
    get_running_tpr(False).update_data()


def sync_data_to_live():
    get_running_tpr(True).update_data()


def merge_db_from_live():
    get_running_tpr(True).merge_db_from()


def sync_db_from_live():
    get_running_tpr(True).sync_db_from()


def merge_db_to_live():
    get_running_tpr(True).merge_db_to()


def sync_db_to_live():
    get_running_tpr(True).sync_db_to()


def merge_db_from_alpha():
    get_running_tpr(False).merge_db_from()


def sync_db_from_alpha():
    get_running_tpr(False).sync_db_from()


def merge_db_to_alpha():
    get_running_tpr(False).merge_db_to()


def sync_db_to_alpha():
    get_running_tpr(False).sync_db_to()


def full_setup_from_nothing(
    tpr: Transper, domain, procn: int, backend=True, branch=None
):
    tpr.setup(backend=backend)
    tpr.validate(backend=backend)
    tpr.setup_fe_services(domain, procs=procn)
    tpr.setup_code(branch)
    tpr.update_fe()
    tpr.sync_py()
    tpr.setup_mcp_services("local" if backend else "live")
    if backend:
        tpr.build_rs()
        tpr.sync_data_to()
        tpr.setup_be_service()
    for live in [False, True]:
        try:
            get_running_tpr(live).pull_certs()
            tpr.push_certs()
        except Exception:
            pass
    tpr.push_certs()
    tpr.setup_nginx(cert=False)
    tpr.restart_nginx()


def new_small_alpha():
    return _new_alpha(30, SMALL, 2, False)


def new_large_alpha():
    return _new_alpha(LARGE_STORAGE_GB, LARGE_INSTANCE_TYPE, LARGE_FE_PROCS, True)


def kill_dangling():
    for inst in get_dangling_instances():
        inst.terminate()


def kill_alpha():
    get_running_inst(False).terminate()


def _new_alpha(storage, itype, fe_procn, backend):
    inst = get_new_inst(storage, itype)
    tpr = get_tpr(inst)
    full_setup_from_nothing(tpr, ALPHA_DOMAIN, fe_procn, backend=backend)
    associate_id(inst, False)
    time.sleep(15)
    new_tpr = get_tpr(inst)
    new_tpr.refresh_certs()
    new_tpr.restart_nginx()
    return new_tpr


def new_large_image():
    v = subprocess.check_output(["git", "tag", "--points-at", "HEAD"]).decode().strip()
    vns = _parse_v(v)
    inst = get_new_inst(LARGE_STORAGE_GB, LARGE_INSTANCE_TYPE)
    tpr = get_tpr(inst)
    full_setup_from_nothing(tpr, LIVE_DOMAIN, LARGE_FE_PROCS)
    inst.stop()
    inst.wait_until_stopped()
    image = inst.create_image(
        Name=f"Rankless {v}",
        Description=f"{v} node, bun, rust and services",
    )
    inst.terminate()
    pd.read_csv(AMI_IMG_CSV).pipe(
        lambda df: pd.concat(
            [df, pd.DataFrame([[*vns, image.id]], columns=df.columns)],
            ignore_index=True,
        )
    ).drop_duplicates().to_csv(AMI_IMG_CSV, index=False)
    return image.id


def horizontal_instances(n):
    ips = []
    for inst in ec2().create_instances(  # pyright: ignore[reportAttributeAccessIssue]
        ImageId=_last_img(),
        InstanceType=LARGE_INSTANCE_TYPE,
        KeyName=key_name(),
        MinCount=n,
        MaxCount=n,
    ):
        inst.wait_until_running()
        inst.load()
        tpr = get_tpr(inst)
        tpr.update_fe()
        tpr.be_service.start()
        ips.append(inst.public_ip_address)
    return ips


def setup_local_test():
    full_setup_from_nothing(_local_tpr(), ALPHA_DOMAIN, 3, True)


def bump_v(i=2):
    vns = _last_vns()
    vns[i] += 1
    for j in range(i + 1, 3):
        vns[j] = 0
    next_v = f"v{vns[0]}.{vns[1]}.{vns[2]}"
    v_const_ts = "src/lib/v_constants.ts"
    const_v_txt = f"""
export const LAST_MOD = '{dt.date.today().isoformat()}';
export const VERSION = '{next_v}';
"""
    Path(v_const_ts).write_text(const_v_txt)
    pack_json = Path("package.json")
    ptxt = re.sub(
        r'version": "\d+\.\d+\.\d+', f'version": "{next_v[1:]}', pack_json.read_text()
    )
    pack_json.write_text(ptxt)
    subprocess.call(["git", "add", v_const_ts, pack_json.as_posix()])
    subprocess.call(["git", "commit", "-m", f"{next_v} consts"])
    subprocess.call(["git", "tag", next_v])
    subprocess.call(["git", "push", "origin", "tag", next_v])
    # annoted, within the ancestors tags
    # git push --follow-tags


def rolling_restart_live_fe():
    get_running_tpr(True).rolling_restart_live_fe()


def bump_v_minor():
    bump_v(1)


def promote_alpha_to_live():
    alpha_inst = get_running_inst(False)
    assert alpha_inst is not None
    tpr = get_tpr(alpha_inst)
    tpr.setup_fe_services(LIVE_DOMAIN, procs=LARGE_FE_PROCS)
    tpr.update_env()
    tpr.update_fe()
    tpr.ssh.run(f"sudo rm -f {NGINX_ENDIR}/{ALPHA_DOMAIN}")
    tpr.setup_nginx(cert=False)
    tpr.add_domain_fw(FW_DOMAIN, cert=False)
    tpr.restart_nginx()
    time.sleep(10)
    associate_id(alpha_inst, True)
    time.sleep(5)
    get_running_tpr(True).refresh_certs(FW_DOMAIN)


def associate_id(inst, live: bool):
    ipa = live_ip_alloc() if live else alpha_ip_alloc()
    ec2c().associate_address(InstanceId=inst.id, AllocationId=ipa.alloc_id)
    inst.reload()
    return inst


def tryfloat(s):
    try:
        return float(s)
    except Exception:
        return float("nan")


def _local_tpr():
    return Transper(SSHrer("127.0.0.1", "ubuntu", reset=True, port=2223))


def _last_img():
    return (
        pd.read_csv(AMI_IMG_CSV)
        .pipe(lambda df: df.set_index([*df.columns[:3]]))
        .sort_index()
        .iloc[-1, 0]
    )


def _current_branch() -> str:
    return subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()


def _last_vns():
    tag_str = subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"]
    ).decode()
    return _parse_v(tag_str)


def _parse_v(tag_str):
    return list(map(int, re.findall(r"^v(\d+)\.(\d+)\.(\d+)$", tag_str)[0]))
