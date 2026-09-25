"""Download only the official archives required to rerun the submitted notebooks."""

import csv
import hashlib
import urllib.request
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / "data" / "source_manifest.csv"

with MANIFEST.open(encoding="utf-8", newline="") as handle:
    sources = list(csv.DictReader(handle))

for item in sources:
    destination = PACKAGE / item["source_path"]
    expected = item["sha256"].lower()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        digest = hashlib.file_digest(destination.open("rb"), "sha256").hexdigest()
        if digest == expected:
            print(f"Verified: {destination.relative_to(PACKAGE)}")
            continue
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(item["final_url"], timeout=60) as response, temporary.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    with temporary.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != expected:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"SHA-256 mismatch for {destination.name}; source may have changed")
    temporary.replace(destination)
    print(f"Downloaded and verified: {destination.relative_to(PACKAGE)}")
