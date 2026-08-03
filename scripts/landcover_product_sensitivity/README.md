# ESA WorldCover and Dynamic World product-sensitivity analysis

This folder contains the scripts used to compare oasis internal land-cover composition derived from **ESA WorldCover 2020** and **Dynamic World 2020 annual mode**. The workflow is designed as a supplementary-code component of the global oasis mapping paper.

## Rationale

The scripts are intentionally modular rather than merged into a single long script. The public workflow separates (i) GEE batch export and (ii) final merging and recalculation of percentages. This keeps the released code focused on the analysis steps needed to reproduce the reported product comparison.

## Main files

| File | Role | Core/utility |
|---|---|---|
| `run_workflow.py` | Unified entry point for status check, workflow display, and calling sub-scripts. | Core |
| `gee_code_editor_global_non_na_esa_dw_2020.js` | Google Earth Engine Code Editor script for global non-North-America tiles. | Core |
| `submit_global_non_na_gee_tasks.py` | Python Earth Engine API batch submitter for global non-North-America tiles. | Core |
| `merge_global_non_na_with_north_america.py` | Merges global non-North-America CSVs with North America CSVs and recalculates percentages from summed areas. | Core |

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

Merge already downloaded CSVs:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step merge
```

## Important notes

Percentages must not be averaged across tiles. The merging script first sums `Area_km2` by product and class and then recalculates percentages from the summed areas.

Do not publish Google OAuth tokens, local Google credentials, downloaded CSVs, or other private files. The repository `.gitignore` excludes common credential and output patterns.
