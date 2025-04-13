import os
import random
import re
import smtplib
import time
from email.mime.text import MIMEText

import requests

from .deploy import get_running_tpr

EMAIL_ADDRESS = os.environ["GMAIL_ADDR"]
EMAIL_PASSWORD = os.environ["GMAIL_APP_PW"]
TO_EMAIL = EMAIL_ADDRESS
SUBJECT = "Rankless Down"
BODY = "Rankless Down!!"

url = "https://www.rankless.org/"


def val_url(url):
    r = requests.get(url)
    assert r.ok, f"{url} failed with {r.status_code}"
    t = r.elapsed.microseconds / 1_000_000
    assert t < 1.2, f"{url} took {t}s"
    return r


def validate():
    r = val_url(url)
    links = re.findall(r'href="\.\/([a-z]+?\/.+?)"', r.text)
    assert len(links) > 0, "no links found"
    val_url(url + random.choice(links))


def warn(e):
    msg = MIMEText(BODY + "\n" + str(e))
    msg["Subject"] = SUBJECT
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())


if __name__ == "__main__":
    started = False
    while True:
        try:
            validate()
            ltpr = get_running_tpr(True)
            rem_bytes, full_pct = map(
                int,
                re.findall(r"/dev/root.*?(\d+)\s+(\d+)% /\n", ltpr.ssh.run("df"))[0],
            )
            assert full_pct < 95, f"getting full {full_pct}"
            if not started:
                started = True
                raise RuntimeError(f"just started {rem_bytes / 1e6} at {full_pct}%")
            time.sleep(70)
        except Exception as e:
            print(e)
            warn(e)
