import datetime as dt
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

SERIVCE_DIR = ".config/systemd/user"
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
ORCID_VARS = {k: os.environ.get(k) for k in ["ORCID_CLIENT_ID", "ORCID_CLIENT_SECRET"]}

BIG16 = "c6a.4xlarge"
BIG16 = "c6a.8xlarge"
SMALL = "c6a.large"

LARGE_INSTANCE_TYPE = BIG16
LARGE_STORAGE_GB = 300
LARGE_FE_PROCS = 12
DEFAULT_RS_PORT = 3038

SERVICE_SUFFIX = """
Restart=always
RestartSec=15

[Install]
WantedBy=default.target"""

FE_BUILD_NAMES = ["blue", "green"]
FE_BUILD_PORTS_STARTS = [4000, 4200]
NGINX_AVDIR, NGINX_ENDIR = [f"/etc/nginx/sites-{s}" for s in ["available", "enabled"]]
UPSTREAM_ETC_FNAME = "app_upstreams"

be_service_name = "rankless-backend.service"
tunnel_service_name = "rankless-tunnel.service"
fe_service_template_frame = "rankless-frontend-{}@.service"

be_service_frame = (
    """[Unit]
Description=Rankless Backend

[Service]
LimitNOFILE=65534
ExecStart={}/target/release/rankless-server {}"""
    + SERVICE_SUFFIX
)

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
    "work-references",
    "authors-ref-subfields",
    "authors-cit-subfields",
    "source-pairs-by-path",
]


aws_profile = os.environ.get("AWS_PROFILE")
key_name = os.environ["RL_KEY_ID"]
key_path = os.environ["RL_KEY_PATH"]

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
    return Transper(SSHrer(inst.public_ip_address, "ubuntu", key_path, True))


live_ip_alloc = get_ip_alloc(True)
alpha_ip_alloc = get_ip_alloc(False)

session = boto3.Session(profile_name=aws_profile)

ec2 = session.resource("ec2")
ec2c = session.client("ec2")


def get_running_inst(live: bool):
    ip_alloc = live_ip_alloc if live else alpha_ip_alloc
    ip = ip_alloc.ip
    for inst in ec2.instances.all():  # pyright: ignore[reportAttributeAccessIssue]
        if inst.public_ip_address == ip:
            return inst


def get_dangling_instances():
    ips = [live_ip_alloc.ip, alpha_ip_alloc.ip]
    all_insts = ec2.instances.all()  # pyright: ignore[reportAttributeAccessIssue]

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
    inst = ec2.create_instances(  # pyright: ignore[reportAttributeAccessIssue]
        ImageId=img,
        InstanceType=itype,
        KeyName=key_name,
        MinCount=1,
        MaxCount=1,
        BlockDeviceMappings=[block_device],
    )[0]

    inst.wait_until_running()
    inst.reload()
    return inst


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

    def run(self, comm):
        try:
            return subprocess.check_output(
                [*self.basis, comm], stderr=subprocess.STDOUT, text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"{comm}\nexit code {e.returncode}:\n", e.output)
            raise e

    def prun(self, comm):
        print("running", comm)
        print(self.run(comm))

    def rsync(self, src, target, excludes=[]):
        comm = self.rsync_basis + [f"--exclude={e}" for e in excludes] + [src]
        comm.append(f"{self.full_host}:{target}/")
        return subprocess.check_output(comm).decode()

    def download(self, fpath):
        return subprocess.check_output(
            ["scp", *self.basis[1:-1], f"{self.full_host}:{fpath}", "./"]
        )

    def prsync(self, src, target, excludes=[]):
        print(self.rsync(src, target, excludes=excludes))


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
        self.ssh.prun(f"systemctl daemon-reload")

    def _run(self, comm):
        self.ssh.prun(f"systemctl {comm} --user {self.name}")


