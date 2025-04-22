import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv
from tqdm.notebook import tqdm

load_dotenv()

SERIVCE_DIR = ".config/systemd/user"
SSL_ETC_DIR = "/etc/letsencrypt/live"
LOCAL_SSL_TAR = "ssl_dir.tar.gz"
AMI_IMG_CSV = "ami-imgs.csv"

ALPHA_DOMAIN = "alpha.rankless.org"
LIVE_DOMAIN = "www.rankless.org"
FW_DOMAIN = "rankless.org"

FE_UPSTREAM = "rankless_frontend"
BE_UPSTREAM = "rankless_backend"

BIG16 = "c6a.4xlarge"
SMALL = "c6a.large"

LARGE_INSTANCE_TYPE = BIG16
LARGE_STORAGE_GB = 500
LARGE_FE_PROCS = 12
DEFAULT_RS_PORT = 3038
BUN_PORT_START = 3000


NGINX_AVDIR, NGINX_ENDIR = [f"/etc/nginx/sites-{s}" for s in ["available", "enabled"]]

be_service_name = "rankless-backend.service"
fe_service_template_name = "rankless-frontend@.service"
tunnel_service_name = "rankless-tunnel.service"

be_service_frame = """
[Unit]
Description=Rankless Backend

[Service]
LimitNOFILE=65534
ExecStart={}/target/release/rankless-server {}
Restart=always
RestartSec=15

[Install]
WantedBy=default.target
"""

local_tmp_home = Path("/tmp/rls-services")
local_service_path = local_tmp_home / SERIVCE_DIR
local_service_path.mkdir(exist_ok=True, parents=True)

local_data_root = os.environ["OA_ROOT"]
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
    "authors-rel-insts",
]


aws_profile = os.environ.get("AWS_PROFILE")
key_name = os.environ["RL_KEY_ID"]
key_path = os.environ["RL_KEY_PATH"]

ubuntu24_image_id = "ami-0f67ca03a667867bb"
image_id = ubuntu24_image_id


@dataclass
class IpAlloc:
    ip: str
    alloc_id: str


@dataclass
class UpstreamConf:
    fe_ports: list[int]
    ip: str = "127.0.0.1"
    be_port: int = DEFAULT_RS_PORT

    def be_server(self):
        return self.sconf(self.be_port)

    def fe_servers(self):
        return map(self.sconf, self.fe_ports)

    def sconf(self, port):
        return f"server {self.ip}:{port};"


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
    for inst in ec2.instances.all():
        if inst.public_ip_address == ip:
            return inst


def get_dangling_instances():
    ips = [live_ip_alloc.ip, alpha_ip_alloc.ip]
    return [inst for inst in ec2.instances.all() if inst.public_ip_address not in ips]


