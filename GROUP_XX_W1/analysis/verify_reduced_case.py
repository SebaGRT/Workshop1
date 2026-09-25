"""Recompute the W1 spot checks from the reduced input extracts."""

from pathlib import Path

import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
INPUT = PACKAGE / "data" / "input"
OUTPUT = PACKAGE / "data" / "processed"
OUTPUT.mkdir(parents=True, exist_ok=True)

emergency = pd.read_csv(INPUT / "urgencias_2023w20w21_2024w20_id1_id2.csv.gz")
weekly = (emergency.groupby(["AnioFuente", "semana", "IdCausa"], as_index=False)["Total"]
          .sum().pivot(index=["AnioFuente", "semana"], columns="IdCausa", values="Total")
          .rename(columns={1: "total_urgencias", 2: "urgencias_respiratorias"}).reset_index())
weekly["pct_respiratorio"] = 100 * weekly["urgencias_respiratorias"] / weekly["total_urgencias"]
weekly = weekly.rename(columns={"AnioFuente": "year", "semana": "week", "total_urgencias": "all_emergency_visits", "urgencias_respiratorias": "respiratory_visits", "pct_respiratorio": "respiratory_share_pct"})
weekly.to_csv(OUTPUT / "urgencias_weekly_spot_check.csv", index=False)

rem = pd.read_csv(INPUT / "rem_p2_2020_2024_selected_codes.csv.gz", dtype={
    "IdServicio": "string", "IdEstablecimiento": "string", "CodigoPrestacion": "string"})
keys = ["AnioFuente", "Mes", "IdServicio", "IdEstablecimiento"]
identity = keys + ["CodigoPrestacion"] + [f"Col{i:02d}" for i in range(1, 32)]
rem = rem.dropna(subset=keys).drop_duplicates(subset=identity)
counts = rem.groupby(keys + ["CodigoPrestacion"], dropna=False).size().rename("count").reset_index()
conflicts = counts.loc[counts["count"] > 1, keys].drop_duplicates()
if not conflicts.empty:
    rem = rem.merge(conflicts.assign(_conflict=1), on=keys, how="left")
    rem = rem.loc[rem["_conflict"].isna()].drop(columns="_conflict")
selected = rem.loc[rem["CodigoPrestacion"].isin(["P2060000", "P2070503", "P2070504"]),
                   keys + ["CodigoPrestacion", "Col01"]]
panel = selected.pivot(index=keys, columns="CodigoPrestacion", values="Col01").dropna().reset_index()
panel["numerator"] = panel["P2070503"] + panel["P2070504"]
summary = panel.groupby(["AnioFuente", "Mes"], as_index=False).agg(
    matched_units=("numerator", "size"), denominator=("P2060000", "sum"),
    numerator=("numerator", "sum"))
summary["matched_share_pct"] = 100 * summary["numerator"] / summary["denominator"]
summary = summary.rename(columns={"AnioFuente": "year", "Mes": "month"})
summary.to_csv(OUTPUT / "rem_p2_cut_spot_check.csv", index=False)

print(weekly.to_string(index=False))
print(summary[["year", "month", "matched_units", "matched_share_pct"]].to_string(index=False))
