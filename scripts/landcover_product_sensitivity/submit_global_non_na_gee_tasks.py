from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import ee


PROJECT_ID = "oasis-494813"
OASIS_ASSET = "users/linjingwu08/oasis_global_simplified10m"
DRIVE_FOLDER = "Global_LC_ESA_DW_2020_skip_NA"

REGION_NAME = "Global_without_North_America"
PARENT_TILE_NAME = "Global_2deg_nonempty_skip_NA"

LON_START = -82
LAT_START = -36
LON_STEP = 2
LAT_STEP = 2
LON_COLUMNS = 114

DEFAULT_BATCH_START_INDEX = 0
DEFAULT_BATCH_END_INDEX = 99

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
STATE_CSV = LOG_DIR / "gee_global_lc_exports_skip_na_status.csv"

CLASS_INFO = {
    1: "Cropland",
    2: "Tree_shrub_grass_vegetation",
    3: "Wetland_mangrove_flooded_vegetation",
    4: "Built_up",
    5: "Bare_or_sparse_vegetation",
    6: "Water",
    7: "Snow_ice",
    8: "Other",
}

CLASS_CODES = list(CLASS_INFO)

# Generated from the local oasis_global_simplified10m shapefile on 2026-05-28.
# The source data were filtered with ContinentI != "NA" to skip North America.
ACTIVE_TILE_ROW_COL_RANGES = [
    {"row": 0, "ranges": [[6, 6]]},
    {"row": 1, "ranges": [[6, 7]]},
    {"row": 2, "ranges": [[5, 6], [49, 50], [110, 111]]},
    {"row": 3, "ranges": [[5, 7], [49, 49], [108, 112]]},
    {"row": 4, "ranges": [[5, 8], [48, 48], [108, 113]]},
    {"row": 5, "ranges": [[6, 8], [97, 97], [107, 108], [110, 112]]},
    {"row": 6, "ranges": [[5, 6], [8, 8], [48, 48], [98, 98], [108, 111]]},
    {"row": 7, "ranges": [[6, 7], [47, 48], [98, 100], [109, 110]]},
    {"row": 8, "ranges": [[5, 7], [47, 47], [100, 102]]},
    {"row": 9, "ranges": [[4, 7]]},
    {"row": 10, "ranges": [[2, 4], [46, 47]]},
    {"row": 11, "ranges": [[2, 3], [47, 47]]},
    {"row": 12, "ranges": [[1, 2]]},
    {"row": 13, "ranges": [[1, 1]]},
    {"row": 14, "ranges": [[0, 1]]},
    {"row": 15, "ranges": [[0, 1]]},
    {"row": 17, "ranges": [[60, 61]]},
    {"row": 18, "ranges": [[58, 61]]},
    {"row": 19, "ranges": [[58, 59], [61, 62]]},
    {"row": 20, "ranges": [[61, 63]]},
    {"row": 21, "ranges": [[62, 63]]},
    {"row": 23, "ranges": [[45, 46], [61, 66]]},
    {"row": 24, "ranges": [[37, 38], [41, 42], [45, 48], [57, 58], [62, 65]]},
    {"row": 25, "ranges": [[29, 29], [32, 41], [45, 45], [47, 48], [57, 67]]},
    {"row": 26, "ranges": [[28, 29], [32, 37], [39, 41], [44, 44], [56, 60], [62, 65], [67, 68]]},
    {"row": 27, "ranges": [[32, 36], [44, 44], [46, 47], [56, 60], [63, 63], [67, 69]]},
    {"row": 28, "ranges": [[32, 35], [47, 47], [56, 56], [59, 59], [63, 64], [68, 70]]},
    {"row": 29, "ranges": [[32, 33], [54, 59], [63, 70]]},
    {"row": 30, "ranges": [[33, 33], [35, 35], [45, 48], [51, 52], [55, 58], [62, 75]]},
    {"row": 31, "ranges": [[33, 35], [40, 42], [45, 45], [47, 49], [54, 76]]},
    {"row": 32, "ranges": [[34, 36], [38, 41], [44, 45], [48, 51], [53, 71], [74, 77]]},
    {"row": 33, "ranges": [[36, 40], [42, 78]]},
    {"row": 34, "ranges": [[36, 48], [50, 53], [58, 59], [62, 78]]},
    {"row": 35, "ranges": [[39, 46], [59, 73], [75, 75], [89, 89]]},
    {"row": 36, "ranges": [[45, 46], [59, 90], [92, 94]]},
    {"row": 37, "ranges": [[60, 65], [68, 80], [82, 94]]},
    {"row": 38, "ranges": [[62, 63], [70, 85], [87, 91], [94, 96]]},
    {"row": 39, "ranges": [[70, 72], [74, 88], [91, 91]]},
    {"row": 40, "ranges": [[70, 86], [89, 91]]},
    {"row": 41, "ranges": [[71, 72], [79, 89]]},
    {"row": 42, "ranges": [[83, 84], [86, 88]]},
    {"row": 43, "ranges": [[86, 88]]},
]


