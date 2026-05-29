#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Supplementary Code S2
OasisID-based retrieval, multi-scale aggregation, and quality control
for the global high-resolution oasis geospatial dataset.

Purpose
-------
This script demonstrates how the OasisID coding framework and the associated
attribute table can be used to support reproducible data retrieval, continent-
and basin-level aggregation, patch-level queries, and basic data-quality checks.
It is designed for the global oasis boundary dataset described in the manuscript.

Important note on country-level area statistics
-----------------------------------------------
This script does NOT calculate country-level oasis areas. Some oasis polygons are
associated with composite CountryID values because they intersect or are related
to multiple countries. Exact country-level area statistics should be calculated
by spatially overlaying the oasis boundary polygons with an authoritative national
boundary layer. Therefore, no country_summary.csv is produced here.

The script can run in two modes:
1) Attribute-table mode (recommended for lightweight reproduction):
   Use Table S1 only. This mode requires no geometry file and reproduces
   continent-, basin-, and patch-level summaries from the attribute table.

2) Optional geometry-check mode:
   If one or more vector files are supplied, the script additionally checks empty
   geometries, invalid geometries, duplicate OasisID values, and the consistency
   between geometry-derived area and the tabulated Area field.

Required input fields in Table S1
---------------------------------
OasisID, ContinentID, CountryID, BasinID, AreaID, Area, Longitude, Latitude, Perimeter

Example usage
-------------
# 1. Attribute table only
python Supplementary_Code_S2_OasisID_retrieval_statistics_no_country_area.py \
    --table "Table S1. Attribute description and coding information.xlsx" \
    --out S2_outputs

# 2. Attribute table + split oasis shapefiles
python Supplementary_Code_S2_OasisID_retrieval_statistics_no_country_area.py \
    --table "Table S1. Attribute description and coding information.xlsx" \
    --vector-folder "./oasis_shapefiles" \
    --out S2_outputs

# 3. Query examples
python Supplementary_Code_S2_OasisID_retrieval_statistics_no_country_area.py \
    --table "Table S1. Attribute description and coding information.xlsx" \
    --continent AS \
    --basin 12 \
    --top-n 20 \
    --out S2_outputs

Outputs
-------
CSV files are written to the output directory:
- QA_summary.csv
- duplicate_oasisid.csv
- missing_required_fields.csv
- invalid_coordinate_records.csv
- nonpositive_area_or_perimeter.csv
- continent_summary.csv
- basin_summary.csv
- top_largest_oases.csv
- query_result.csv
- areaid_rank_check.csv
- geometry_QA_summary.csv               (if vector files are supplied)
- geometry_area_comparison.csv          (if vector files are supplied)

Notes
-----
This script does not modify the oasis dataset. It provides reproducible examples
of data retrieval and aggregation using the OasisID-based coding framework.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "OasisID",
    "ContinentID",
    "CountryID",
    "BasinID",
    "AreaID",
    "Area",
    "Longitude",
    "Latitude",
    "Perimeter",
]

NUMERIC_COLUMNS = ["Area", "Longitude", "Latitude", "Perimeter"]


# -----------------------------------------------------------------------------
# I/O utilities
# -----------------------------------------------------------------------------

def ensure_output_dir(out_dir: str | Path) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and normalize common column-name variants."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    aliases = {
        "Oasis_ID": "OasisID",
        "Oasis Id": "OasisID",
        "Oasis id": "OasisID",
        "Continent": "ContinentID",
        "Country": "CountryID",
        "Basin": "BasinID",
        "Area_ID": "AreaID",
        "area": "Area",
        "AREA": "Area",
        "lon": "Longitude",
        "Lon": "Longitude",
        "longitude": "Longitude",
        "lat": "Latitude",
        "Lat": "Latitude",
        "latitude": "Latitude",
        "perimeter": "Perimeter",
        "PERIMETER": "Perimeter",
    }
    df = df.rename(columns={c: aliases.get(c, c) for c in df.columns})
    return df


def load_attribute_table(table_path: str | Path) -> pd.DataFrame:
    """Load Table S1 from .xlsx, .xls, or .csv."""
    table_path = Path(table_path)
    if not table_path.exists():
        raise FileNotFoundError(f"Input table not found: {table_path}")

    suffix = table_path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(table_path, sheet_name=0, keep_default_na=False)
    elif suffix == ".csv":
        df = pd.read_csv(table_path, keep_default_na=False)
    else:
        raise ValueError("Unsupported table format. Please use .xlsx, .xls, or .csv")

    df = clean_column_names(df)

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["OasisID", "ContinentID", "CountryID", "BasinID", "AreaID"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["nan", "None", "NaN"]), col] = np.nan

    return df


