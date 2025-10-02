import multiprocessing
import os
import random
import re
import smtplib
import subprocess
import time
from email.mime.text import MIMEText

import requests

from .deploy import LIVE_DOMAIN

EMAIL_ADDRESS = os.environ["GMAIL_ADDR"]
EMAIL_PASSWORD = os.environ["GMAIL_APP_PW"]
TO_EMAIL = EMAIL_ADDRESS
IP = "63.177.45.140"
WARN_AT_FILES = 300
WARN_AT_FULL = 92
WARN_AT_RAM = 1.2


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
    msg = MIMEText(f"{subprocess.check_output(['hostname']).decode().strip()}:\n{body}")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())


def err_w(subject, e: Exception):
    return warn(subject, f"{type(e).__name__}({str(e)})")


if __name__ == "__main__":
    started = False
    while True:
        try:
            with multiprocessing.Pool(1) as pool:
                try:
                    pool.map_async(validate, [1]).get(timeout=10)
                except Exception as e1:
                    print("missed 6sec timeout")
                    try:
                        pool.map_async(validate, [1]).get(timeout=20)
                    except Exception as e:
                        err_w("Rankless Failed Validation", e)
            try:
                status_dic = requests.get(f"http://{IP}:5566/status").json()
            except:
                warn("Rankless failed getting status json", "")
                continue
            full_pct = status_dic["fs_use_pct"]
            if full_pct >= 97.5:
                warn("Rankless filling", f"getting full {full_pct}")
                time.sleep(20)
                continue
            nfiles = status_dic["open_files"]
            if nfiles > WARN_AT_FILES:
                warn("Rankless too many open files", str(nfiles))
                time.sleep(60)
            if status_dic["fs_use_pct"] > WARN_AT_FULL:
                warn("Rankless running out of space", str(status_dic))
                time.sleep(60)
            if status_dic["memory_free_gb"] < WARN_AT_RAM:
                warn("Rankless running out of ram", str(status_dic))
                time.sleep(60)
            if not started:
                started = True
                warn(
                    "Rankless monitoring",
                    f"just started at {full_pct}% full {nfiles} open",
                )
        except Exception as e:
            err_w("Rankless Down", e)
        time.sleep(20)
