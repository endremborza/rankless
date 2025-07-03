import multiprocessing
import os
import random
import re
import smtplib
import subprocess
import time
from email.mime.text import MIMEText

import requests

from .deploy import get_running_tpr

EMAIL_ADDRESS = os.environ["GMAIL_ADDR"]
EMAIL_PASSWORD = os.environ["GMAIL_APP_PW"]
TO_EMAIL = EMAIL_ADDRESS

url = "https://www.rankless.org/"


def val_url(url):
    r = requests.get(url)
    assert r.ok, f"{url} failed with {r.status_code}"
    t = r.elapsed.microseconds / 1_000_000
    assert t < 1.2, f"{url} took {t}s"
    return r


def validate(n=1):
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
                    res = pool.map_async(validate, [1]).get(timeout=6)
                except Exception as e:
                    err_w("Rankless Failed Validation", e)
                try:
                    ltpr = pool.map_async(get_running_tpr, [True]).get(timeout=10)[0]
                except Exception as e:
                    err_w("Rankless ssh error", e)
                    time.sleep(10)
                    continue
            try:
                rem_bytes, full_pct = ltpr.get_storage_stats()
            except:
                warn("Error getting ssh info", "")
                continue
            if full_pct >= 97:
                warn("Rankless filling", f"getting full {full_pct}")
                time.sleep(20)
                continue
            nfiles = None
            for _ in range(5):
                try:
                    nfiles = ltpr.get_backend_open_files_df().shape[0]
                    break
                except:
                    pass
            if nfiles is None:
                warn("Rankless no backend", "nfiles not found")
                time.sleep(60)
            elif nfiles > 120:
                warn("Rankless too many open files", str(nfiles))
                time.sleep(60)
            if not started:
                started = True
                warn(
                    "Rankless monitoring",
                    f"just started {rem_bytes / 1e6} at {full_pct}% full {nfiles} open",
                )
        except Exception as e:
            err_w("Rankless Down", e)
        time.sleep(20)
