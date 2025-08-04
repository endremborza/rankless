from time import sleep

from tqdm import tqdm

from .deploy import ALPHA_DOMAIN
from .live_monitoring import validate

if __name__ == "__main__":
    pbar = tqdm()
    while True:
        validate(3, url=f"https://{ALPHA_DOMAIN}/")
        sleep(1.5)
        pbar.update()
