#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pilot analysis for North America NA_02 ESA/Dynamic World oasis land-cover statistics.

This script reads a ZIP file containing GEE-exported CSV files for the NA_02 pilot
region, validates the exported tables, aggregates area by product and harmonized
land-cover class, and writes quality-control tables. It does not require GEE access.
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_DIR / "outputs" / "GEE_ESA_DW_landcover_comparison" / "north_america_na02_pilot"

EXPECTED_TILE_COUNT = 140
EXPECTED_TILE_IDS = set(range(1, EXPECTED_TILE_COUNT + 1))
EXPECTED_PRODUCTS = {"ESA_WorldCover_2020", "Dynamic_World_2020_mode"}
EXPECTED_CLASS_CODES = set(range(1, 9))

REQUIRED_COLUMNS = {
    "Area_km2",
    "Class_code",
    "Class_name",
    "Parent_tile",
    "Product",
    "Region",
    "Region_type",
    "Tile",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze North America NA_02 pilot CSV exports from ESA/Dynamic World GEE statistics."
    )
    parser.add_argument("--zip", dest="zip_path", required=True, help="ZIP file containing GEE-exported CSVs.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--expected-tile-count", type=int, default=EXPECTED_TILE_COUNT)
    return parser.parse_args()


def setup_logging(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"analysis_log_{datetime.now():%Y%m%d_%H%M%S}.txt"
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )
    return log_path


def atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
    tmp_path.replace(path)


def parse_tile_id(name: str) -> int | None:
    match = re.search(r"NA_02_sub_(\d+)", name)
    if not match:
        return None
    return int(match.group(1))


def write_status(status_rows: list[dict[str, object]], path: Path) -> None:
    fieldnames = ["file_name", "tile_id", "status", "row_count", "message"]
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in status_rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    tmp_path.replace(path)


def extract_zip(zip_path: Path, extract_dir: Path) -> list[str]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        for name in names:
            zf.extract(name, extract_dir)
    return names


