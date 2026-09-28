# Global Oasis Supplementary Code

This repository contains supplementary code for the global high-resolution oasis
mapping and structural analysis study.

The code provides OasisID retrieval, aggregation, and quality-control procedures based on the
   Table S1 attribute table.

Large data files and local authorization files are excluded.

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
    `-- supplementary_code_s2_oasisid_retrieval_statistics.py
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

## Data Not Included

The following files are required to fully reproduce the analysis but are not
included by default:

- Table S1 attribute table;
- split oasis vector files, if geometry QA is needed.

Recommended data layout:

```text
data/
|-- Table_S1_attribute_description_and_coding_information.xlsx
`-- oasis_shapefiles/
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Do not commit credentials. The `.gitignore` file excludes local credentials,
input datasets, logs, and generated outputs.

