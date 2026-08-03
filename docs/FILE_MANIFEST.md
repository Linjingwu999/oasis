# File Manifest

This manifest records how the original working files were renamed and organized
for the GitHub-ready supplementary code package.

| GitHub-ready file | Role |
|---|---|
| `scripts/supplementary_code_s2_oasisid_retrieval_statistics.py` | OasisID retrieval, aggregation, AreaID rank check, and optional geometry QA script. |
| `scripts/landcover_product_sensitivity/run_workflow.py` | Unified command-line entry point for the ESA/Dynamic World product-sensitivity workflow. |
| `scripts/landcover_product_sensitivity/submit_global_non_na_gee_tasks.py` | Python Earth Engine API batch submission script for global non-North-America tiles. |
| `scripts/landcover_product_sensitivity/merge_global_non_na_with_north_america.py` | Final merge/statistics script for global non-North-America and North America CSV outputs. |
| `scripts/landcover_product_sensitivity/gee_code_editor_global_non_na_esa_dw_2020.js` | Google Earth Engine Code Editor script for global non-North-America ESA/Dynamic World statistics. |

Private files such as `rclone.conf`, Google OAuth tokens, local credentials,
downloaded CSV batches, and local logs are intentionally excluded.
