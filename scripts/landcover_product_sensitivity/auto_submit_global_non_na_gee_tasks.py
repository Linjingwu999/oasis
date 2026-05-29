from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import ee

import submit_global_non_na_gee_tasks as base


ACTIVE_GEE_STATES = {"READY", "RUNNING"}
SUCCESS_GEE_STATES = {"COMPLETED"}
FAILED_GEE_STATES = {"FAILED", "CANCELLED", "CANCEL_REQUESTED"}

PROGRESS_JSON = base.LOG_DIR / "gee_global_lc_auto_submit_skip_na_progress.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor global non-North-America GEE export tasks and submit the next "
            "batch automatically after the active batch finishes."
        )
    )
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--poll-seconds", type=float, default=600.0)
    parser.add_argument("--submit-sleep-seconds", type=float, default=0.25)
    parser.add_argument(
        "--max-new-batches",
        type=int,
        default=0,
        help="0 means keep submitting until all remaining active tiles have been handled.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def setup_logging() -> Path:
    base.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = base.LOG_DIR / f"gee_global_lc_auto_submit_skip_na_{datetime.now():%Y%m%d_%H%M%S}.log"
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


def task_time_ms(task: dict[str, Any]) -> int:
    return int(task.get("update_timestamp_ms") or task.get("creation_timestamp_ms") or 0)


def get_latest_global_tasks() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for task in ee.data.getTaskList():
        description = str(task.get("description") or "")
        if not description.startswith("LC_GLB_noNA_sub_"):
            continue
        current = latest.get(description)
        if current is None or task_time_ms(task) >= task_time_ms(current):
            latest[description] = task
    return latest


def status_from_gee_state(state: str) -> str:
    if state in SUCCESS_GEE_STATES:
        return "success"
    if state in FAILED_GEE_STATES:
        return "failed"
    if state in ACTIVE_GEE_STATES:
        return "running"
    return "pending"


def description_for_tile_id(tile_id: int) -> str:
    tile_info = base.get_tile_info(tile_id)
    return f"LC_{tile_info['tile_name']}_ESA_DW_2020"


def update_row_from_task(row: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    state = str(task.get("state") or "")
    message = "latest GEE state refreshed"
    if state in SUCCESS_GEE_STATES:
        message = "completed in GEE"
    elif state in FAILED_GEE_STATES:
        message = str(task.get("error_message") or "failed or cancelled in GEE")
    elif state in ACTIVE_GEE_STATES:
        message = "active in GEE"

    row.update(
        {
            "status": status_from_gee_state(state),
            "gee_state": state,
            "task_id": task.get("id", row.get("task_id", "")),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "message": message,
        }
    )
    return row


def refresh_status_rows(active_tile_ids: list[int]) -> dict[int, dict[str, Any]]:
    rows = base.load_status_rows()
    latest_tasks = get_latest_global_tasks()

    for tile_id in active_tile_ids:
        tile_info = base.get_tile_info(tile_id)
        description = f"LC_{tile_info['tile_name']}_ESA_DW_2020"
        row = rows.get(tile_id) or base.make_pending_row(tile_info, description)
        task = latest_tasks.get(description)
        if task:
            row = update_row_from_task(row, task)
        rows[tile_id] = row

    base.write_status_rows(rows)
    return rows


def summarize_rows(rows: dict[int, dict[str, Any]], active_tile_ids: list[int]) -> dict[str, int]:
    summary = {"pending": 0, "running": 0, "success": 0, "failed": 0, "other": 0}
    active_set = set(active_tile_ids)
    for tile_id, row in rows.items():
        if tile_id not in active_set:
            continue
        status = str(row.get("status") or "")
        if status in summary:
            summary[status] += 1
        else:
            summary["other"] += 1
    return summary


def get_active_submitted_tile_ids(rows: dict[int, dict[str, Any]], active_tile_ids: list[int]) -> list[int]:
    active_set = set(active_tile_ids)
    ids: list[int] = []
    for tile_id, row in rows.items():
        if tile_id not in active_set:
            continue
        if row.get("gee_state") in ACTIVE_GEE_STATES or row.get("status") == "running":
            ids.append(tile_id)
    return sorted(ids)


def get_next_unsubmitted_batch(
    rows: dict[int, dict[str, Any]],
    active_tile_ids: list[int],
    batch_size: int,
) -> list[int]:
    terminal_or_active = {"success", "failed", "running"}
    batch: list[int] = []
    for tile_id in active_tile_ids:
        row = rows.get(tile_id)
        if row and row.get("status") in terminal_or_active:
            continue
        batch.append(tile_id)
        if len(batch) >= batch_size:
            break
    return batch


def submit_batch(tile_ids: list[int], args: argparse.Namespace) -> dict[str, int]:
    oasis = ee.FeatureCollection(base.OASIS_ASSET)
    esa_h, dw_collection = base.build_images()
    rows = base.load_status_rows()
    counts = {"submitted": 0, "failed": 0, "dry_run": 0}

    for idx, tile_id in enumerate(tile_ids, start=1):
        logging.info("Submitting next batch tile %s/%s: %s", idx, len(tile_ids), tile_id)
        try:
            row, did_submit = base.submit_tile(
                oasis=oasis,
                esa_h=esa_h,
                dw_collection=dw_collection,
                tile_id=tile_id,
                dry_run=args.dry_run,
            )
            rows[tile_id] = row
            base.write_status_rows(rows)
            if did_submit:
                counts["submitted"] += 1
                logging.info("Submitted %s task_id=%s state=%s", row["description"], row["task_id"], row["gee_state"])
            else:
                counts["dry_run"] += 1
            time.sleep(args.submit_sleep_seconds)
        except Exception as exc:
            counts["failed"] += 1
            tile_info = base.get_tile_info(tile_id)
            description = f"LC_{tile_info['tile_name']}_ESA_DW_2020"
            row = base.make_pending_row(tile_info, description)
            row.update(
                {
                    "status": "failed",
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "message": repr(exc),
                }
            )
            rows[tile_id] = row
            base.write_status_rows(rows)
            logging.exception("Failed to submit tile %s; continuing.", tile_id)
    return counts


def write_progress(
    *,
    log_path: Path,
    active_tile_count: int,
    summary: dict[str, int],
    active_submitted_count: int,
    next_batch: list[int],
    submitted_batches: int,
    done: bool,
) -> None:
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "log_path": str(log_path),
        "status_csv": str(base.STATE_CSV),
        "active_tile_count": active_tile_count,
        "summary": summary,
        "active_submitted_count": active_submitted_count,
        "next_batch_count": len(next_batch),
        "next_batch_tile_ids": next_batch,
        "submitted_batches_this_run": submitted_batches,
        "done": done,
    }
    tmp = PROGRESS_JSON.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(PROGRESS_JSON)


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.poll_seconds <= 0:
        raise ValueError("--poll-seconds must be > 0")

    log_path = setup_logging()
    logging.info("Auto monitor log: %s", log_path)
    logging.info("Status CSV: %s", base.STATE_CSV)
    logging.info("Progress JSON: %s", PROGRESS_JSON)
    logging.info("Project ID: %s", base.PROJECT_ID)
    logging.info("Drive folder: %s", base.DRIVE_FOLDER)
    logging.info("Batch size: %s; poll seconds: %s", args.batch_size, args.poll_seconds)

    ee.Initialize(project=base.PROJECT_ID)
    active_tile_ids = base.expand_active_tile_ids()
    logging.info("Total active non-North-America tiles: %s", len(active_tile_ids))

    submitted_batches = 0
    while True:
        rows = refresh_status_rows(active_tile_ids)
        summary = summarize_rows(rows, active_tile_ids)
        active_submitted = get_active_submitted_tile_ids(rows, active_tile_ids)
        next_batch = get_next_unsubmitted_batch(rows, active_tile_ids, args.batch_size)
        done = not active_submitted and not next_batch

        logging.info(
            "Summary pending=%s running=%s success=%s failed=%s active_submitted=%s next_batch=%s",
            summary["pending"],
            summary["running"],
            summary["success"],
            summary["failed"],
            len(active_submitted),
            len(next_batch),
        )
        write_progress(
            log_path=log_path,
            active_tile_count=len(active_tile_ids),
            summary=summary,
            active_submitted_count=len(active_submitted),
            next_batch=next_batch,
            submitted_batches=submitted_batches,
            done=done,
        )

        if done:
            logging.info("All active tiles are terminal; auto monitor is done.")
            return 0

        if active_submitted:
            logging.info("Current GEE batch still active; sleep %.1f seconds.", args.poll_seconds)
            time.sleep(args.poll_seconds)
            continue

        if args.max_new_batches and submitted_batches >= args.max_new_batches:
            logging.info("Reached max_new_batches=%s; stop without submitting more.", args.max_new_batches)
            return 0

        logging.info("No active submitted tasks; submitting next batch of %s tile(s).", len(next_batch))
        counts = submit_batch(next_batch, args)
        submitted_batches += 1
        logging.info("Batch submitted: %s", counts)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
