"""
Step 1 of the ML pipeline: download free, public datasets.

Datasets (all free, no login needed):
  1. UCI SMS Spam Collection      -> labelled SMS messages (spam / ham)
  2. UCI PhiUSIIL Phishing URLs    -> ~235k labelled URLs (phishing / legitimate)
  3. OpenPhish community feed      -> fresh, live phishing URLs (extra positives)

Run:  python ml/download_data.py
Output goes to ml/data/raw/
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import requests

RAW = Path(__file__).parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "sms_spam": "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
    "phiusiil": "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip",
    "openphish": "https://openphish.com/feed.txt",
}
HEADERS = {"User-Agent": "scamshield-student-project/1.0"}


def fetch(url: str) -> bytes:
    print(f"  downloading {url}")
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.content


def extract_zip(data: bytes, target: Path) -> None:
    """Extract a zip safely (refuse paths that escape the target folder)."""
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            dest = (target / member).resolve()
            if not str(dest).startswith(str(target.resolve())):
                raise RuntimeError(f"Unsafe path in zip: {member}")
        zf.extractall(target)


def main() -> int:
    ok = True
    for name, url in SOURCES.items():
        print(f"[{name}]")
        try:
            data = fetch(url)
            if url.endswith(".zip"):
                extract_zip(data, RAW / name)
            else:
                (RAW / f"{name}.txt").write_bytes(data)
            print("  done")
        except Exception as exc:  # keep going, other datasets may still work
            ok = False
            print(f"  FAILED: {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
