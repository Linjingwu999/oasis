#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download GEE-exported CSV files from Google Drive using rclone.

This is a local helper script. Do not commit rclone.conf, Google OAuth tokens,
or any local authorization file to a public repository.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_DIR = Path(__file__).resolve().parents[2]
REMOTE_NAME = "gdrive"
REMOTE_FOLDER = "Global_LC_ESA_DW_2020_skip_NA"

DOWNLOAD_DIR_DEFAULT = REPO_DIR / "data" / "GEE_ESA_DW_landcover_comparison" / "GEE_Global_LC_ESA_DW_2020_skip_NA_csv"
RESULT_DIR_DEFAULT = REPO_DIR / "outputs" / "GEE_ESA_DW_landcover_comparison" / "GEE_Global_LC_ESA_DW_2020_skip_NA_download"
LOG_DIR_DEFAULT = REPO_DIR / "logs"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "download_gee_global_esa_dw_rclone.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return log_path


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if not rows:
        tmp.write_text("", encoding="utf-8-sig")
    else:
        with tmp.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    tmp.replace(path)


def resolve_rclone_exe(raw: str) -> str:
    if Path(raw).exists():
        return str(Path(raw))
    found = shutil.which(raw)
    if found:
        return found
    raise FileNotFoundError(f"rclone executable not found: {raw}. Install rclone or pass --rclone-exe.")


def find_rclone_config(explicit_config: str | None) -> Path:
    candidates = []
    if explicit_config:
        candidates.append(Path(explicit_config))
    if os.environ.get("RCLONE_CONFIG"):
        candidates.append(Path(os.environ["RCLONE_CONFIG"]))
    candidates.extend([
        REPO_DIR / "local" / "rclone.conf",
        Path.home() / ".config" / "rclone" / "rclone.conf",
        Path.home() / "AppData" / "Roaming" / "rclone" / "rclone.conf",
    ])
    for path in candidates:
        if path.exists():
            return path
    checked = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        "No rclone config found. Keep authorization files local and do not include them in GitHub. Checked:\n"
        + checked
    )


