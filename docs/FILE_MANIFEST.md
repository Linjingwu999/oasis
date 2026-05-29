# File Manifest

This manifest records how the original working files were renamed and organized
for the GitHub-ready supplementary code package.

| GitHub-ready file | Role |
|---|---|
| `scripts/supplementary_code_s2_oasisid_retrieval_statistics.py` | OasisID retrieval, aggregation, AreaID rank check, and optional geometry QA script. |
| `scripts/landcover_product_sensitivity/run_workflow.py` | Unified command-line entry point for the ESA/Dynamic World product-sensitivity workflow. |
| `scripts/landcover_product_sensitivity/pilot_north_america_na02_analysis.py` | North America NA_02 pilot/test analysis script. |
| `scripts/landcover_product_sensitivity/submit_global_non_na_gee_tasks.py` | Python Earth Engine API batch submission script for global non-North-America tiles. |
| `scripts/landcover_product_sensitivity/auto_submit_global_non_na_gee_tasks.py` | Optional unattended monitor and batch-submission helper. |
| `scripts/landcover_product_sensitivity/download_gee_results_rclone.py` | Optional local rclone helper for downloading GEE-exported CSV files. |
| `scripts/landcover_product_sensitivity/merge_global_non_na_with_north_america.py` | Final merge/statistics script for global non-North-America and North America CSV outputs. |
| `scripts/landcover_product_sensitivity/gee_code_editor_global_non_na_esa_dw_2020.js` | Google Earth Engine Code Editor script for global non-North-America ESA/Dynamic World statistics. |
| `scripts/landcover_product_sensitivity/gee_code_editor_arabian_peninsula_test_esa_dw_2020.js` | Regional test/debugging GEE Code Editor script for the Arabian Peninsula. |
| `figures/Supplementary_Figure_S2_OasisID_workflow.png` | Supplementary workflow figure for the OasisID retrieval/statistics/QA procedure. |

Private files such as `rclone.conf`, Google OAuth tokens, local credentials,
downloaded CSV batches, and local logs are intentionally excluded.

