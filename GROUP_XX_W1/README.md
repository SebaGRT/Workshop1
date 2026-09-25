# Workshop 1 · Submission Package

**Team:** Benjamín Pinto and Sebastián Herrera  
**Group:** XX (not yet assigned; replace `XX` with the two-digit group number before submission)  
**Version:** September 25, 2026

## Reading order

1. Open `report/GROUP_XX_W1_Report.pdf`. This self-contained report covers both candidate lines, documentary support, initial data observations, comparison, provisional preference, instructor questions, later ML/dashboard potential, the Process record, and references.
2. Inspect `analysis/urgencias_respiratorias.ipynb` and `analysis/rem_p2.ipynb`. Both retain executed outputs. The first supports Candidate A; the second supports Candidate B.
3. Inspect `data/input/` and `data/processed/`. Input files are uncleaned extracts from official ZIP archives; processed files are checks computed from those extracts.
4. Use `data/source_manifest.csv` for the source URLs, download dates, sizes, and SHA-256 hashes. Official dictionaries and the assignment brief are in `data/reference/`.

`report/GROUP_XX_W1_Report.docx` is an editable English copy of the report. The [English Google Doc](https://docs.google.com/document/d/1yr28MOk6eWTMOoFIpBCnv9CIzfOCUTrpTGP9T3mb7Gs/edit) is also available for collaboration.

## Files and scope

| Path | Role |
| --- | --- |
| `data/input/urgencias_2023w20w21_2024w20_id1_id2.csv.gz` | Uncleaned reduced input: emergency records for weeks 20 and 21 of 2023 and week 20 of 2024, for cause IDs 1 and 2. Supports a check of peak demand. |
| `data/input/rem_p2_2020_2024_selected_codes.csv.gz` | Uncleaned reduced input: Serie P rows for P2060000, P2070501–P2070506, and P2501800, 2020–2024. |
| `data/processed/urgencias_weekly_spot_check.csv` | Generated table of totals and respiratory share for the selected weeks. |
| `data/processed/rem_p2_cut_spot_check.csv` | Generated table of matched shares by six-month reporting cut. |
| `data/processed/duplicate_key_audit.csv` | Full-source audit of facility/date/cause key duplicates in the selected emergency rows. |
| `analysis/build_reduced_inputs.py` | Exact filters and steps for extracting reduced inputs from the official ZIPs. |
| `analysis/verify_reduced_case.py` | Recreates both checks from the included reduced inputs. |
| `analysis/audit_duplicate_keys.py` | Rechecks duplicate facility/date/cause keys against all five official emergency ZIPs. |
| `analysis/download_required_sources.py` | Downloads the ZIPs needed to rerun the complete notebooks and verifies SHA-256 hashes. |

The five annual Urgencias ZIPs and five REM ZIPs total more than 1 GB. The brief permits omitting giant originals, so they are excluded from this archive. The source manifest records the versions downloaded on September 24, 2026 and their hashes. The package contains no virtual environments, caches, or credentials. `data/source_cache/` is created only when the full originals are reconstructed.

## Reproduction

Python 3 was used with pandas 2.2.3, NumPy 2.3.5, and openpyxl 3.1.5. The notebooks also use Matplotlib and IPython/Jupyter. Install dependencies with:

```bash
python -m pip install -r analysis/requirements.txt
```

From the extracted `GROUP_XX_W1` folder, verify the included reduced case with:

```bash
python analysis/verify_reduced_case.py
```

This works with the included files and refreshes `data/processed/`. To rebuild the extracts and rerun the complete notebooks, first download the official originals with an Internet connection:

```bash
python analysis/download_required_sources.py
python analysis/build_reduced_inputs.py
python analysis/audit_duplicate_keys.py
jupyter notebook analysis/urgencias_respiratorias.ipynb
jupyter notebook analysis/rem_p2.ipynb
```

The notebooks find the ZIPs under `data/source_cache/` and the emergency dictionary under `data/reference/`. Paths are relative to the package. After downloading the originals, restart each kernel, run all cells in order, and save the outputs. The submitted notebooks already contain outputs from runs on the originals. The duplicate-key audit found 12 extra keys in 2023 and three in 2024; the annual totals retain raw source rows, so the audit CSV records the small discrepancy. If a public portal has replaced a ZIP, SHA-256 verification will flag it; the manifest describes the version needed to reproduce the saved results exactly.

## Submission status

The group ID was not assigned when this package was prepared. Before submitting to Canvas, replace `XX` consistently in the root folder name, archive name, and both report filenames. Use the same ID for W1 and C1. Instructor feedback is recorded as pending in the report. No execution errors are known in the saved notebook outputs.

Official source files and field names remain in their original language so their definitions and hashes remain traceable to the published versions.
