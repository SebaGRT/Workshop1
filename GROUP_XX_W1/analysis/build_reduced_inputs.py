"""Rebuild the small, inspectable W1 input extracts from official source ZIPs.

The full official archives are intentionally outside the submission. Put them in
data/source_cache/{Urgencias,REM}/<year>/ or pass --source-root to a directory
containing the original Urgencias/ and REM/ folders.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
OUTPUT = PACKAGE / "data" / "input"
P2_CODES = {"P2060000", *(f"P20705{i:02d}" for i in range(1, 7)), "P2501800"}


def emergency_extract(source_root: Path) -> None:
    frames = []
    for year, weeks in ((2023, (20, 21)), (2024, (20,))):
        path = source_root / "Urgencias" / str(year) / f"AtencionesUrgencia{year}.zip"
        with ZipFile(path) as archive, archive.open(f"AtencionesUrgencia{year}.csv") as raw:
            for chunk in pd.read_csv(raw, sep=";", encoding="latin1", chunksize=250_000, low_memory=False):
                part = chunk.loc[chunk["semana"].isin(weeks) & chunk["IdCausa"].isin((1, 2))].copy()
                if not part.empty:
                    part.insert(0, "AnioFuente", year)
                    frames.append(part)
    output = OUTPUT / "urgencias_2023w20w21_2024w20_id1_id2.csv.gz"
    pd.concat(frames, ignore_index=True).to_csv(output, index=False, compression="gzip")
    print(f"{output.relative_to(PACKAGE)}: {sum(map(len, frames)):,} source rows")


def rem_extract(source_root: Path) -> None:
    frames = []
    usecols = ["Mes", "IdServicio", "IdEstablecimiento", "CodigoPrestacion"] + [f"Col{i:02d}" for i in range(1, 32)]
    for year in range(2020, 2025):
        path = source_root / "REM" / str(year) / f"SERIE_REM_{year}.zip"
        with ZipFile(path) as archive:
            members = [name for name in archive.namelist() if Path(name).name.lower().startswith("seriep") and Path(name).suffix.lower() in (".csv", ".txt")]
            if len(members) != 1:
                raise ValueError(f"Expected one SerieP member in {path}; found {members}")
            with archive.open(members[0]) as raw:
                for chunk in pd.read_csv(raw, sep=";", usecols=usecols, dtype={"IdServicio": "string", "IdEstablecimiento": "string", "CodigoPrestacion": "string"}, chunksize=200_000, encoding="utf-8-sig", low_memory=False):
                    part = chunk.loc[chunk["CodigoPrestacion"].str.strip().isin(P2_CODES)].copy()
                    if not part.empty:
                        part.insert(0, "AnioFuente", year)
                        frames.append(part)
    output = OUTPUT / "rem_p2_2020_2024_selected_codes.csv.gz"
    pd.concat(frames, ignore_index=True).to_csv(output, index=False, compression="gzip")
    print(f"{output.relative_to(PACKAGE)}: {sum(map(len, frames)):,} source rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=PACKAGE / "data" / "source_cache")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    emergency_extract(args.source_root)
    rem_extract(args.source_root)