def read_and_validate_csv(path: Path, file_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing required columns: {sorted(missing_columns)}")

    tile_id = parse_tile_id(file_name)
    if tile_id is None:
        raise ValueError("cannot parse tile id from file name")

    df["FileName"] = file_name
    df["Tile_id"] = tile_id
    df["Area_km2"] = pd.to_numeric(df["Area_km2"], errors="coerce").fillna(0.0)
    df["Class_code"] = pd.to_numeric(df["Class_code"], errors="raise").astype(int)

    products = set(df["Product"].astype(str).unique())
    class_codes = set(df["Class_code"].unique())
    if products != EXPECTED_PRODUCTS:
        raise ValueError(f"unexpected products: {sorted(products)}")
    if class_codes != EXPECTED_CLASS_CODES:
        raise ValueError(f"unexpected class codes: {sorted(class_codes)}")
    if len(df) != 16:
        raise ValueError(f"unexpected row count: {len(df)}")
    if (df["Area_km2"] < 0).any():
        raise ValueError("negative Area_km2 values found")
    return df


def make_summary(merged: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = (
        merged.groupby(["Product", "Class_code", "Class_name"], as_index=False)["Area_km2"]
        .sum()
        .sort_values(["Product", "Class_code"])
    )
    totals = summary.groupby("Product", as_index=False)["Area_km2"].sum()
    totals = totals.rename(columns={"Area_km2": "Product_total_area_km2"})
    summary = summary.merge(totals, on="Product", how="left")
    summary["Percent"] = summary["Area_km2"] / summary["Product_total_area_km2"] * 100
    summary[["Area_km2", "Product_total_area_km2", "Percent"]] = summary[
        ["Area_km2", "Product_total_area_km2", "Percent"]
    ].round(6)

    area_wide = summary.pivot_table(
        index=["Class_code", "Class_name"], columns="Product", values="Area_km2", fill_value=0.0
    ).reset_index()
    percent_wide = summary.pivot_table(
        index=["Class_code", "Class_name"], columns="Product", values="Percent", fill_value=0.0
    ).reset_index()

    wide = area_wide.rename(
        columns={
            "ESA_WorldCover_2020": "ESA_Area_km2",
            "Dynamic_World_2020_mode": "DW_Area_km2",
        }
    )
    percent_wide = percent_wide.rename(
        columns={
            "ESA_WorldCover_2020": "ESA_Percent",
            "Dynamic_World_2020_mode": "DW_Percent",
        }
    )
    wide = wide.merge(
        percent_wide[["Class_code", "Class_name", "ESA_Percent", "DW_Percent"]],
        on=["Class_code", "Class_name"],
        how="left",
    )
    wide["Area_diff_DW_minus_ESA_km2"] = wide["DW_Area_km2"] - wide["ESA_Area_km2"]
    wide["Percent_point_diff_DW_minus_ESA"] = wide["DW_Percent"] - wide["ESA_Percent"]
    numeric_cols = [
        "ESA_Area_km2",
        "DW_Area_km2",
        "ESA_Percent",
        "DW_Percent",
        "Area_diff_DW_minus_ESA_km2",
        "Percent_point_diff_DW_minus_ESA",
    ]
    wide[numeric_cols] = wide[numeric_cols].round(6)

    tile_totals = (
        merged.groupby(["Tile_id", "Tile", "Product"], as_index=False)["Area_km2"]
        .sum()
        .sort_values(["Tile_id", "Product"])
    )
    tile_totals_wide = tile_totals.pivot_table(
        index=["Tile_id", "Tile"], columns="Product", values="Area_km2", fill_value=0.0
    ).reset_index()
    tile_totals_wide = tile_totals_wide.rename(
        columns={
            "ESA_WorldCover_2020": "ESA_total_area_km2",
            "Dynamic_World_2020_mode": "DW_total_area_km2",
        }
    )
    tile_totals_wide["Total_diff_DW_minus_ESA_km2"] = (
        tile_totals_wide["DW_total_area_km2"] - tile_totals_wide["ESA_total_area_km2"]
    )
    tile_totals_wide["Has_oasis_area"] = (
        (tile_totals_wide["ESA_total_area_km2"] > 0)
        | (tile_totals_wide["DW_total_area_km2"] > 0)
    )
    for col in ["ESA_total_area_km2", "DW_total_area_km2", "Total_diff_DW_minus_ESA_km2"]:
        tile_totals_wide[col] = tile_totals_wide[col].round(6)
    return summary, wide, tile_totals_wide


def write_report(
    report_path: Path,
    zip_path: Path,
    zip_names: list[str],
    status_rows: list[dict[str, object]],
    merged: pd.DataFrame,
    summary: pd.DataFrame,
    wide: pd.DataFrame,
    tile_totals: pd.DataFrame,
    expected_tile_count: int,
) -> None:
    expected_ids = set(range(1, expected_tile_count + 1))
    tile_ids = [parse_tile_id(name) for name in zip_names]
    parsed_tile_ids = [tile_id for tile_id in tile_ids if tile_id is not None]
    missing_tiles = sorted(expected_ids - set(parsed_tile_ids))
    duplicate_tiles = sorted(tile_id for tile_id in set(parsed_tile_ids) if parsed_tile_ids.count(tile_id) > 1)
    failed = [row for row in status_rows if row["status"] == "failed"]
    success = [row for row in status_rows if row["status"] == "success"]

    totals = summary.groupby("Product")["Area_km2"].sum().to_dict()
    nonzero_tiles = int(tile_totals["Has_oasis_area"].sum())
    zero_tiles = int((~tile_totals["Has_oasis_area"]).sum())

    lines = [
        "GEE North America NA_02 ESA/Dynamic World 2020 area statistics",
        f"Source zip: {zip_path}",
        f"Output folder: {report_path.parent}",
        "",
        "Completeness check",
        f"CSV files in zip: {len(zip_names)}",
        f"Successfully read CSV files: {len(success)}",
        f"Failed CSV files: {len(failed)}",
        f"Parsed tile IDs: {len(parsed_tile_ids)}",
        f"Missing tile IDs: {missing_tiles if missing_tiles else 'none'}",
        f"Duplicate tile IDs: {duplicate_tiles if duplicate_tiles else 'none'}",
        f"Merged rows: {len(merged)}",
        "",
        "Tile area check",
        f"Tiles with oasis area: {nonzero_tiles}",
        f"Zero-area tiles: {zero_tiles}",
        f"ESA total area km2: {totals.get('ESA_WorldCover_2020', 0):.6f}",
        f"Dynamic World total area km2: {totals.get('Dynamic_World_2020_mode', 0):.6f}",
        f"Total difference DW - ESA km2: {totals.get('Dynamic_World_2020_mode', 0) - totals.get('ESA_WorldCover_2020', 0):.6f}",
        "",
        "Class summary sorted by ESA area",
    ]
    esa_rank = wide.sort_values("ESA_Area_km2", ascending=False)
    for _, row in esa_rank.iterrows():
        lines.append(
            f"{int(row['Class_code'])}. {row['Class_name']}: "
            f"ESA {row['ESA_Area_km2']:.2f} km2 ({row['ESA_Percent']:.2f}%), "
            f"DW {row['DW_Area_km2']:.2f} km2 ({row['DW_Percent']:.2f}%), "
            f"diff {row['Area_diff_DW_minus_ESA_km2']:.2f} km2"
        )
    if failed:
        lines.extend(["", "Failed files"])
        for row in failed:
            lines.append(f"{row['file_name']}: {row['message']}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    zip_path = Path(args.zip_path)
    output_dir = Path(args.out)
    setup_logging(output_dir)
    logging.info("Source zip: %s", zip_path)
    logging.info("Output directory: %s", output_dir)
    if not zip_path.exists():
        raise FileNotFoundError(f"Source zip does not exist: {zip_path}")

    extract_dir = output_dir / "extracted_csv"
    status_path = output_dir / "analysis_status.csv"
    zip_names = extract_zip(zip_path, extract_dir)
    logging.info("Extracted %s CSV files to %s", len(zip_names), extract_dir)

    frames: list[pd.DataFrame] = []
    status_rows: list[dict[str, object]] = []
    for index, name in enumerate(sorted(zip_names), start=1):
        csv_path = extract_dir / name
        tile_id = parse_tile_id(name)
        logging.info("[%s/%s] Reading %s", index, len(zip_names), name)
        try:
            df = read_and_validate_csv(csv_path, name)
            frames.append(df)
            status_rows.append({"file_name": name, "tile_id": tile_id or "", "status": "success", "row_count": len(df), "message": ""})
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed to read %s; continuing.", name)
            status_rows.append({"file_name": name, "tile_id": tile_id or "", "status": "failed", "row_count": "", "message": repr(exc)})
        write_status(status_rows, status_path)

    if not frames:
        logging.error("No valid CSV files were read.")
        return 1

    merged = pd.concat(frames, ignore_index=True)
    summary, wide, tile_totals = make_summary(merged)

    merged_path = output_dir / "NA_02_ESA_DW_2020_merged_tile_class_area.csv"
    summary_path = output_dir / "NA_02_ESA_DW_2020_summary_by_product_class.csv"
    wide_path = output_dir / "NA_02_ESA_DW_2020_summary_wide.csv"
    tile_totals_path = output_dir / "NA_02_ESA_DW_2020_tile_totals.csv"
    report_path = output_dir / "NA_02_ESA_DW_2020_quality_report.txt"
    xlsx_path = output_dir / "NA_02_ESA_DW_2020_analysis.xlsx"

    atomic_write_csv(merged, merged_path)
    atomic_write_csv(summary, summary_path)
    atomic_write_csv(wide, wide_path)
    atomic_write_csv(tile_totals, tile_totals_path)
    write_report(report_path, zip_path, zip_names, status_rows, merged, summary, wide, tile_totals, args.expected_tile_count)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary_by_product_class", index=False)
        wide.to_excel(writer, sheet_name="summary_wide", index=False)
        tile_totals.to_excel(writer, sheet_name="tile_totals", index=False)
        merged.to_excel(writer, sheet_name="merged_tile_class_area", index=False)
        pd.DataFrame(status_rows).to_excel(writer, sheet_name="analysis_status", index=False)

    logging.info("Analysis completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
