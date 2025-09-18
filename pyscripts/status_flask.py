import json
import os
import threading
import time

import psutil
from flask import Flask, jsonify, send_file

from .deploy import be_service_name

app = Flask(__name__)

cgroup_procs_path = f"/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/{be_service_name}/cgroup.procs"
cache_enabled = True
cache_file = "/tmp/status_cache.json"
cache_interval = 3


def get_status():
    mem = psutil.virtual_memory()
    free_gb = mem.available / (1024**3)
    free_rate = mem.available / mem.total
    try:
        with open(cgroup_procs_path) as f:
            pids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        pids = []
    open_files = 0
    for pid in pids:
        fd_path = f"/proc/{pid}/fd"
        if os.path.isdir(fd_path):
            try:
                open_files += len(os.listdir(fd_path))
            except PermissionError:
                pass
    return {
        "memory_free_gb": round(free_gb, 2),
        "memory_free_pct": round(free_rate, 3),
        "open_files": open_files,
    }


def cache_updater():
    while True:
        status = get_status()
        with open(cache_file, "w") as f:
            json.dump(status, f)
        time.sleep(cache_interval)


@app.route("/status")
def status():
    if cache_enabled and os.path.exists(cache_file):
        return send_file(cache_file, mimetype="application/json")
    else:
        return jsonify(get_status())


if __name__ == "__main__":
    if cache_enabled:
        t = threading.Thread(target=cache_updater, daemon=True)
        t.start()
    app.run(host="0.0.0.0", port=5566)