def get_new_inst(vol_size: int, itype: str):
    block_device = {
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "VolumeSize": vol_size,
            "VolumeType": "gp3",
            "DeleteOnTermination": True,
        },
    }
    inst = ec2.create_instances(
        ImageId=ubuntu24_image_id,
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
    def __init__(self, host, user=None, key_path=None, reset=False):
        if reset:
            hp = Path.home() / ".ssh" / "known_hosts"
            subprocess.check_output(["ssh-keygen", "-f", hp.as_posix(), "-R", host])
        self.basis = ["ssh", "-o", "StrictHostKeyChecking=no"]
        self.key_extend = []
        self.rsync_basis = ["rsync", "-rav", "-z"]
        if key_path:
            self.key_extend.extend(["-i", key_path])
            self.rsync_basis.extend(["-e", f"ssh -i {key_path}"])
        self.basis.extend(self.key_extend)
        self.full_host = host if user is None else f"{user}@{host}"
        self.basis.append(self.full_host)

    def run(self, comm):
        return subprocess.check_output([*self.basis, comm]).decode()

    def prun(self, comm):
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
        for _ in range(10):
            try:
                sshc.run("echo working")
                break
            except Exception as e:
                print(e)
                time.sleep(10)
        self.ssh = sshc
        self.inst_home = sshc.run("pwd").strip()
        self.deploy_dir = self.inst_home + "/rankless-deploy"
        self.data_dir = self.inst_home + "/rankless-data"
        self.systemd_dir = f"{self.inst_home}/{SERIVCE_DIR}/"
        cache_dir = f"{self.inst_home}/nginx-cache"
        self.be_cache_dir = f"{cache_dir}/be"
        self.fe_cache_dir = f"{cache_dir}/fe"
        self.ssh.prun(
            f"mkdir -p {self.data_dir} {self.deploy_dir} {self.systemd_dir} {self.be_cache_dir} {self.fe_cache_dir}"
        )
        self.be_service = ServiceMan(be_service_name, sshc)
        self.fe_services = []
        self.fill_fe_services()

    def get_node_v(self):
        return self.ssh.run("source .nvm/nvm.sh;nvm version").strip()

    def validate(self):
        print(self.get_node_v())
        self.ssh.prun("source .profile;cargo --version")

    def clean_caches(self):
        self.ssh.prun(f"rm -rf {self.data_dir}/cache")
        self.ssh.prun(f"sudo rm -rf {self.be_cache_dir}/*")
        self.ssh.prun(f"sudo rm -rf {self.fe_cache_dir}/*")

    def setup(self, backend=True, bun=False):
        self.ssh.prun("sudo apt update")
        self.ssh.prun(
            "sudo apt install unzip certbot build-essential python3-certbot-nginx nginx -y"
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

    def sync_txt(self, txt, name, dir):
        p = Path(name)
        existed = p.exists()
        past_blob = b""
        if existed:
            past_blob = p.read_bytes()
        p.write_text(txt)
        self.ssh.prsync(p, dir)
        p.unlink()
        if existed:
            p.write_bytes(past_blob)

    def sync_service(self, txt, name):
        self.sync_txt(txt, name, self.systemd_dir)

    def setup_be_service(self):
        be_service_txt = be_service_frame.format(self.deploy_dir, self.data_dir)
        self.sync_service(be_service_txt, be_service_name)
        self.be_service.enable()

    def setup_fe_service(
        self, inst_dns: str, node_port_start=BUN_PORT_START, procs=10, bun=False
    ):
        if bun:
            comm = "%h/.bun/bin/bun run build/"
        else:
            node_version = self.get_node_v()
            comm = f"%h/.nvm/versions/node/{node_version}/bin/node build"
        fe_service_txt = f"""
[Unit]
Description=Rankless Frontend %i
After=network.target

[Service]
WorkingDirectory={self.deploy_dir}
Environment=ORIGIN=https://{inst_dns} PORT=%i
ExecStart={comm}
Restart=always
RestartSec=15

[Install]
WantedBy=default.target
"""
        self.sync_service(fe_service_txt, fe_service_template_name)
        for i in range(procs):
            sman = self.fes_from_port(node_port_start + i)
            sman.enable()
            self.fe_services.append(sman)

    def fes_from_port(self, port):
        return ServiceMan(fe_service_template_name.replace("@", f"@{port}"), self.ssh)

    def get_fe_ports(self):
        fe_rex = re.compile(fe_service_template_name.replace("@", r"@(\d+)"))
        return list(map(int, fe_rex.findall(self.ssh.run("systemctl --user"))))

    def fill_fe_services(self):
        self.fe_services = [self.fes_from_port(p) for p in self.get_fe_ports()]

    def get_dns(self):
        return re.findall(
            "ORIGIN=https://(.*) ",
            self.ssh.run(f"cat ~/{SERIVCE_DIR}/{fe_service_template_name}"),
        )[0]

    def setup_nginx(self, inst_dns=None, rs_port=DEFAULT_RS_PORT, cert=True):
        if inst_dns is None:
            inst_dns = self.get_dns()
        if cert:
            self.get_cert(inst_dns)
        ports = self.get_fe_ports()
        assert ports
        self.nginx_add_upstreams([UpstreamConf(ports)])
        self.ssh.prun(f"mkdir -p {self.fe_cache_dir} {self.be_cache_dir}")
        cert_dir = f"{SSL_ETC_DIR}/{inst_dns}"
        server_prefix = f"""
    server_name {inst_dns};

    ssl_certificate {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    access_log /var/log/nginx/access.log upstream_time;
"""
        loc_suffix = """
        proxy_cache_use_stale error timeout http_500 http_502 http_503 http_504;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
"""

        nginx_conf = f"""
proxy_cache_path {self.be_cache_dir} levels=1:2 keys_zone=be-cache:50m max_size=20g;
proxy_cache_path {self.fe_cache_dir} levels=1:2 keys_zone=fe-cache:50m max_size=10g;
limit_req_zone $binary_remote_addr zone=baselimit:10m rate=2r/s;

log_format upstream_time '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent"'
                         'rt=$request_time uct="$upstream_connect_time" uht="$upstream_header_time" urt="$upstream_response_time"';

server {{
    listen 443 ssl;
    {server_prefix}

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1000;   

    location / {{
        proxy_pass http://{FE_UPSTREAM};
        proxy_cache fe-cache;
        {loc_suffix}
        limit_req zone=baselimit burst=60;
    }}
}}

server {{
    listen {rs_port + 1} ssl;
    {server_prefix}

    location / {{
        proxy_pass http://{BE_UPSTREAM};
        proxy_cache be-cache;
        {loc_suffix}
        limit_req zone=baselimit burst=80;
    }}
}}

# Redirect HTTP to HTTPS
server {{
   listen 80;
   server_name {inst_dns};
   return 301 https://$server_name$request_uri;
}}
        """
        self._send_nginx_conf(nginx_conf, inst_dns)
        self.restart_nginx()

    def clean_cert_default(self):
        self._send_nginx_conf("", "default")

    def get_cert(self, dns):
        self.ssh.prun(
            f"sudo certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d {dns}"
        )
        self.clean_cert_default()

    def pull_certs(self):
        self.ssh.prun(f"sudo tar zpcvf {LOCAL_SSL_TAR} /etc/letsencrypt/")
        self.ssh.download(f"{self.inst_home}/{LOCAL_SSL_TAR}")

    def push_certs(self):
        self.ssh.rsync(LOCAL_SSL_TAR, self.inst_home)
        self.ssh.prun(f"sudo tar zxvf {LOCAL_SSL_TAR} -C /")

    def refresh_certs(self, *other_domains):
        for domain in [self.get_dns(), *other_domains]:
            self.get_cert(domain)

    def add_dns_fw(self, dns_to_fw: str, cert=True):
        orig_dns = self.get_dns()
        nginx_conf = f"""
server {{
    listen 80;
    listen [::]:80;
    server_name {dns_to_fw};
    return 301 https://{orig_dns}$request_uri;
}}

server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {dns_to_fw};

    ssl_certificate {SSL_ETC_DIR}/{dns_to_fw}/fullchain.pem;
    ssl_certificate_key {SSL_ETC_DIR}/{dns_to_fw}/privkey.pem;
    
    include /etc/letsencrypt/options-ssl-nginx.conf;

    return 301 https://{orig_dns}$request_uri;
}}
"""
        self._send_nginx_conf(nginx_conf, dns_to_fw)
        if cert:
            self.get_cert(dns_to_fw)

    def nginx_add_upstreams(self, upstreams: list[UpstreamConf]):
        us_etc_name = "app_upstreams"
        fe_servers = []
        be_servers = []
        for conf in upstreams:
            fe_servers.extend(conf.fe_servers())
            be_servers.append(conf.be_server())

        fe_conf = "    \n".join(fe_servers)
        be_conf = "    \n".join(be_servers)
        conf_txt = f"""
upstream {FE_UPSTREAM} {{
    {fe_conf}
}}

upstream {BE_UPSTREAM} {{
     {be_conf}
}}
"""
        self._send_nginx_conf(conf_txt, us_etc_name)

    def restart_nginx(self):
        self._nginx_run(["reload", "restart", "status"])

    def reload_nginx(self):
        self._nginx_run(["reload", "status"])

    def sync_data_to(self):
        for subdir in tqdm(data_subdirs):
            self.ssh.rsync(f"{local_data_root}/{subdir}", self.data_dir, ignores)

    def setup_code(self):
        self.ssh.prun(
            f"git clone https://github.com/endremborza/rankless {self.deploy_dir}"
        )
        self.update_env()

    def sync_code(self):
        self.ssh.prun(f"cd {self.deploy_dir} && git pull")
        self.update_env()

    def build_js(self):
        self.ssh.prun(
            f"cd {self.deploy_dir};source ~/.profile;source ~/.nvm/nvm.sh;npm install;npm run build"
        )

    def build_rs(self):
        self.ssh.prun(f"cd {self.deploy_dir};source ~/.profile;cargo build --release")

    def update_env(self):
        dns = self.get_dns()
        txt = f"PUBLIC_ORIGIN=https://{dns}\nOA_ROOT={self.data_dir}"
        self.sync_txt(txt, ".env", self.deploy_dir)

    def update_fe(self):
        self.sync_code()
        self.build_js()
        for fes in self.fe_services:
            fes.restart()

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


def sync_fe_to_live():
    get_running_tpr(True).update_fe()


def new_small_alpha(pushed_certs: bool):
    assert get_running_inst(False) is None
    new_alpha_inst = get_new_inst(30, SMALL)
    tpr = get_tpr(new_alpha_inst)
    tpr.setup(backend=False, bun=True)
    tpr.setup_fe_service(ALPHA_DOMAIN, bun=True, procs=2)
    tpr.setup_code()
    tpr.build_js()
    for fes in tpr.fe_services:
        fes.start()
    if pushed_certs:
        tpr.push_certs()
        tpr.setup_nginx(cert=False)
    ec2c.associate_address(
        InstanceId=new_alpha_inst.id, AllocationId=alpha_ip_alloc.alloc_id
    )
    new_alpha_inst.reload()
    if not pushed_certs:
        get_tpr(new_alpha_inst).setup_nginx(cert=True)
    return new_alpha_inst


def new_large_alpha():
    inst = ec2.create_instances(
        ImageId=_last_img(),
        InstanceType=LARGE_INSTANCE_TYPE,
        KeyName=key_name,
        MinCount=1,
        MaxCount=1,
    )[0]
    inst.wait_until_running()
    inst.load()
    tpr = get_tpr(inst)
    tpr.setup_fe_service(ALPHA_DOMAIN, bun=True, procs=LARGE_FE_PROCS)
    tpr.update_fe()
    tpr.be_service.start()
    tpr.setup_nginx(cert=False)
    return associate_id(inst, False)


def new_large_image():
    v = subprocess.check_output(["git", "tag", "--points-at", "HEAD"]).decode().strip()
    vns = _parse_v(v)
    inst = get_new_inst(LARGE_STORAGE_GB, LARGE_INSTANCE_TYPE)
    tpr = get_tpr(inst)
    tpr.setup(backend=True, bun=True)
    tpr.validate()
    tpr.setup_fe_service(LIVE_DOMAIN, bun=True, procs=LARGE_FE_PROCS)
    tpr.setup_code()
    tpr.build_js()
    tpr.build_rs()
    tpr.sync_data_to()
    tpr.setup_be_service()
    tpr.push_certs()
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
    return image_id


def horizontal_instances(n):
    ips = []
    for inst in ec2.create_instances(
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


def bump_v():
    vns = _last_vns()
    next_v = f"v{vns[0]}.{vns[1]}.{vns[2] + 1}"
    subprocess.call(["git", "tag", next_v])
    # git push origin tag <tag_name>
    # not recommended
    # git push --tags
    # annoted, within the ancestors tags
    # git push --follow-tags


def promote_alpha_to_live():
    alpha_inst = get_running_inst(False)
    assert alpha_inst is not None
    tpr = get_tpr(alpha_inst)
    tpr.setup_fe_service(LIVE_DOMAIN, bun=True, procs=LARGE_FE_PROCS)
    tpr.update_env()
    tpr.update_fe()
    tpr.ssh.prun(f"sudo rm {NGINX_ENDIR}/{ALPHA_DOMAIN}")
    tpr.setup_nginx(cert=False)
    tpr.add_dns_fw(FW_DOMAIN, cert=False)
    associate_id(alpha_inst, True)
    tpr.refresh_certs(FW_DOMAIN)


def associate_id(inst, live: bool):
    ipa = live_ip_alloc if live else alpha_ip_alloc
    ec2c.associate_address(InstanceId=inst.id, AllocationId=ipa.alloc_id)
    inst.reload()
    return inst


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
