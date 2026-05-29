from __future__ import annotations

import csv
import json
import logging
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_DIR = Path(__file__).resolve().parents[2]

GLOBAL_NO_NA_DIR = (
    REPO_DIR
    / "data"
    / "GEE_ESA_DW_landcover_comparison"
    / "GEE_Global_LC_ESA_DW_2020_skip_NA_csv"
)
NORTH_AMERICA_DIR = (
    REPO_DIR
    / "data"
    / "GEE_ESA_DW_landcover_comparison"
    / "GEE_North_America_NA02_csv"
)

OUTPUT_DIR = (
    REPO_DIR
    / "outputs"
    / "GEE_ESA_DW_landcover_comparison"
    / "GEE_Global_LC_ESA_DW_2020_combined_with_NA"
)
LOG_DIR = REPO_DIR / "logs"

EXPECTED_PRODUCTS = {"ESA_WorldCover_2020", "Dynamic_World_2020_mode"}
EXPECTED_CLASS_CODES = set(range(1, 9))
EXPECTED_ROWS_PER_FILE = 16
EXPECTED_GLOBAL_NO_NA_FILE_COUNT = 565
EXPECTED_NA_FILE_COUNT = 140

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

CLASS_ORDER = [
    (1, "Cropland"),
    (2, "Tree_shrub_grass_vegetation"),
    (3, "Wetland_mangrove_flooded_vegetation"),
    (4, "Built_up"),
    (5, "Bare_or_sparse_vegetation"),
    (6, "Water"),
    (7, "Snow_ice"),
    (8, "Other"),
]


def setup_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"merge_global_esa_dw_with_na_{datetime.now():%Y%m%d_%H%M%S}.log"

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


def atomic_write_csv(df: pd.DataFrame, path: Path, **kwargs: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp_path, index=False, encoding="utf-8-sig", **kwargs)
    tmp_path.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def write_status(rows: list[dict[str, object]], path: Path) -> None:
    fieldnames = [
        "source_scope",
        "file_name",
        "file_path",
        "tile_id",
        "tile_name",
        "status",
        "row_count",
        "area_total_km2",
        "message",
    ]
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    tmp_path.replace(path)


def parse_tile_id_from_name(name: str) -> int | None:
    patterns = [
        r"GLB_noNA_sub_(\d+)",
        r"NA_02_sub_(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            return int(match.group(1))
    return None


def input_specs() -> list[dict[str, object]]:
    return [
        {
            "source_scope": "Global_without_North_America",
            "source_label": "GEE_global_skip_NA_565_files",
            "input_dir": GLOBAL_NO_NA_DIR,
            "expected_file_count": EXPECTED_GLOBAL_NO_NA_FILE_COUNT,
        },
        {
            "source_scope": "North_America_existing_NA_02",
            "source_label": "Existing_North_America_NA_02_140_files",
            "input_dir": NORTH_AMERICA_DIR,
            "expected_file_count": EXPECTED_NA_FILE_COUNT,
        },
    ]


def validate_one_csv(path: Path, spec: dict[str, object]) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"missing required columns: {sorted(missing_columns)}")

    tile_id = parse_tile_id_from_name(path.name)
    if tile_id is None:
        if "Tile_id" in df.columns and pd.notna(df["Tile_id"]).any():
            tile_id = int(pd.to_numeric(df["Tile_id"], errors="raise").iloc[0])
        else:
            raise ValueError("cannot parse tile id from file name or Tile_id column")

    df["Area_km2"] = pd.to_numeric(df["Area_km2"], errors="coerce").fillna(0.0)
    df["Class_code"] = pd.to_numeric(df["Class_code"], errors="raise").astype(int)
    df["Product"] = df["Product"].astype(str)
    df["Class_name"] = df["Class_name"].astype(str)
    df["Tile"] = df["Tile"].astype(str)

    products = set(df["Product"].unique())
    class_codes = set(df["Class_code"].unique())
    if products != EXPECTED_PRODUCTS:
        raise ValueError(f"unexpected products: {sorted(products)}")
    if class_codes != EXPECTED_CLASS_CODES:
        raise ValueError(f"unexpected class codes: {sorted(class_codes)}")
    if len(df) != EXPECTED_ROWS_PER_FILE:
        raise ValueError(f"unexpected row count: {len(df)}")
    if (df["Area_km2"] < 0).any():
        raise ValueError("negative Area_km2 values found")

    tile_names = sorted(df["Tile"].dropna().astype(str).unique())
    if len(tile_names) != 1:
        raise ValueError(f"file contains multiple Tile values: {tile_names}")

    df["Input_file"] = path.name
    df["Input_path"] = str(path)
    df["Source_scope"] = str(spec["source_scope"])
    df["Source_label"] = str(spec["source_label"])
    df["Tile_id"] = tile_id

    if "Tile_lon0" not in df.columns:
        df["Tile_lon0"] = pd.NA
    if "Tile_lon1" not in df.columns:
        df["Tile_lon1"] = pd.NA
    if "Tile_lat0" not in df.columns:
        df["Tile_lat0"] = pd.NA
    if "Tile_lat1" not in df.columns:
        df["Tile_lat1"] = pd.NA

    keep_columns = [
        "Source_scope",
        "Source_label",
        "Input_file",
        "Input_path",
        "Region",
        "Region_type",
        "Parent_tile",
        "Tile",
        "Tile_id",
        "Tile_lon0",
        "Tile_lon1",
        "Tile_lat0",
        "Tile_lat1",
        "Product",
        "Class_code",
        "Class_name",
        "Area_km2",
    ]
    return df[keep_columns].copy()


