"""Audit duplicate facility/date/cause keys in the selected emergency source rows.

The official annual ZIPs are required. Download them with
``analysis/download_required_sources.py`` or pass ``--source-root`` to the
repository directory containing ``Urgencias/<year>/``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

PACKAGE = Path(__file__).resolve().parents[1]
CODES = {1, 2, 3, 4, 5, 6, 10, 11, 30, 31, 32, 33}
KEY = ["IdEstablecimiento", "fecha", "IdCausa"]


def audit(source_root: Path) -> pd.DataFrame:
    rows = []
    for year in range(2020, 2025):
        path = source_root / "Urgencias" / str(year) / f"AtencionesUrgencia{year}.zip"
        parts = []
        with ZipFile(path) as archive, archive.open(f"AtencionesUrgencia{year}.csv") as raw:
            for chunk in pd.read_csv(
                raw, sep=";", encoding="latin1", usecols=KEY + ["Total"],
                chunksize=500_000, low_memory=False,
            ):
                parts.append(chunk.loc[chunk["IdCausa"].isin(CODES)])
        selected = pd.concat(parts, ignore_index=True)
        duplicate_extra = selected.duplicated(KEY, keep="first")
        rows.append({
            "year": year,
            "selected_rows": len(selected),
            "duplicate_key_extras": int(duplicate_extra.sum()),
            "extra_total_visits": int(selected.loc[duplicate_extra & selected["IdCausa"].eq(1), "Total"].sum()),
            "extra_respiratory_visits": int(selected.loc[duplicate_extra & selected["IdCausa"].eq(2), "Total"].sum()),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=PACKAGE / "data" / "source_cache")
    args = parser.parse_args()
    result = audit(args.source_root)
    output = PACKAGE / "data" / "processed" / "duplicate_key_audit.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    print(result.to_string(index=False))
    print(f"Saved {output.relative_to(PACKAGE)}")