class Transper:
    def __init__(self, sshc: SSHrer):
        for _ in range(4):
            try:
                sshc.run("echo working")
                break
            except Exception as e:
                print(e)
                time.sleep(5)
        self.ssh = sshc
        self.inst_home = sshc.run("pwd").strip()
        self.deploy_dir = self.inst_home + "/rankless-deploy"
        self.data_dir = self.inst_home + "/rankless-data"
        self.systemd_dir = f"{self.inst_home}/{SERIVCE_DIR}/"
        cache_dir = f"/var/cache"
        self.be_cache_dir = f"{cache_dir}/rankless-be"
        self.fe_cache_dir = f"{cache_dir}/rankless-fe"
        self.ssh.run(f"mkdir -p {self.data_dir} {self.deploy_dir} {self.systemd_dir}")
        for cd in [self.be_cache_dir, self.fe_cache_dir]:
            self.ssh.run(f"sudo mkdir -p {cd}")
            self.ssh.run(f"sudo chown -R www-data:www-data {cd}")
        self.be_service = ServiceMan(be_service_name, sshc)
        self.sync_txt("test", "___test", self.inst_home)

    def get_node_v(self):
        return self.ssh.run("source .nvm/nvm.sh;nvm version").strip()

    def validate(self, backend=True):
        print(self.get_node_v())
        if backend:
            self.ssh.prun("source .profile;cargo --version")

    def clean_caches(self):
        self.ssh.prun(f"rm -rf {self.data_dir}/cache")
        self.ssh.prun(f"sudo rm -rf {self.be_cache_dir}/*")
        self.ssh.prun(f"sudo rm -rf {self.fe_cache_dir}/*")

    def setup(self, backend=True, bun=False):
        self.ssh.prun("sudo apt update")
        self.ssh.prun(
            f"sudo DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt install {' '.join(APTS)} -y"
        )
        if backend:
            self.ssh.prun(
                "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
            )
        if bun:
            self.ssh.prun("curl -fsSL https://bun.sh/install | bash")
        self.ssh.prun(
            "curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash"
        )
        self.ssh.prun("source .nvm/nvm.sh; nvm install --lts")
        self.ssh.prun("systemctl enable --now systemd-oomd")

    def sync_txt(self, txt, name, dir):
        p = Path(name)
        existed = p.exists()
        past_blob = b""
        if existed:
            past_blob = p.read_bytes()
        p.write_text(txt)
        self.ssh.prsync(p.as_posix(), dir)
        p.unlink()
        if existed:
            p.write_bytes(past_blob)

    def sync_service(self, txt, name):
        self.sync_txt(txt, name, self.systemd_dir)

    def setup_be_service(self):
        be_service_txt = be_service_frame.format(self.deploy_dir, self.data_dir)
        self.sync_service(be_service_txt, be_service_name)
        self.be_service.enable()
        self.be_service.start()

    def setup_fe_services(self, inst_domain: str, bun=False, procs: int = 2):
        confs = [
            FrontendServiceConf(sport, procs, suff)
            for sport, suff in zip(FE_BUILD_PORTS_STARTS, FE_BUILD_NAMES)
        ]
        for conf in confs:
            if bun:
                comm = f"%h/.bun/bin/bun run {conf.build_dir()}/"
            else:
                node_version = self.get_node_v()
                comm = (
                    f"%h/.nvm/versions/node/{node_version}/bin/node {conf.build_dir()}"
                )
            fe_service_txt = (
                f"""[Unit]
    Description=Rankless Frontend {conf.suffix} %i
    After=network.target

    [Service]
    WorkingDirectory={self.deploy_dir}
    Environment=ORIGIN=https://{inst_domain} PORT=%i
    ExecStart={comm}"""
                + SERVICE_SUFFIX
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
        except:
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
        server_prefix = f"""
    listen 443 ssl;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1000;   

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    access_log /var/log/nginx/access.log upstream_time;"""
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
                         'rt=$request_time uct="$upstream_connect_time" uht="$upstream_header_time" urt="$upstream_response_time"';

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
    }}
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
        except:
            pass

        return f"""
    server_name {domain};
    {suffix}"""

    def clean_cert_default(self):
        self._send_nginx_conf("", "default")

    def get_cert(self, domain):
        self.ssh.prun(
            f"sudo certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d {domain}"
        )
        self.clean_cert_default()

    def pull_certs(self):
        self.ssh.prun(f"sudo tar zpcvf {LOCAL_SSL_TAR} /etc/letsencrypt/")
        self.ssh.download(f"{self.inst_home}/{LOCAL_SSL_TAR}")

    def push_certs(self):
        self.ssh.rsync(LOCAL_SSL_TAR, self.inst_home)
        self.ssh.prun(f"sudo tar zxvf {LOCAL_SSL_TAR} -C /")

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

    def setup_code(self, branch=None):
        self.ssh.prun(f"rm -rf {self.deploy_dir}")
        self.ssh.prun(
            f"git clone https://github.com/endremborza/rankless {self.deploy_dir}"
        )
        if branch:
            self._depcomm(f"git checkout {branch}")
        self.update_env()

    def sync_code(self):
        self._depcomm("git pull")
        self.update_env()

    def build_js(self):
        self._depcomm("source ~/.nvm/nvm.sh;npm install;npm run build")

    def build_rs(self):
        self._depcomm("cargo build --release")

    def update_env(self):
        domain = self.get_domain()
        be_url = "https://" + self.get_backend_domain()
        txt = f"{PUB_URL_VAR}=https://{domain}\n{BE_URL_VAR}={be_url}\n{OA_ROOT_VAR}={self.data_dir}\n"
        txt += "\n".join(f"{k}={v}" for k, v in ORCID_VARS.items())
        self.sync_txt(txt, ".env", self.deploy_dir)

    def update_fe(self):
        self.sync_code()
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
        self.ssh.prun(f"sudo rm -rf {self.fe_cache_dir}/*")
        for service in self._iter_conf_services(live_conf):
            service.stop()

    def rolling_restart_live_fe(self):
        _stage_conf, live_conf = self.get_fe_systems()
        for service in self._iter_conf_services(live_conf):
            service.restart()
            time.sleep(20)
            service.status()

    def reload_systemctl(self):
        self.ssh.prun("sudo systemctl daemon-reload")

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
        self.ssh.prun(f"cd {self.deploy_dir};source ~/.profile;{comm}")

    def _get_fe_service(self, conf: FrontendServiceConf, port):
        return ServiceMan(conf.template_fname().replace("@", f"@{port}"), self.ssh)

    def _validate_fe(self, conf: FrontendServiceConf):
        time.sleep(0.5)
        for i in range(conf.n_procs):
            port = conf.start_port + i
            try:
                self.ssh.prun(
                    'curl -s -o /dev/null -w "%{http_code}" localhost:' + str(port)
                )
            except:
                return True
        return False

    def _add_upstreams_from_conf(self, conf: FrontendServiceConf):
        ports = [conf.start_port + i for i in range(conf.n_procs)]
        self.nginx_add_upstreams([UpstreamConf(ports)])

    def _iter_conf_services(self, conf: FrontendServiceConf):
        for i in range(conf.n_procs):
            yield self._get_fe_service(conf, conf.start_port + i)

    def _nginx_run(self, comms):
        self.ssh.prun("sudo nginx -t")
        self.reload_systemctl()
        for comm in comms:
            self.ssh.prun(f"sudo systemctl {comm} nginx")

    def _send_nginx_conf(self, conf_txt, slug):
        self.ssh.prun(f"sudo rm -f {NGINX_AVDIR}/{slug} {NGINX_ENDIR}/{slug}")
        if conf_txt:
            self.sync_txt(conf_txt, slug, self.inst_home)
            self.ssh.prun(f"sudo mv {self.inst_home}/{slug} {NGINX_AVDIR}/")
            self.ssh.prun(f"sudo ln -s {NGINX_AVDIR}/{slug} {NGINX_ENDIR}/")


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


