# Global Oasis Supplementary Code

This repository contains supplementary code for the global high-resolution oasis
mapping and structural analysis study. The code is organized into two main
components:

1. OasisID retrieval, aggregation, and quality-control procedures based on the
   Table S1 attribute table.
2. ESA WorldCover 2020 vs. Dynamic World 2020 product-sensitivity analysis for
   oasis land-cover composition.

Large data files, downloaded Google Drive outputs, Earth Engine credentials, and
local authorization files are intentionally excluded.

## Repository Structure

```text
global-oasis-supplementary-code/
|-- README.md
|-- requirements.txt
|-- .gitignore
|-- data/
|   `-- README.md
|-- figures/
|   `-- Supplementary_Figure_S2_OasisID_workflow.png
|-- logs/
|   `-- README.md
|-- outputs/
|   `-- README.md
|-- docs/
|   `-- FILE_MANIFEST.md
`-- scripts/
    |-- supplementary_code_s2_oasisid_retrieval_statistics.py
    `-- landcover_product_sensitivity/
        |-- README.md
        |-- run_workflow.py
        |-- pilot_north_america_na02_analysis.py
        |-- submit_global_non_na_gee_tasks.py
        |-- auto_submit_global_non_na_gee_tasks.py
        |-- download_gee_results_rclone.py
        |-- merge_global_non_na_with_north_america.py
        |-- gee_code_editor_global_non_na_esa_dw_2020.js
        `-- gee_code_editor_arabian_peninsula_test_esa_dw_2020.js
```

## OasisID Retrieval and Quality Control

`scripts/supplementary_code_s2_oasisid_retrieval_statistics.py` demonstrates how
the OasisID coding framework and Table S1 can be used for reproducible
retrieval, continent- and basin-level aggregation, patch-level queries, AreaID
rank checking, and optional vector-geometry quality control.

Example:

```bash
python scripts/supplementary_code_s2_oasisid_retrieval_statistics.py \
  --table "data/Table_S1_attribute_description_and_coding_information.xlsx" \
  --continent AS \
  --basin 12 \
  --top-n 20 \
  --out outputs/S2_oasisid
```

Optional geometry checking requires `geopandas` and one or more vector files:

```bash
python scripts/supplementary_code_s2_oasisid_retrieval_statistics.py \
  --table "data/Table_S1_attribute_description_and_coding_information.xlsx" \
  --vector-folder "data/oasis_shapefiles" \
  --out outputs/S2_oasisid_geometry_QA
```

## ESA/Dynamic World Product-Sensitivity Analysis

The scripts in `scripts/landcover_product_sensitivity/` compare oasis internal
land-cover composition derived from ESA WorldCover 2020 and Dynamic World 2020
annual mode. The workflow includes Google Earth Engine computation scripts,
local pilot analysis, optional task/download utilities, and final
merge/statistical summaries.

Basic status check:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step status
```

Recommended workflow overview:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step workflow
```

Final merge after CSV export and download:

```bash
python scripts/landcover_product_sensitivity/run_workflow.py --step merge
```

More details are provided in
`scripts/landcover_product_sensitivity/README.md`.

## Data Not Included

The following files are required to fully reproduce the analysis but are not
included by default:

- Table S1 attribute table;
- split oasis vector files, if geometry QA is needed;
- GEE-exported CSV files;
- local Google Drive, rclone, or Earth Engine credential files.

Recommended data layout:

```text
data/
|-- Table_S1_attribute_description_and_coding_information.xlsx
`-- GEE_ESA_DW_landcover_comparison/
    |-- GEE_Global_LC_ESA_DW_2020_skip_NA_csv/
    `-- GEE_North_America_NA02_csv/
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For Earth Engine scripts, authenticate separately:

```bash
earthengine authenticate
```

## Reproducibility and Restart Behavior

The batch-processing scripts keep status files and logs so failed or unfinished
steps can be inspected and rerun. Percentages are recalculated after summing
`Area_km2`; tile-level percentages should not be averaged.

Do not commit credentials. The `.gitignore` file excludes `rclone.conf`, OAuth
tokens, Earth Engine private keys, raw downloaded CSVs, logs, and generated
outputs.

