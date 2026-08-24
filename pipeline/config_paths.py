"""Resolve config paths relative to the handoff package root (parent of config file)."""

from __future__ import annotations

from pathlib import Path

import yaml


def handoff_root(cfg_path: Path) -> Path:
    return cfg_path.resolve().parent


def load_config(cfg_path: Path) -> dict:
    cfg_path = cfg_path.resolve()
    root = handoff_root(cfg_path)
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    for key in ("video_path", "reference_video_path", "work_dir"):
        if key not in cfg or cfg[key] is None:
            continue
        path = Path(cfg[key])
        if not path.is_absolute():
            cfg[key] = str((root / path).resolve())

    colmap_cfg = cfg.get("colmap")
    if colmap_cfg and colmap_cfg.get("colmap_exe"):
        exe = Path(colmap_cfg["colmap_exe"])
        if not exe.is_absolute():
            colmap_cfg["colmap_exe"] = str((root / exe).resolve())

    ocfg = cfg.get("openmvs")
    if ocfg and ocfg.get("openmvs_dir"):
        odir = Path(ocfg["openmvs_dir"])
        if not odir.is_absolute():
            ocfg["openmvs_dir"] = str((root / odir).resolve())

    return cfg


def frame_source_dir(cfg: dict, work: Path) -> Path:
    kf = cfg.get("keyframes", {})
    if kf.get("enabled") and kf.get("use_for_pipeline"):
        return work / kf.get("output_dir", "frames_key")
    return work / "frames_raw"


def masks_equirect_dir(cfg: dict, work: Path) -> Path:
    return work / "masks_equirect"