def run_rclone(rclone_exe: str, rclone_config: Path, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    cmd = [rclone_exe, "--config", str(rclone_config), *args]
    logging.info("Running rclone command: %s ...", " ".join(cmd[:5]))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.stdout.strip():
        logging.info("rclone stdout:\n%s", result.stdout.strip())
    if result.stderr.strip():
        logging.info("rclone stderr:\n%s", result.stderr.strip())
    return result


def list_remote_files(rclone_exe: str, rclone_config: Path, remote_path: str, result_dir: Path) -> list[dict[str, Any]]:
    result = run_rclone(rclone_exe, rclone_config, ["lsjson", remote_path, "--files-only", "--include", "*.csv"], timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"rclone lsjson failed: {result.stderr}")
    rows = json.loads(result.stdout)
    manifest: list[dict[str, Any]] = []
    for row in rows:
        manifest.append({
            "name": row.get("Name", ""),
            "path": row.get("Path", ""),
            "size": int(row.get("Size") or 0),
            "mod_time": row.get("ModTime", ""),
            "mime_type": row.get("MimeType", ""),
        })
    manifest.sort(key=lambda x: x["name"])
    write_csv(result_dir / "remote_file_manifest.csv", manifest)
    return manifest


def local_manifest(download_dir: Path, result_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(download_dir.glob("*.csv")):
        rows.append({
            "name": path.name,
            "size": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "local_path": str(path),
        })
    write_csv(result_dir / "local_file_manifest.csv", rows)
    return rows


def copy_remote(rclone_exe: str, rclone_config: Path, remote_path: str, download_dir: Path, log_path: Path) -> None:
    result = run_rclone(
        rclone_exe,
        rclone_config,
        [
            "copy", remote_path, str(download_dir), "--include", "*.csv",
            "--transfers", "8", "--checkers", "16", "--ignore-existing",
            "--retries", "5", "--low-level-retries", "10", "--stats", "30s",
            "--log-file", str(log_path), "--log-level", "INFO",
        ],
        timeout=3600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"rclone copy failed: {result.stderr}")


def validate(remote: list[dict[str, Any]], local: list[dict[str, Any]]) -> dict[str, Any]:
    remote_by_name = {row["name"]: row for row in remote}
    local_by_name = {row["name"]: row for row in local}
    missing = sorted(set(remote_by_name) - set(local_by_name))
    extra = sorted(set(local_by_name) - set(remote_by_name))
    size_mismatch = []
    for name in sorted(set(remote_by_name) & set(local_by_name)):
        if int(remote_by_name[name]["size"]) != int(local_by_name[name]["size"]):
            size_mismatch.append({
                "name": name,
                "remote_size": int(remote_by_name[name]["size"]),
                "local_size": int(local_by_name[name]["size"]),
            })
    return {
        "remote_count": len(remote),
        "local_count": len(local),
        "remote_total_bytes": sum(int(row["size"]) for row in remote),
        "local_total_bytes": sum(int(row["size"]) for row in local),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "size_mismatch_count": len(size_mismatch),
        "missing_files": missing[:50],
        "extra_files": extra[:50],
        "size_mismatches": size_mismatch[:50],
        "complete": len(missing) == 0 and len(size_mismatch) == 0 and len(remote) > 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download GEE-exported ESA/Dynamic World CSV files with rclone.")
    parser.add_argument("--remote-name", default=REMOTE_NAME)
    parser.add_argument("--remote-folder", default=REMOTE_FOLDER)
    parser.add_argument("--rclone-exe", default="rclone")
    parser.add_argument("--rclone-config", default=None)
    parser.add_argument("--download-dir", default=str(DOWNLOAD_DIR_DEFAULT))
    parser.add_argument("--result-dir", default=str(RESULT_DIR_DEFAULT))
    parser.add_argument("--log-dir", default=str(LOG_DIR_DEFAULT))
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--show-paths", action="store_true")
    return parser.parse_args()


def run(args: argparse.Namespace, log_path: Path) -> dict[str, Any]:
    download_dir = Path(args.download_dir)
    result_dir = Path(args.result_dir)
    for path in [download_dir, result_dir]:
        path.mkdir(parents=True, exist_ok=True)
    state_json = result_dir / "download_state.json"
    summary_json = result_dir / "download_summary.json"

    rclone_exe = resolve_rclone_exe(args.rclone_exe)
    rclone_config = find_rclone_config(args.rclone_config)
    remote_path = f"{args.remote_name}:{args.remote_folder}"

    atomic_write_json(state_json, {"status": "running", "started_at": now_iso(), "remote_path": remote_path, "download_dir": str(download_dir)})
    remote = list_remote_files(rclone_exe, rclone_config, remote_path, result_dir)
    logging.info("Remote CSV count: %s", len(remote))
    if not args.list_only:
        copy_remote(rclone_exe, rclone_config, remote_path, download_dir, log_path)
    local = local_manifest(download_dir, result_dir)
    validation = validate(remote, local)
    summary = {
        "status": "success" if validation["complete"] else "incomplete",
        "finished_at": now_iso(),
        "remote_path": remote_path,
        "download_dir": str(download_dir),
        "remote_manifest_csv": str(result_dir / "remote_file_manifest.csv"),
        "local_manifest_csv": str(result_dir / "local_file_manifest.csv"),
        "log_path": str(log_path),
        "rclone_config_used": "local/private",
        "validation": validation,
    }
    atomic_write_json(state_json, summary)
    atomic_write_json(summary_json, summary)
    return summary


def main() -> int:
    args = parse_args()
    log_path = setup_logging(Path(args.log_dir))
    if args.show_paths:
        data = {
            "repo_dir": str(REPO_DIR),
            "remote": f"{args.remote_name}:{args.remote_folder}",
            "download_dir": args.download_dir,
            "rclone_exe": args.rclone_exe,
            "rclone_config_search": ["--rclone-config", "$RCLONE_CONFIG", "local/rclone.conf", "default user rclone config"],
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    try:
        summary = run(args, log_path)
        logging.info("Download summary: %s", json.dumps(summary, ensure_ascii=False))
        return 0 if summary["status"] == "success" else 2
    except Exception as exc:  # noqa: BLE001
        err = {"status": "failed", "failed_at": now_iso(), "error": repr(exc), "traceback": traceback.format_exc(), "log_path": str(log_path)}
        result_dir = Path(args.result_dir)
        atomic_write_json(result_dir / "download_state.json", err)
        logging.exception("Download failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
