#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified command-line entry point for ESA/Dynamic World oasis land-cover comparison."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parents[1]

STEPS = {
    "pilot-na": SCRIPT_DIR / "pilot_north_america_na02_analysis.py",
    "submit-global": SCRIPT_DIR / "submit_global_non_na_gee_tasks.py",
    "auto-submit-global": SCRIPT_DIR / "auto_submit_global_non_na_gee_tasks.py",
    "download": SCRIPT_DIR / "download_gee_results_rclone.py",
    "merge": SCRIPT_DIR / "merge_global_non_na_with_north_america.py",
}

DATA_DIR = REPO_DIR / "data" / "GEE_ESA_DW_landcover_comparison"
GLOBAL_NO_NA_CSV_DIR = DATA_DIR / "GEE_Global_LC_ESA_DW_2020_skip_NA_csv"
NA_CSV_DIR = DATA_DIR / "GEE_North_America_NA02_csv"
COMBINED_OUTPUT_DIR = REPO_DIR / "outputs" / "GEE_ESA_DW_landcover_comparison" / "GEE_Global_LC_ESA_DW_2020_combined_with_NA"
LOG_DIR = REPO_DIR / "logs"


def count_csv(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.csv")))


def print_status() -> None:
    summary_path = COMBINED_OUTPUT_DIR / "global_with_existing_NA_run_summary.json"
    report_path = COMBINED_OUTPUT_DIR / "global_with_existing_NA_quality_report.txt"
    status = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "repo_dir": str(REPO_DIR),
        "global_non_na_csv_count": count_csv(GLOBAL_NO_NA_CSV_DIR),
        "north_america_csv_count": count_csv(NA_CSV_DIR),
        "combined_output_dir_exists": COMBINED_OUTPUT_DIR.exists(),
        "combined_summary_json": str(summary_path) if summary_path.exists() else "",
        "combined_quality_report": str(report_path) if report_path.exists() else "",
    }
    if summary_path.exists():
        try:
            status["combined_summary"] = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            status["combined_summary_read_error"] = repr(exc)
    print(json.dumps(status, ensure_ascii=False, indent=2))


def print_workflow() -> None:
    print(
        "\n".join(
            [
                "Recommended workflow for the ESA/Dynamic World product-sensitivity analysis:",
                "1. pilot-na: analyze North America NA_02 as the pilot/test case.",
                "2. submit-global: submit selected global non-North-America GEE batches.",
                "3. auto-submit-global: optional unattended batch monitor/submission utility.",
                "4. download: optional local utility to retrieve exported CSVs from Google Drive.",
                "5. merge: merge global non-NA CSVs and existing North America CSVs, then recalculate percentages.",
                "",
                "Do not publish rclone.conf, Google tokens, or other local authorization files.",
            ]
        )
    )


def run_step(step: str, extra_args: list[str]) -> int:
    script = STEPS[step]
    if not script.exists():
        print(f"Missing script for step {step}: {script}", file=sys.stderr)
        return 1

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"gee_esa_dw_{step}_{datetime.now():%Y%m%d_%H%M%S}.log"
    cmd = [sys.executable, str(script), *extra_args]
    print(f"Running step: {step}")
    print(f"Script: {script}")
    print(f"Log: {log_path}")

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Command: {' '.join(cmd)}\n")
        log.write(f"Started at: {datetime.now().isoformat(timespec='seconds')}\n\n")
        proc = subprocess.Popen(
            cmd,
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log.write(line)
        code = proc.wait()
        log.write(f"\nFinished at: {datetime.now().isoformat(timespec='seconds')}\n")
        log.write(f"Exit code: {code}\n")
    return code


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Unified entry point for GEE ESA/Dynamic World oasis land-cover comparison."
    )
    parser.add_argument(
        "--step",
        choices=[*STEPS.keys(), "status", "workflow"],
        default="status",
        help="Workflow step to run. Extra arguments after -- are passed to the selected script.",
    )
    return parser.parse_known_args()


def main() -> int:
    args, extra_args = parse_args()
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    if args.step == "status":
        print_status()
        return 0
    if args.step == "workflow":
        print_workflow()
        return 0
    return run_step(args.step, extra_args)


if __name__ == "__main__":
    raise SystemExit(main())
