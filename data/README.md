# Data directory

Place required input files here when reproducing the analysis. Large datasets are not included in this code repository.

Suggested layout:

```text
data/
├── Table_S1_attribute_description_and_coding_information.xlsx
├── oasis_shapefiles/                         # optional, for geometry QA
└── GEE_ESA_DW_landcover_comparison/
    ├── GEE_Global_LC_ESA_DW_2020_skip_NA_csv/
    └── GEE_North_America_NA02_csv/
```

Do not commit private authorization files, downloaded bulk CSVs, shapefile bundles, or temporary data unless the repository release policy explicitly allows them.