def write_csv(df: pd.DataFrame, out_path: Path) -> None:
    df.to_csv(out_path, index=False, encoding="utf-8-sig")


# -----------------------------------------------------------------------------
# Quality checks
# -----------------------------------------------------------------------------

def validate_required_columns(df: pd.DataFrame) -> List[str]:
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def make_quality_tables(df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """Create quality-control tables and return a QA summary."""
    summary_records = []

    missing_cols = validate_required_columns(df)
    summary_records.append({
        "Check": "Required columns missing",
        "Count": len(missing_cols),
        "Details": "; ".join(missing_cols) if missing_cols else "None",
    })

    if missing_cols:
        print("WARNING: Missing required columns:", missing_cols, file=sys.stderr)

    # Duplicate OasisID
    if "OasisID" in df.columns:
        dup_mask = df["OasisID"].duplicated(keep=False) & df["OasisID"].notna()
        duplicates = df.loc[dup_mask].sort_values("OasisID")
    else:
        duplicates = pd.DataFrame()
    write_csv(duplicates, out_dir / "duplicate_oasisid.csv")
    summary_records.append({
        "Check": "Duplicate OasisID records",
        "Count": int(len(duplicates)),
        "Details": "Rows with non-unique OasisID values",
    })

    # Missing required field values
    available_required = [c for c in REQUIRED_COLUMNS if c in df.columns]
    if available_required:
        missing_values = df[df[available_required].isna().any(axis=1)].copy()
    else:
        missing_values = pd.DataFrame()
    write_csv(missing_values, out_dir / "missing_required_fields.csv")
    summary_records.append({
        "Check": "Records with missing required-field values",
        "Count": int(len(missing_values)),
        "Details": "Rows with at least one missing value in available required fields",
    })

    # Coordinate validity
    coord_invalid = pd.DataFrame()
    if {"Longitude", "Latitude"}.issubset(df.columns):
        coord_invalid = df[
            df["Longitude"].isna()
            | df["Latitude"].isna()
            | (df["Longitude"] < -180)
            | (df["Longitude"] > 180)
            | (df["Latitude"] < -90)
            | (df["Latitude"] > 90)
        ].copy()
    write_csv(coord_invalid, out_dir / "invalid_coordinate_records.csv")
    summary_records.append({
        "Check": "Invalid coordinate records",
        "Count": int(len(coord_invalid)),
        "Details": "Longitude outside [-180, 180], latitude outside [-90, 90], or missing coordinates",
    })

    # Area and perimeter validity
    size_invalid = pd.DataFrame()
    if {"Area", "Perimeter"}.issubset(df.columns):
        size_invalid = df[
            df["Area"].isna()
            | df["Perimeter"].isna()
            | (df["Area"] <= 0)
            | (df["Perimeter"] <= 0)
        ].copy()
    write_csv(size_invalid, out_dir / "nonpositive_area_or_perimeter.csv")
    summary_records.append({
        "Check": "Non-positive or missing Area/Perimeter records",
        "Count": int(len(size_invalid)),
        "Details": "Area <= 0, Perimeter <= 0, or missing values",
    })

    qa_summary = pd.DataFrame(summary_records)
    write_csv(qa_summary, out_dir / "QA_summary.csv")
    return qa_summary


# -----------------------------------------------------------------------------
# Multi-scale aggregation and retrieval
# -----------------------------------------------------------------------------

def summarize_by(df: pd.DataFrame, group_cols: Sequence[str]) -> pd.DataFrame:
    """Summarize oasis count and area statistics by non-country coding units."""
    missing = [c for c in group_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing grouping columns: {missing}")

    if "CountryID" in group_cols:
        raise ValueError(
            "Country-level area aggregation is intentionally disabled. "
            "Exact country-level oasis areas require spatial overlay with national boundaries."
        )

    agg = (
        df.groupby(list(group_cols), dropna=False)
        .agg(
            Oasis_count=("OasisID", "nunique") if "OasisID" in df.columns else ("Area", "size"),
            Total_area_km2=("Area", "sum"),
            Mean_area_km2=("Area", "mean"),
            Median_area_km2=("Area", "median"),
            Max_area_km2=("Area", "max"),
            Total_perimeter_km=("Perimeter", "sum"),
        )
        .reset_index()
    )

    total_area = agg["Total_area_km2"].sum()
    if total_area > 0:
        agg["Area_share_percent"] = agg["Total_area_km2"] / total_area * 100
    else:
        agg["Area_share_percent"] = np.nan

    agg = agg.sort_values("Total_area_km2", ascending=False)
    return agg


def retrieve_oases(
    df: pd.DataFrame,
    continent: Optional[str] = None,
    basin: Optional[str] = None,
    min_area: Optional[float] = None,
    top_n: Optional[int] = None,
) -> pd.DataFrame:
    """Retrieve oasis records according to continent, basin, and area filters."""
    result = df.copy()

    if continent and "ContinentID" in result.columns:
        result = result[result["ContinentID"].astype(str).str.upper() == continent.upper()]

    if basin and "BasinID" in result.columns:
        result = result[result["BasinID"].astype(str) == str(basin)]

    if min_area is not None and "Area" in result.columns:
        result = result[result["Area"] >= float(min_area)]

    if "Area" in result.columns:
        result = result.sort_values("Area", ascending=False)

    if top_n is not None:
        result = result.head(int(top_n))

    return result


def check_areaid_rank(df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """
    Check whether AreaID is consistent with descending Area rank within
    ContinentID-BasinID groups.

    This matches the revised coding definition in which AreaID represents the
    area-based ranking of oasis patches within the same basin. CountryID is not
    used for the ranking check because some patches use composite CountryID codes.
    """
    needed = {"ContinentID", "BasinID", "AreaID", "Area"}
    if not needed.issubset(df.columns):
        out = pd.DataFrame({
            "Message": ["AreaID rank check skipped because required columns are missing."],
            "Required_columns": [", ".join(sorted(needed))],
        })
        write_csv(out, out_dir / "areaid_rank_check.csv")
        return out

    tmp = df.copy()
    tmp = tmp.sort_values(["ContinentID", "BasinID", "Area"], ascending=[True, True, False])
    tmp["Expected_rank"] = tmp.groupby(["ContinentID", "BasinID"], dropna=False).cumcount() + 1

    def parse_areaid(v):
        try:
            return int(str(v).strip())
        except Exception:
            return np.nan

    tmp["AreaID_numeric"] = tmp["AreaID"].apply(parse_areaid)
    tmp["AreaID_matches_area_rank"] = tmp["AreaID_numeric"] == tmp["Expected_rank"]

    mismatches = tmp[~tmp["AreaID_matches_area_rank"]].copy()
    cols = [
        "OasisID", "ContinentID", "CountryID", "BasinID", "AreaID",
        "AreaID_numeric", "Expected_rank", "Area", "Longitude", "Latitude",
    ]
    cols = [c for c in cols if c in mismatches.columns]
    write_csv(mismatches[cols], out_dir / "areaid_rank_check.csv")
    return mismatches[cols]


# -----------------------------------------------------------------------------
# Optional geometry checks
# -----------------------------------------------------------------------------

def list_vector_files(vector_folder: str | Path) -> List[Path]:
    folder = Path(vector_folder)
    if not folder.exists():
        raise FileNotFoundError(f"Vector folder not found: {folder}")

    vector_exts = [".shp", ".gpkg", ".geojson", ".json"]
    files = []
    for ext in vector_exts:
        files.extend(folder.rglob(f"*{ext}"))
    return sorted(files)


def run_geometry_checks(
    vector_folder: str | Path,
    attribute_df: pd.DataFrame,
    out_dir: Path,
    area_tolerance_percent: float = 1.0,
) -> None:
    """Run optional geometry checks if geopandas is installed and vector files are supplied."""
    try:
        import geopandas as gpd
    except ImportError:
        print(
            "geopandas is not installed. Geometry checks were skipped. "
            "Install geopandas to enable vector QA.",
            file=sys.stderr,
        )
        return

    vector_files = list_vector_files(vector_folder)
    if not vector_files:
        print("No vector files found. Geometry checks were skipped.", file=sys.stderr)
        return

    gdfs = []
    for fp in vector_files:
        try:
            gdf = gpd.read_file(fp)
            gdf = clean_column_names(gdf)
            gdf["Source_file"] = str(fp)
            gdfs.append(gdf)
            print(f"Loaded vector file: {fp} ({len(gdf)} features)")
        except Exception as exc:
            print(f"WARNING: Failed to read {fp}: {exc}", file=sys.stderr)

    if not gdfs:
        return

    gdf_all = pd.concat(gdfs, ignore_index=True)
    gdf_all = gpd.GeoDataFrame(gdf_all, geometry="geometry", crs=gdfs[0].crs)

    empty_geom = gdf_all[gdf_all.geometry.is_empty | gdf_all.geometry.isna()].copy()
    invalid_geom = gdf_all[~gdf_all.geometry.is_valid & ~(gdf_all.geometry.is_empty | gdf_all.geometry.isna())].copy()

    geom_summary = pd.DataFrame([
        {"Check": "Vector files loaded", "Count": len(vector_files), "Details": "; ".join(map(str, vector_files))},
        {"Check": "Total vector features", "Count": len(gdf_all), "Details": "All loaded vector features"},
        {"Check": "Empty or missing geometries", "Count": len(empty_geom), "Details": "geometry is empty or null"},
        {"Check": "Invalid geometries", "Count": len(invalid_geom), "Details": "Shapely validity check failed"},
    ])
    write_csv(geom_summary, out_dir / "geometry_QA_summary.csv")

    if "OasisID" in gdf_all.columns:
        dup_geom = gdf_all[gdf_all["OasisID"].duplicated(keep=False) & gdf_all["OasisID"].notna()].copy()
        write_csv(pd.DataFrame(dup_geom.drop(columns="geometry", errors="ignore")), out_dir / "geometry_duplicate_oasisid.csv")

    if "Area" in attribute_df.columns and "OasisID" in attribute_df.columns and "OasisID" in gdf_all.columns:
        try:
            gdf_area = gdf_all[["OasisID", "geometry"]].copy()
            gdf_area = gdf_area.to_crs("EPSG:6933")
            gdf_area["Geometry_area_km2"] = gdf_area.geometry.area / 1e6
            area_df = attribute_df[["OasisID", "Area"]].copy()
            comp = area_df.merge(
                pd.DataFrame(gdf_area[["OasisID", "Geometry_area_km2"]]),
                on="OasisID",
                how="inner",
            )
            comp["Area_difference_km2"] = comp["Geometry_area_km2"] - comp["Area"]
            comp["Area_difference_percent"] = np.where(
                comp["Area"].abs() > 0,
                comp["Area_difference_km2"] / comp["Area"] * 100,
                np.nan,
            )
            comp["Exceeds_tolerance"] = comp["Area_difference_percent"].abs() > area_tolerance_percent
            comp = comp.sort_values("Area_difference_percent", key=lambda x: x.abs(), ascending=False)
            write_csv(comp, out_dir / "geometry_area_comparison.csv")
        except Exception as exc:
            print(f"WARNING: Geometry area comparison failed: {exc}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Main routine
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OasisID-based retrieval, non-country multi-scale statistics, and QA for the global oasis dataset."
    )
    parser.add_argument("--table", required=True, help="Path to Table S1 (.xlsx, .xls, or .csv).")
    parser.add_argument("--out", default="S2_outputs", help="Output directory for CSV files.")
    parser.add_argument("--vector-folder", default=None, help="Optional folder containing split oasis vector files.")
    parser.add_argument("--continent", default=None, help="Optional ContinentID query, e.g., AS, AF, NA, SA, OA.")
    parser.add_argument("--basin", default=None, help="Optional BasinID query.")
    parser.add_argument("--min-area", type=float, default=None, help="Optional minimum oasis area in km2 for query.")
    parser.add_argument("--top-n", type=int, default=20, help="Number of largest oases to export.")
    parser.add_argument(
        "--area-tolerance-percent",
        type=float,
        default=1.0,
        help="Tolerance for geometry-derived area comparison, in percent.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = ensure_output_dir(args.out)

    df = load_attribute_table(args.table)
    print(f"Loaded attribute table with {len(df)} records and {len(df.columns)} columns.")

    qa_summary = make_quality_tables(df, out_dir)
    print("QA summary:")
    print(qa_summary.to_string(index=False))

    if "ContinentID" in df.columns:
        continent_summary = summarize_by(df, ["ContinentID"])
        write_csv(continent_summary, out_dir / "continent_summary.csv")

    if {"ContinentID", "BasinID"}.issubset(df.columns):
        basin_summary = summarize_by(df, ["ContinentID", "BasinID"])
        write_csv(basin_summary, out_dir / "basin_summary.csv")

    top_n = retrieve_oases(df, top_n=args.top_n)
    write_csv(top_n, out_dir / "top_largest_oases.csv")

    query_result = retrieve_oases(
        df,
        continent=args.continent,
        basin=args.basin,
        min_area=args.min_area,
        top_n=args.top_n,
    )
    write_csv(query_result, out_dir / "query_result.csv")

    mismatches = check_areaid_rank(df, out_dir)
    print(f"AreaID rank diagnostic records exported: {len(mismatches)}")

    if args.vector_folder:
        run_geometry_checks(
            args.vector_folder,
            df,
            out_dir,
            area_tolerance_percent=args.area_tolerance_percent,
        )

    print("Country-level area statistics are intentionally not calculated by this script.")
    print("For exact country-level areas, overlay oasis polygons with an authoritative national boundary layer.")
    print(f"All outputs written to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
