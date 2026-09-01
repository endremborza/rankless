import datetime as dt
import json
import multiprocessing
import os
import random
import re
import smtplib
import subprocess
import time
from collections import deque
from email.mime.text import MIMEText

import requests

from .deploy import LIVE_DOMAIN, rolling_restart_live_fe

EMAIL_ADDRESS = os.environ["GMAIL_ADDR"]
EMAIL_PASSWORD = os.environ["GMAIL_APP_PW"]
IP = os.environ["RL_LIVE_IP"]
FILE_CHANNEL_ADDR = os.environ.get("FILE_CHANNEL_ADDR")
FILE_CHANNEL_TOKEN = os.environ.get("FILE_CHANNEL_TOKEN")
TO_EMAIL = EMAIL_ADDRESS
ALLOW_FE_RESTART = os.environ.get("ALLOW_RANKLESS_FE_RESTART")

WARN_AT_FILES = 500
WARN_AT_FULL = 92
WARN_AT_RAM = int(os.environ.get("WARN_AT_RAM", 10))

FAIL_SECONDS = 120
WAIT_SECONDS = 15
WAIT_POST_WARN = 50

LAST_SUCCESS = 0
ERROR_DEQUE = deque(maxlen=8)


def val_url(url):
    r = requests.get(url)
    assert r.ok, f"{url} failed with {r.status_code}"
    t = r.elapsed.microseconds / 1_000_000
    assert t < 1.2, f"{url} took {t}s"
    return r


def validate(n=1, url=f"https://{LIVE_DOMAIN}/"):
    r = val_url(url)
    links = re.findall(r'href="\.\/([a-z]+?\/.+?)"', r.text)
    assert len(links) > 0, "no links found"
    return [val_url(url + random.choice(links)) for _ in range(n)]


def warn(subject, body):
    msg = MIMEText(f"{get_selfname()}:\n{body}")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())
    time.sleep(WAIT_POST_WARN)


def get_selfname():
    return subprocess.check_output(["hostname"]).decode().strip()


def log_result(e=None, msg=None):
    if e is None:
        global LAST_SUCCESS
        LAST_SUCCESS = time.time()
    else:
        ERROR_DEQUE.append([dt.datetime.now().isoformat(), type(e).__name__, msg])
        print("added error ", type(e).__name__, msg)


def get_success_dic():
    try:
        url = FILE_CHANNEL_ADDR + "/files"  # pyright: ignore[reportOptionalOperand]
        return requests.get(url, timeout=5).json()
    except Exception:
        return {}


def read_records_and_warn():
    now = time.time()
    if (now - LAST_SUCCESS) < FAIL_SECONDS:
        return post_success()
    latest_remote_success = max(
        [0, *[d.get("time", 0) for d in get_success_dic().values()]]
    )
    print("reading remote records", latest_remote_success)
    if (now - latest_remote_success) < FAIL_SECONDS:
        print("remote success")
        return
    msg = "\n\n".join(" - ".join(e) for e in ERROR_DEQUE)
    warn("Rankless Failed Validation", msg)


def post_success():
    if FILE_CHANNEL_ADDR is not None:
        try:
            requests.post(
                FILE_CHANNEL_ADDR + "/upload",
                headers={"token": FILE_CHANNEL_TOKEN, "filename": get_selfname()},
                data=json.dumps(
                    {"time": int(LAST_SUCCESS), "errs": [*ERROR_DEQUE]}
                ).encode(),
                timeout=10,
            )
        except Exception as _:
            # raise e
            pass


def try_restarting_fe():
    if ALLOW_FE_RESTART:
        try:
            p = multiprocessing.Process(target=rolling_restart_live_fe)
            p.start()
            p.join(timeout=180)
            time.sleep(20)
        except Exception as e:
            print(f"failed restarting frontend {e}")


if __name__ == "__main__":
    started = False
    while True:
        if started:
            read_records_and_warn()
            time.sleep(WAIT_SECONDS)
        else:
            started = True
            warn(
                "Rankless monitoring",
                f"just started with\n{get_success_dic()}",
            )
            continue
        with multiprocessing.Pool(1) as pool:
            try:
                pool.map_async(validate, [2]).get(timeout=15)
                log_result()
            except Exception as e1:
                log_result(e1, "short time")
                try:
                    pool.map_async(validate, [1]).get(timeout=30)
                except Exception as e:
                    log_result(e, "long time")
        try:
            status_dic = requests.get(f"http://{IP}:5566/status").json()
        except Exception as e:
            print("failed status json")
            log_result(e, "status json")
            continue

        if status_dic["fs_use_pct"] >= 97.5:
            warn("Rankless filling", str(status_dic))
            continue
        if status_dic["fs_use_pct"] > WARN_AT_FULL:
            warn("Rankless running out of space", str(status_dic))
        if status_dic["open_files"] > WARN_AT_FILES:
            try_restarting_fe()
            warn("Rankless too many open files", str(status_dic))
        if status_dic["memory_free_gb"] < WARN_AT_RAM:
            try_restarting_fe()
            warn("Rankless running out of ram", str(status_dic))