def setup_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"gee_global_lc_submit_skip_na_{datetime.now():%Y%m%d_%H%M%S}.log"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit global non-North-America ESA/Dynamic World oasis area exports to GEE."
    )
    parser.add_argument("--batch-start-index", type=int, default=DEFAULT_BATCH_START_INDEX)
    parser.add_argument("--batch-end-index", type=int, default=DEFAULT_BATCH_END_INDEX)
    parser.add_argument(
        "--failed-tile-ids",
        default="",
        help="Comma-separated tile IDs to rerun. Overrides batch indexes.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    return parser.parse_args()


def expand_active_tile_ids() -> list[int]:
    tile_ids: list[int] = []
    for item in ACTIVE_TILE_ROW_COL_RANGES:
        row = int(item["row"])
        for col0, col1 in item["ranges"]:
            for col in range(int(col0), int(col1) + 1):
                tile_ids.append(row * LON_COLUMNS + col + 1)
    return tile_ids


def parse_failed_tile_ids(raw: str) -> list[int]:
    if not raw.strip():
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def get_tile_info(tile_number: int) -> dict[str, Any]:
    row_index = (tile_number - 1) // LON_COLUMNS
    col_index = (tile_number - 1) % LON_COLUMNS

    lon0 = LON_START + col_index * LON_STEP
    lat0 = LAT_START + row_index * LAT_STEP
    lon1 = lon0 + LON_STEP
    lat1 = lat0 + LAT_STEP

    return {
        "tile_number": tile_number,
        "tile_name": f"GLB_noNA_sub_{tile_number}",
        "lon0": lon0,
        "lat0": lat0,
        "lon1": lon1,
        "lat1": lat1,
        "tile_geom": ee.Geometry.Rectangle([lon0, lat0, lon1, lat1], None, False),
    }


def get_existing_tasks_by_description() -> dict[str, dict[str, Any]]:
    tasks = ee.data.getTaskList()
    existing: dict[str, dict[str, Any]] = {}
    for task in tasks:
        description = task.get("description")
        if not description:
            continue
        description = str(description)
        current = existing.get(description)
        task_time = int(task.get("update_timestamp_ms") or task.get("creation_timestamp_ms") or 0)
        current_time = int(
            current.get("update_timestamp_ms") or current.get("creation_timestamp_ms") or 0
        ) if current else -1
        if current is None or task_time >= current_time:
            existing[description] = task
    return existing


def make_zero_features(product_name: str, tile_info: dict[str, Any]) -> ee.FeatureCollection:
    features = []
    for code in CLASS_CODES:
        features.append(
            ee.Feature(
                None,
                {
                    "Region": REGION_NAME,
                    "Region_type": "Global_subtile",
                    "Parent_tile": PARENT_TILE_NAME,
                    "Tile": tile_info["tile_name"],
                    "Tile_id": tile_info["tile_number"],
                    "Tile_lon0": tile_info["lon0"],
                    "Tile_lat0": tile_info["lat0"],
                    "Tile_lon1": tile_info["lon1"],
                    "Tile_lat1": tile_info["lat1"],
                    "Product": product_name,
                    "Class_code": code,
                    "Class_name": CLASS_INFO[code],
                    "Area_km2": 0,
                },
            )
        )
    return ee.FeatureCollection(features)


def calculate_area_by_class(
    oasis: ee.FeatureCollection,
    image: ee.Image,
    product_name: str,
    tile_info: dict[str, Any],
    scale: int,
) -> ee.FeatureCollection:
    tile_geom = tile_info["tile_geom"]
    tile_oasis = oasis.filterBounds(tile_geom)
    has_oasis = tile_oasis.size().gt(0)

    oasis_mask = (
        ee.Image(0)
        .byte()
        .paint(featureCollection=tile_oasis, color=1)
        .clip(tile_geom)
        .selfMask()
    )

    masked_class = image.updateMask(oasis_mask).clip(tile_geom)

    area_image = (
        ee.Image.pixelArea()
        .divide(1e6)
        .rename("area_km2")
        .addBands(masked_class.rename("class"))
    )

    result = area_image.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
        geometry=tile_geom,
        scale=scale,
        maxPixels=1e13,
        tileScale=16,
        bestEffort=True,
    )

    groups = ee.List(
        ee.Algorithms.If(result.contains("groups"), result.get("groups"), ee.List([]))
    )

    group_keys = groups.map(
        lambda g: ee.Number(ee.Dictionary(g).get("class")).format()
    )
    group_values = groups.map(lambda g: ee.Number(ee.Dictionary(g).get("sum")))
    area_dict = ee.Dictionary.fromLists(group_keys, group_values)

    features = []
    for code in CLASS_CODES:
        key = str(code)
        area_km2 = ee.Number(
            ee.Algorithms.If(area_dict.contains(key), area_dict.get(key), 0)
        )
        features.append(
            ee.Feature(
                None,
                {
                    "Region": REGION_NAME,
                    "Region_type": "Global_subtile",
                    "Parent_tile": PARENT_TILE_NAME,
                    "Tile": tile_info["tile_name"],
                    "Tile_id": tile_info["tile_number"],
                    "Tile_lon0": tile_info["lon0"],
                    "Tile_lat0": tile_info["lat0"],
                    "Tile_lon1": tile_info["lon1"],
                    "Tile_lat1": tile_info["lat1"],
                    "Product": product_name,
                    "Class_code": code,
                    "Class_name": CLASS_INFO[code],
                    "Area_km2": area_km2,
                },
            )
        )

    stats_fc = ee.FeatureCollection(features)
    zero_fc = make_zero_features(product_name, tile_info)

    return ee.FeatureCollection(ee.Algorithms.If(has_oasis, stats_fc, zero_fc))