def read_all_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    status_rows: list[dict[str, object]] = []
    frames: list[pd.DataFrame] = []

    for spec in input_specs():
        input_dir = Path(spec["input_dir"])
        expected_file_count = int(spec["expected_file_count"])
        source_scope = str(spec["source_scope"])
        logging.info("Checking input folder: %s", input_dir)

        if not input_dir.exists():
            status_rows.append(
                {
                    "source_scope": source_scope,
                    "file_name": "",
                    "file_path": str(input_dir),
                    "status": "failed",
                    "message": "input folder does not exist",
                }
            )
            continue

        csv_paths = sorted(input_dir.glob("*.csv"))
        logging.info("%s CSV count: %s", source_scope, len(csv_paths))
        if len(csv_paths) != expected_file_count:
            logging.warning(
                "%s expected %s CSV files, found %s",
                source_scope,
                expected_file_count,
                len(csv_paths),
            )

        for index, path in enumerate(csv_paths, start=1):
            try:
                df = validate_one_csv(path, spec)
                frames.append(df)
                status_rows.append(
                    {
                        "source_scope": source_scope,
                        "file_name": path.name,
                        "file_path": str(path),
                        "tile_id": int(df["Tile_id"].iloc[0]),
                        "tile_name": str(df["Tile"].iloc[0]),
                        "status": "success",
                        "row_count": len(df),
                        "area_total_km2": round(float(df["Area_km2"].sum()), 6),
                        "message": "",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logging.exception("Failed to read %s", path)
                status_rows.append(
                    {
                        "source_scope": source_scope,
                        "file_name": path.name,
                        "file_path": str(path),
                        "tile_id": parse_tile_id_from_name(path.name) or "",
                        "tile_name": "",
                        "status": "failed",
                        "row_count": "",
                        "area_total_km2": "",
                        "message": f"{exc}\n{traceback.format_exc()[-2000:]}",
                    }
                )

            if index % 100 == 0:
                logging.info("%s read progress: %s/%s files", source_scope, index, len(csv_paths))

    status = pd.DataFrame(status_rows)
    if not frames:
        raise RuntimeError("No valid CSV files were read; cannot continue")

    merged = pd.concat(frames, ignore_index=True)
    return merged, status


def make_class_template() -> pd.DataFrame:
    return pd.DataFrame(CLASS_ORDER, columns=["Class_code", "Class_name"])


def add_percent(summary: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    totals = (
        summary.groupby(group_columns, as_index=False)["Area_km2"]
        .sum()
        .rename(columns={"Area_km2": "Product_total_area_km2"})
    )
    out = summary.merge(totals, on=group_columns, how="left")
    out["Percent"] = out["Area_km2"] / out["Product_total_area_km2"] * 100
    out["Percent"] = out["Percent"].fillna(0.0)
    return out


def complete_class_rows(summary: pd.DataFrame, scope_values: list[str]) -> pd.DataFrame:
    template = make_class_template()
    products = sorted(EXPECTED_PRODUCTS)
    rows: list[pd.DataFrame] = []
    for scope in scope_values:
        for product in products:
            base = template.copy()
            base["Summary_scope"] = scope
            base["Product"] = product
            rows.append(base)
    full = pd.concat(rows, ignore_index=True)
    out = full.merge(
        summary,
        on=["Summary_scope", "Product", "Class_code", "Class_name"],
        how="left",
    )
    out["Area_km2"] = out["Area_km2"].fillna(0.0)
    return out


def make_summaries(merged: pd.DataFrame) -> dict[str, pd.DataFrame]:
    source_summary = (
        merged.groupby(
            ["Source_scope", "Product", "Class_code", "Class_name"],
            as_index=False,
        )["Area_km2"]
        .sum()
        .rename(columns={"Source_scope": "Summary_scope"})
    )

    combined_summary = (
        merged.groupby(["Product", "Class_code", "Class_name"], as_index=False)["Area_km2"]
        .sum()
    )
    combined_summary["Summary_scope"] = "Global_combined_current_inputs"

    class_summary = pd.concat([source_summary, combined_summary], ignore_index=True)
    class_summary = complete_class_rows(
        class_summary,
        [
            "Global_without_North_America",
            "North_America_existing_NA_02",
            "Global_combined_current_inputs",
        ],
    )
    class_summary = add_percent(class_summary, ["Summary_scope", "Product"])
    class_summary = class_summary[
        [
            "Summary_scope",
            "Product",
            "Class_code",
            "Class_name",
            "Area_km2",
            "Product_total_area_km2",
            "Percent",
        ]
    ].sort_values(["Summary_scope", "Product", "Class_code"])

    class_summary[["Area_km2", "Product_total_area_km2", "Percent"]] = class_summary[
        ["Area_km2", "Product_total_area_km2", "Percent"]
    ].round(6)

    wide_rows: list[pd.DataFrame] = []
    for scope, scope_df in class_summary.groupby("Summary_scope", sort=False):
        area = scope_df.pivot_table(
            index=["Class_code", "Class_name"],
            columns="Product",
            values="Area_km2",
            fill_value=0.0,
        ).reset_index()
        percent = scope_df.pivot_table(
            index=["Class_code", "Class_name"],
            columns="Product",
            values="Percent",
            fill_value=0.0,
        ).reset_index()
        area = area.rename(
            columns={
                "ESA_WorldCover_2020": "ESA_Area_km2",
                "Dynamic_World_2020_mode": "DW_Area_km2",
            }
        )
        percent = percent.rename(
            columns={
                "ESA_WorldCover_2020": "ESA_Percent",
                "Dynamic_World_2020_mode": "DW_Percent",
            }
        )
        wide = area.merge(percent, on=["Class_code", "Class_name"], how="left")
        wide.insert(0, "Summary_scope", scope)
        wide["Area_diff_DW_minus_ESA_km2"] = wide["DW_Area_km2"] - wide["ESA_Area_km2"]
        wide["Percent_point_diff_DW_minus_ESA"] = wide["DW_Percent"] - wide["ESA_Percent"]
        wide_rows.append(wide)

    summary_wide = pd.concat(wide_rows, ignore_index=True)
    numeric_cols = [
        "ESA_Area_km2",
        "DW_Area_km2",
        "ESA_Percent",
        "DW_Percent",
        "Area_diff_DW_minus_ESA_km2",
        "Percent_point_diff_DW_minus_ESA",
    ]
    summary_wide[numeric_cols] = summary_wide[numeric_cols].round(6)

    product_totals = (
        class_summary.groupby(["Summary_scope", "Product"], as_index=False)["Area_km2"]
        .sum()
        .rename(columns={"Area_km2": "Total_area_km2"})
    )
    product_totals["Total_area_km2"] = product_totals["Total_area_km2"].round(6)

    product_total_wide = product_totals.pivot_table(
        index="Summary_scope",
        columns="Product",
        values="Total_area_km2",
        fill_value=0.0,
    ).reset_index()
    product_total_wide = product_total_wide.rename(
        columns={
            "ESA_WorldCover_2020": "ESA_total_area_km2",
            "Dynamic_World_2020_mode": "DW_total_area_km2",
        }
    )
    product_total_wide["Total_diff_DW_minus_ESA_km2"] = (
        product_total_wide["DW_total_area_km2"] - product_total_wide["ESA_total_area_km2"]
    ).round(6)

    tile_totals = (
        merged.groupby(["Source_scope", "Tile_id", "Tile", "Product"], as_index=False)["Area_km2"]
        .sum()
        .sort_values(["Source_scope", "Tile_id", "Product"])
    )
    tile_totals_wide = tile_totals.pivot_table(
        index=["Source_scope", "Tile_id", "Tile"],
        columns="Product",
        values="Area_km2",
        fill_value=0.0,
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

    return {
        "summary_by_scope_product_class": class_summary,
        "summary_by_scope_wide": summary_wide,
        "summary_combined_wide": summary_wide[
            summary_wide["Summary_scope"] == "Global_combined_current_inputs"
        ].copy(),
        "product_total_check": product_total_wide,
        "tile_totals": tile_totals_wide,
    }


def make_quality_report(
    merged: pd.DataFrame,
    status: pd.DataFrame,
    summaries: dict[str, pd.DataFrame],
    log_path: Path,
) -> str:
    success_status = status[status["status"] == "success"].copy()
    failed_status = status[status["status"] != "success"].copy()

    file_counts = success_status.groupby("source_scope")["file_name"].count().to_dict()
    row_counts = merged.groupby("Source_scope").size().to_dict()
    tile_counts = merged.groupby("Source_scope")["Tile"].nunique().to_dict()

    product_total_check = summaries["product_total_check"]
    tile_totals = summaries["tile_totals"]
    combined_wide = summaries["summary_combined_wide"].sort_values(
        "ESA_Area_km2", ascending=False
    )

    lines: list[str] = []
    lines.append("GEE global ESA/Dynamic World 2020 oasis land-cover statistics")
    lines.append(f"Generated at: {datetime.now():%Y-%m-%d %H:%M:%S}")
    lines.append(f"Log file: {log_path}")
    lines.append("")
    lines.append("Input folders")
    lines.append(f"- Global without North America CSVs: {GLOBAL_NO_NA_DIR}")
    lines.append(f"- Existing North America CSVs: {NORTH_AMERICA_DIR}")
    lines.append("")
    lines.append("Completeness check")
    lines.append(f"- Expected global non-NA CSV files: {EXPECTED_GLOBAL_NO_NA_FILE_COUNT}")
    lines.append(f"- Expected North America CSV files: {EXPECTED_NA_FILE_COUNT}")
    lines.append(f"- Successfully read CSV files: {len(success_status)}")
    lines.append(f"- Failed CSV files: {len(failed_status)}")
    for scope in ["Global_without_North_America", "North_America_existing_NA_02"]:
        lines.append(
            f"  - {scope}: files={file_counts.get(scope, 0)}, "
            f"tiles={tile_counts.get(scope, 0)}, rows={row_counts.get(scope, 0)}"
        )
    lines.append(f"- Merged rows: {len(merged)}")
    lines.append("")

    duplicate_keys = (
        merged[["Source_scope", "Tile", "Product", "Class_code"]]
        .value_counts()
        .reset_index(name="count")
    )
    duplicate_keys = duplicate_keys[duplicate_keys["count"] > 1]
    lines.append("Duplicate logical row check")
    lines.append(f"- Duplicate Source_scope + Tile + Product + Class_code rows: {len(duplicate_keys)}")
    lines.append("")

    lines.append("Product total area check")
    for _, row in product_total_check.iterrows():
        lines.append(
            f"- {row['Summary_scope']}: ESA={row['ESA_total_area_km2']:.6f} km2, "
            f"DW={row['DW_total_area_km2']:.6f} km2, "
            f"DW-ESA={row['Total_diff_DW_minus_ESA_km2']:.6f} km2"
        )
    lines.append("")

    lines.append("Tile area check")
    for scope, scope_df in tile_totals.groupby("Source_scope"):
        lines.append(
            f"- {scope}: tiles with oasis area={int(scope_df['Has_oasis_area'].sum())}, "
            f"zero-area tiles={int((~scope_df['Has_oasis_area']).sum())}"
        )
    lines.append("")

    lines.append("Combined global class summary sorted by ESA area")
    for _, row in combined_wide.iterrows():
        lines.append(
            f"- {int(row['Class_code'])}. {row['Class_name']}: "
            f"ESA {row['ESA_Area_km2']:.2f} km2 ({row['ESA_Percent']:.2f}%), "
            f"DW {row['DW_Area_km2']:.2f} km2 ({row['DW_Percent']:.2f}%), "
            f"diff {row['Area_diff_DW_minus_ESA_km2']:.2f} km2"
        )

    if len(failed_status):
        lines.append("")
        lines.append("Failed files")
        for _, row in failed_status.iterrows():
            lines.append(f"- {row.get('file_path')}: {row.get('message')}")

    return "\n".join(lines) + "\n"


def write_excel_outputs(
    merged: pd.DataFrame,
    status: pd.DataFrame,
    summaries: dict[str, pd.DataFrame],
    path: Path,
) -> None:
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            summaries["summary_combined_wide"].to_excel(
                writer, sheet_name="combined_wide", index=False
            )
            summaries["summary_by_scope_wide"].to_excel(
                writer, sheet_name="scope_wide", index=False
            )
            summaries["summary_by_scope_product_class"].to_excel(
                writer, sheet_name="scope_class_long", index=False
            )
            summaries["product_total_check"].to_excel(
                writer, sheet_name="product_total_check", index=False
            )
            summaries["tile_totals"].to_excel(writer, sheet_name="tile_totals", index=False)
            status.to_excel(writer, sheet_name="input_file_status", index=False)
            merged.to_excel(writer, sheet_name="merged_rows", index=False)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Excel output failed: %s", exc)
        atomic_write_text(
            path.with_suffix(".excel_failed.txt"),
            f"Excel output failed at {datetime.now():%Y-%m-%d %H:%M:%S}\n{exc}\n"
            f"{traceback.format_exc()}",
        )


def main() -> int:
    log_path = setup_logging()
    logging.info("Starting global ESA/DW merge analysis")
    logging.info("Output folder: %s", OUTPUT_DIR)

    merged, status = read_all_inputs()
    logging.info("Valid merged rows: %s", len(merged))

    status_path = OUTPUT_DIR / "input_file_status.csv"
    write_status(status.to_dict("records"), status_path)

    summaries = make_summaries(merged)

    merged_path = OUTPUT_DIR / "global_with_existing_NA_tile_class_area.csv"
    summary_long_path = OUTPUT_DIR / "global_with_existing_NA_summary_by_scope_product_class.csv"
    summary_scope_wide_path = OUTPUT_DIR / "global_with_existing_NA_summary_by_scope_wide.csv"
    summary_combined_wide_path = OUTPUT_DIR / "global_with_existing_NA_summary_combined_wide.csv"
    product_total_check_path = OUTPUT_DIR / "global_with_existing_NA_product_total_check.csv"
    tile_totals_path = OUTPUT_DIR / "global_with_existing_NA_tile_totals.csv"
    report_path = OUTPUT_DIR / "global_with_existing_NA_quality_report.txt"
    summary_json_path = OUTPUT_DIR / "global_with_existing_NA_run_summary.json"
    excel_path = OUTPUT_DIR / "global_with_existing_NA_ESA_DW_2020_analysis.xlsx"

    atomic_write_csv(merged, merged_path)
    atomic_write_csv(summaries["summary_by_scope_product_class"], summary_long_path)
    atomic_write_csv(summaries["summary_by_scope_wide"], summary_scope_wide_path)
    atomic_write_csv(summaries["summary_combined_wide"], summary_combined_wide_path)
    atomic_write_csv(summaries["product_total_check"], product_total_check_path)
    atomic_write_csv(summaries["tile_totals"], tile_totals_path)

    report = make_quality_report(merged, status, summaries, log_path)
    atomic_write_text(report_path, report)
    write_excel_outputs(merged, status, summaries, excel_path)

    failed_count = int((status["status"] != "success").sum())
    run_summary = {
        "status": "success" if failed_count == 0 else "completed_with_failed_files",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_global_without_na_dir": str(GLOBAL_NO_NA_DIR),
        "input_north_america_dir": str(NORTH_AMERICA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "expected_global_without_na_files": EXPECTED_GLOBAL_NO_NA_FILE_COUNT,
        "expected_north_america_files": EXPECTED_NA_FILE_COUNT,
        "successful_file_count": int((status["status"] == "success").sum()),
        "failed_file_count": failed_count,
        "merged_row_count": int(len(merged)),
        "outputs": {
            "status_csv": str(status_path),
            "merged_csv": str(merged_path),
            "summary_long_csv": str(summary_long_path),
            "summary_scope_wide_csv": str(summary_scope_wide_path),
            "summary_combined_wide_csv": str(summary_combined_wide_path),
            "product_total_check_csv": str(product_total_check_path),
            "tile_totals_csv": str(tile_totals_path),
            "quality_report": str(report_path),
            "excel": str(excel_path),
            "log": str(log_path),
        },
    }
    atomic_write_json(summary_json_path, run_summary)

    logging.info("Finished. Status: %s", run_summary["status"])
    logging.info("Quality report: %s", report_path)
    print(report)
    return 0 if failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
