"""Path and config helpers for recon_v2.

Project root = parent of recon_v2/ (gpu_handoff_netherlands).
Config relative paths resolve against project root.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

RECON_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = RECON_DIR.parent


def project_root() -> Path:
    return PROJECT_ROOT


def recon_dir() -> Path:
    return RECON_DIR


def default_config_path() -> Path:
    return RECON_DIR / "config_accurate.yaml"


def _resolve(root: Path, value: str | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((root / path).resolve())


def load_config(cfg_path: Path | None = None) -> dict[str, Any]:
    cfg_path = (cfg_path or default_config_path()).resolve()
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    root = PROJECT_ROOT
    for key in ("video_path", "work_dir"):
        if key in cfg and cfg[key] is not None:
            cfg[key] = _resolve(root, cfg[key])

    colmap_cfg = cfg.get("colmap") or {}
    if colmap_cfg.get("colmap_exe"):
        colmap_cfg["colmap_exe"] = _resolve(root, colmap_cfg["colmap_exe"])

    ocfg = cfg.get("openmvs") or {}
    if ocfg.get("openmvs_dir"):
        ocfg["openmvs_dir"] = _resolve(root, ocfg["openmvs_dir"])

    gs = cfg.get("gaussian_splat") or {}
    if gs.get("output_dir"):
        gs["output_dir"] = _resolve(root, gs["output_dir"])

    cfg["_config_path"] = str(cfg_path)
    cfg["_project_root"] = str(root)
    return cfg


def work_dir(cfg: dict) -> Path:
    return Path(cfg["work_dir"])


def ensure_work_dirs(cfg: dict) -> Path:
    work = work_dir(cfg)
    for sub in (
        "frames_raw",
        "frames_key",
        "masks_equirect",
        "images",
        "masks",
        "qa",
        "logs",
        "colmap/sparse",
        "colmap/dense",
        "openmvs",
    ):
        (work / sub).mkdir(parents=True, exist_ok=True)
    return work


def frames_raw_dir(work: Path) -> Path:
    return work / "frames_raw"


def frames_key_dir(cfg: dict, work: Path) -> Path:
    return work / cfg.get("keyframes", {}).get("output_dir", "frames_key")


def equirect_source_dir(cfg: dict, work: Path) -> Path:
    """Frames used for mask/dewarp: keyframes if enabled, else raw."""
    kf = cfg.get("keyframes", {})
    if kf.get("enabled", True):
        return frames_key_dir(cfg, work)
    return frames_raw_dir(work)


def status_path(work: Path) -> Path:
    return work / "status.json"


def write_status(work: Path, stage: str, ok: bool, detail: dict | None = None) -> None:
    path = status_path(work)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    stages = data.setdefault("stages", {})
    stages[stage] = {
        "ok": ok,
        "time": datetime.now(timezone.utc).isoformat(),
        "detail": detail or {},
    }
    data["last_stage"] = stage
    data["last_ok"] = ok
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