def full_setup_from_nothing(
    tpr: Transper, domain, procn: int, backend=True, bun=True, branch=None
):
    tpr.setup(backend=backend, bun=bun)
    tpr.validate(backend=backend)
    tpr.setup_fe_services(domain, bun=bun, procs=procn)
    tpr.setup_code(branch)
    tpr.update_fe()
    if backend:
        tpr.build_rs()
        tpr.sync_data_to()
        tpr.setup_be_service()
    for live in [False, True]:
        try:
            get_running_tpr(live).pull_certs()
            tpr.push_certs()
        except:
            pass
    tpr.push_certs()
    tpr.setup_nginx(cert=False)
    tpr.restart_nginx()


def new_small_alpha():
    return _new_alpha(30, SMALL, 2, False)


def new_large_alpha():
    return _new_alpha(LARGE_STORAGE_GB, LARGE_INSTANCE_TYPE, LARGE_FE_PROCS, True)


def _new_alpha(storage, itype, fe_procn, backend):
    inst = get_new_inst(storage, itype)
    tpr = get_tpr(inst)
    full_setup_from_nothing(tpr, ALPHA_DOMAIN, fe_procn, backend=backend)
    new_tpr = get_tpr(associate_id(inst, False))
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
    for inst in ec2.create_instances(  # pyright: ignore[reportAttributeAccessIssue]
        ImageId=_last_img(),
        InstanceType=LARGE_INSTANCE_TYPE,
        KeyName=key_name,
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
    tpr = _local_tpr()
    branch = (
        subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    )
    full_setup_from_nothing(tpr, ALPHA_DOMAIN, 3, True, branch=branch)


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
    tpr.setup_fe_services(LIVE_DOMAIN, bun=True, procs=LARGE_FE_PROCS)
    tpr.update_env()
    tpr.update_fe()
    tpr.ssh.prun(f"sudo rm -f {NGINX_ENDIR}/{ALPHA_DOMAIN}")
    tpr.setup_nginx(cert=False)
    tpr.add_domain_fw(FW_DOMAIN, cert=False)
    tpr.restart_nginx()
    time.sleep(10)
    associate_id(alpha_inst, True)
    time.sleep(5)
    get_running_tpr(True).refresh_certs(FW_DOMAIN)


def associate_id(inst, live: bool):
    ipa = live_ip_alloc if live else alpha_ip_alloc
    ec2c.associate_address(InstanceId=inst.id, AllocationId=ipa.alloc_id)
    inst.reload()
    return inst


def tryfloat(s):
    try:
        return float(s)
    except:
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


def _last_vns():
    tag_str = subprocess.check_output(
        ["git", "describe", "--tags", "--abbrev=0"]
    ).decode()
    return _parse_v(tag_str)


def _parse_v(tag_str):
    return list(map(int, re.findall(r"^v(\d+)\.(\d+)\.(\d+)$", tag_str)[0]))
