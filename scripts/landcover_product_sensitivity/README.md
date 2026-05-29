# ESA WorldCover and Dynamic World product-sensitivity analysis

This folder contains the scripts used to compare oasis internal land-cover composition derived from **ESA WorldCover 2020** and **Dynamic World 2020 annual mode**. The workflow is designed as a supplementary-code component of the global oasis mapping paper.

## Rationale

The scripts are intentionally modular rather than merged into a single long script. The workflow separates: (i) pilot analysis, (ii) GEE batch export, (iii) optional task monitoring, (iv) optional Google Drive download, and (v) final merging and recalculation of percentages. This makes the analysis easier to rerun, inspect, and document.

## Main files

| File | Role | Core/utility |
|---|---|---|
| `run_workflow.py` | Unified entry point for status check, workflow display, and calling sub-scripts. | Core |
| `gee_code_editor_global_non_na_esa_dw_2020.js` | Google Earth Engine Code Editor script for global non-North-America tiles. | Core |
| `submit_global_non_na_gee_tasks.py` | Python Earth Engine API batch submitter for global non-North-America tiles. | Core |
| `merge_global_non_na_with_north_america.py` | Merges global non-North-America CSVs with North America CSVs and recalculates percentages from summed areas. | Core |
| `pilot_north_america_na02_analysis.py` | North America NA_02 pilot/test result analysis. | Supporting |
| `auto_submit_global_non_na_gee_tasks.py` | Optional unattended GEE monitor and batch submitter. | Utility |
| `download_gee_results_rclone.py` | Optional rclone-based local download helper. | Utility |
| `gee_code_editor_arabian_peninsula_test_esa_dw_2020.js` | Arabian Peninsula test script for debugging and regional checks. | Supporting |

## Recommended commands

Show current local status:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step status
```

Show recommended workflow:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step workflow
```

Submit a global non-North-America batch, for example active-tile indexes 0--99:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step submit-global -- --batch-start-index 0 --batch-end-index 99
```

Rerun selected failed tiles:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step submit-global -- --failed-tile-ids 3497,3498,3609
```

Merge already downloaded CSVs:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step merge
```

Download exported CSVs with rclone, using a private local config file:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step download -- --rclone-config /path/to/private/rclone.conf
```

## Important notes

Percentages must not be averaged across tiles. The merging script first sums `Area_km2` by product and class and then recalculates percentages from the summed areas.

Do not publish `rclone.conf`, Google OAuth tokens, local Google credentials, downloaded CSVs, or other private files. The repository `.gitignore` excludes common credential and output patterns.