def build_images() -> tuple[ee.Image, ee.ImageCollection]:
    esa_raw = ee.ImageCollection("ESA/WorldCover/v100").first().select("Map")
    esa_h = (
        esa_raw.remap(
            [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
            [2, 2, 2, 1, 4, 5, 7, 6, 3, 3, 8],
        )
        .rename("class")
        .toByte()
    )
    dw_collection = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterDate("2020-01-01", "2021-01-01")
        .select("label")
    )
    return esa_h, dw_collection


def get_dw_harmonized(dw_collection: ee.ImageCollection, tile_geom: ee.Geometry) -> ee.Image:
    dw_tile = dw_collection.filterBounds(tile_geom)
    n = dw_tile.size()
    dw_label = ee.Image(
        ee.Algorithms.If(
            n.gt(0),
            dw_tile.mode().rename("label"),
            ee.Image(0).rename("label").updateMask(ee.Image(0)),
        )
    )
    return (
        dw_label.remap([0, 1, 2, 3, 4, 5, 6, 7, 8], [6, 2, 2, 3, 1, 2, 4, 5, 7])
        .rename("class")
        .toByte()
    )


def load_status_rows() -> dict[int, dict[str, Any]]:
    if not STATE_CSV.exists():
        return {}
    rows: dict[int, dict[str, Any]] = {}
    with STATE_CSV.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[int(row["tile_id"])] = row
    return rows


