"""QA helpers and hard gates for accuracy-first reconstruction."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class QAError(RuntimeError):
    """Raised when a hard quality gate fails — stop before expensive next stages."""


def run_capture(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return (result.stdout or "") + (result.stderr or "")


def analyze_sparse_model(colmap: str, model_dir: Path) -> dict[str, float]:
    text = run_capture([colmap, "model_analyzer", "--path", str(model_dir)])
    stats: dict[str, float] = {"registered_images": 0, "points": 0, "mean_track_length": 0.0}
    for line in text.splitlines():
        lower = line.lower()
        if "registered images:" in lower:
            stats["registered_images"] = float(line.rsplit(":", 1)[-1].strip())
        elif "points:" in lower and "observations" not in lower:
            try:
                stats["points"] = float(line.rsplit(":", 1)[-1].strip().replace(",", ""))
            except ValueError:
                pass
        elif "mean track length:" in lower:
            try:
                stats["mean_track_length"] = float(line.rsplit(":", 1)[-1].strip())
            except ValueError:
                pass
    return stats


def count_images(images_dir: Path) -> int:
    # Windows globs are case-insensitive: *.jpg and *.JPG would double-count.
    names = {p.name.lower() for p in images_dir.iterdir() if p.is_file()}
    return sum(1 for n in names if n.endswith((".jpg", ".jpeg", ".png")))


def gate_sparse(
    colmap: str,
    model_dir: Path,
    images_dir: Path,
    min_ratio: float,
    min_track: float,
) -> dict[str, Any]:
    total = count_images(images_dir)
    stats = analyze_sparse_model(colmap, model_dir)
    registered = int(stats["registered_images"])
    ratio = (registered / total) if total else 0.0
    track = float(stats["mean_track_length"])
    report = {
        "total_images": total,
        "registered_images": registered,
        "registered_ratio": round(ratio, 4),
        "mean_track_length": track,
        "points": int(stats["points"]),
        "model": str(model_dir),
        "min_ratio_required": min_ratio,
        "min_track_required": min_track,
    }
    if ratio < min_ratio:
        raise QAError(
            f"Sparse QA failed: registered {registered}/{total} = {ratio:.1%} "
            f"< required {min_ratio:.0%}. Fix masks/views before dense."
        )
    if track > 0 and track < min_track:
        raise QAError(
            f"Sparse QA failed: mean track length {track:.2f} < required {min_track:.2f}."
        )
    report["ok"] = True
    return report


def write_qa_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def assert_mask_valid_fraction(mask_paths: list[Path], min_fraction: float) -> dict[str, float]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("opencv required for mask QA") from exc

    if not mask_paths:
        raise QAError("No equirect masks found for QA")

    fractions: list[float] = []
    for p in mask_paths[: min(40, len(mask_paths))]:
        m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        fractions.append(float(np.mean(m > 127)))

    if not fractions:
        raise QAError("Could not read any masks for QA")

    mean_frac = float(sum(fractions) / len(fractions))
    report = {
        "sampled_masks": len(fractions),
        "mean_valid_fraction": round(mean_frac, 4),
        "min_required": min_fraction,
    }
    if mean_frac < min_fraction:
        raise QAError(
            f"Mask polarity/coverage QA failed: mean valid pixels {mean_frac:.1%} "
            f"< required {min_fraction:.0%}. COLMAP expects 255=valid, 0=ignore."
        )
    report["ok"] = True
    return report