def write_status_rows(rows: dict[int, dict[str, Any]]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tile_id",
        "tile_name",
        "description",
        "status",
        "gee_state",
        "task_id",
        "lon0",
        "lat0",
        "lon1",
        "lat1",
        "updated_at",
        "message",
    ]
    tmp_path = STATE_CSV.with_suffix(".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for tile_id in sorted(rows):
            writer.writerow({key: rows[tile_id].get(key, "") for key in fieldnames})
    tmp_path.replace(STATE_CSV)


def make_pending_row(tile_info: dict[str, Any], description: str) -> dict[str, Any]:
    return {
        "tile_id": tile_info["tile_number"],
        "tile_name": tile_info["tile_name"],
        "description": description,
        "status": "pending",
        "gee_state": "",
        "task_id": "",
        "lon0": tile_info["lon0"],
        "lat0": tile_info["lat0"],
        "lon1": tile_info["lon1"],
        "lat1": tile_info["lat1"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "message": "",
    }


def submit_tile(
    oasis: ee.FeatureCollection,
    esa_h: ee.Image,
    dw_collection: ee.ImageCollection,
    tile_id: int,
    dry_run: bool,
) -> tuple[dict[str, Any], bool]:
    tile_info = get_tile_info(tile_id)
    description = f"LC_{tile_info['tile_name']}_ESA_DW_2020"
    row = make_pending_row(tile_info, description)

    if dry_run:
        row.update(
            {
                "status": "pending",
                "message": "dry run only; task was not submitted",
            }
        )
        return row, False

    esa_stats = calculate_area_by_class(
        oasis=oasis,
        image=esa_h,
        product_name="ESA_WorldCover_2020",
        tile_info=tile_info,
        scale=10,
    )
    dw_h = get_dw_harmonized(dw_collection, tile_info["tile_geom"])
    dw_stats = calculate_area_by_class(
        oasis=oasis,
        image=dw_h,
        product_name="Dynamic_World_2020_mode",
        tile_info=tile_info,
        scale=10,
    )
    tile_stats = esa_stats.merge(dw_stats)

    task = ee.batch.Export.table.toDrive(
        collection=tile_stats,
        description=description,
        folder=DRIVE_FOLDER,
        fileNamePrefix=description,
        fileFormat="CSV",
    )
    task.start()
    row.update(
        {
            "status": "running",
            "gee_state": task.status().get("state", ""),
            "task_id": task.id,
            "message": "submitted",
        }
    )
    return row, True


def main() -> int:
    args = parse_args()
    log_path = setup_logging()

    logging.info("Log file: %s", log_path)
    logging.info("Status CSV: %s", STATE_CSV)
    logging.info("Project ID: %s", PROJECT_ID)
    logging.info("Oasis asset: %s", OASIS_ASSET)
    logging.info("Drive folder: %s", DRIVE_FOLDER)

    ee.Initialize(project=PROJECT_ID)
    oasis = ee.FeatureCollection(OASIS_ASSET)
    logging.info("Global oasis feature count: %s", oasis.size().getInfo())

    active_tile_ids = expand_active_tile_ids()
    failed_tile_ids = parse_failed_tile_ids(args.failed_tile_ids)
    if failed_tile_ids:
        selected_tile_ids = failed_tile_ids
        logging.info("Rerun failed tile IDs: %s", selected_tile_ids)
    else:
        selected_tile_ids = active_tile_ids[
            args.batch_start_index : args.batch_end_index + 1
        ]
        logging.info(
            "Selected batch indexes %s-%s from %s active tiles.",
            args.batch_start_index,
            args.batch_end_index,
            len(active_tile_ids),
        )

    if not selected_tile_ids:
        logging.warning("No tile IDs selected.")
        return 0

    logging.info("Selected tile count: %s", len(selected_tile_ids))
    logging.info("Selected tile IDs: %s", json.dumps(selected_tile_ids))

    existing_tasks = get_existing_tasks_by_description()
    status_rows = load_status_rows()
    esa_h, dw_collection = build_images()

    submitted = 0
    skipped = 0
    failed = 0

    for index, tile_id in enumerate(selected_tile_ids, start=1):
        tile_info = get_tile_info(tile_id)
        description = f"LC_{tile_info['tile_name']}_ESA_DW_2020"
        logging.info("[%s/%s] Tile %s %s", index, len(selected_tile_ids), tile_id, description)

        existing = existing_tasks.get(description)
        if existing and existing.get("state") in {"READY", "RUNNING", "COMPLETED"}:
            row = make_pending_row(tile_info, description)
            row.update(
                {
                    "status": "success" if existing.get("state") == "COMPLETED" else "running",
                    "gee_state": existing.get("state", ""),
                    "task_id": existing.get("id", ""),
                    "message": "existing task found; skipped duplicate submission",
                }
            )
            status_rows[tile_id] = row
            write_status_rows(status_rows)
            skipped += 1
            logging.info("Skipped existing task: %s state=%s", description, existing.get("state"))
            continue

        try:
            row, did_submit = submit_tile(
                oasis=oasis,
                esa_h=esa_h,
                dw_collection=dw_collection,
                tile_id=tile_id,
                dry_run=args.dry_run,
            )
            status_rows[tile_id] = row
            write_status_rows(status_rows)
            if did_submit:
                submitted += 1
                logging.info(
                    "Submitted task_id=%s state=%s",
                    row.get("task_id"),
                    row.get("gee_state"),
                )
            else:
                logging.info("Dry-run pending tile %s", tile_id)
            time.sleep(args.sleep_seconds)
        except Exception as exc:
            failed += 1
            row = make_pending_row(tile_info, description)
            row.update(
                {
                    "status": "failed",
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "message": repr(exc),
                }
            )
            status_rows[tile_id] = row
            write_status_rows(status_rows)
            logging.exception("Failed to submit tile %s; continuing.", tile_id)

    logging.info(
        "Done. submitted=%s skipped=%s failed=%s selected=%s",
        submitted,
        skipped,
        failed,
        len(selected_tile_ids),
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
