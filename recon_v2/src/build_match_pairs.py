"""Build view-aware image pairs for multi-view video COLMAP matching.

Image naming: frame_XXXXXX_vYY.jpg
Pairs:
  - same view across nearby frames (temporal)
  - adjacent yaw views within the same frame
  - adjacent yaw views on nearby frames (cross)
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

from paths import ensure_work_dirs, load_config, write_status

FRAME_RE = re.compile(r"^(frame_\d+)_v(\d+)\.jpg$", re.IGNORECASE)


def parse_images(images_dir: Path) -> dict[str, dict[int, str]]:
    """frame_stem -> {view_idx: filename}"""
    by_frame: dict[str, dict[int, str]] = defaultdict(dict)
    for p in sorted(images_dir.glob("*.jpg")):
        m = FRAME_RE.match(p.name)
        if not m:
            continue
        by_frame[m.group(1)][int(m.group(2))] = p.name
    return dict(by_frame)


def build_pairs(
    by_frame: dict[str, dict[int, str]],
    temporal_radius: int = 8,
    cross_radius: int = 2,
) -> list[tuple[str, str]]:
    frames = sorted(by_frame.keys())
    pairs: set[tuple[str, str]] = set()

    def add(a: str, b: str) -> None:
        if a == b:
            return
        if a > b:
            a, b = b, a
        pairs.add((a, b))

    n_views = max((max(v.keys()) for v in by_frame.values()), default=-1) + 1

    for fi, frame in enumerate(frames):
        views = by_frame[frame]
        # Adjacent views in same frame (circular yaw)
        for v, name in views.items():
            for dv in (1, -1, 2, -2):
                nv = (v + dv) % n_views
                if nv in views:
                    add(name, views[nv])

        # Temporal same-view + nearby cross-view
        for delta in range(1, temporal_radius + 1):
            for sign in (1, -1):
                oi = fi + sign * delta
                if oi < 0 or oi >= len(frames):
                    continue
                other = by_frame[frames[oi]]
                for v, name in views.items():
                    if v in other:
                        add(name, other[v])
                    if delta <= cross_radius:
                        for dv in (1, -1):
                            nv = (v + dv) % n_views
                            if nv in other:
                                add(name, other[nv])

    return sorted(pairs)


def write_pairs_file(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    images = work / "images"
    by_frame = parse_images(images)
    if not by_frame:
        print(f"No frame_*_v*.jpg in {images}")
        return 1

    match_cfg = cfg.get("matching", {})
    temporal = int(match_cfg.get("temporal_radius", 8))
    cross = int(match_cfg.get("cross_radius", 2))
    pairs = build_pairs(by_frame, temporal, cross)

    out = work / "colmap" / "match_pairs.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for a, b in pairs:
            f.write(f"{a} {b}\n")

    detail = {
        "frames": len(by_frame),
        "pairs": len(pairs),
        "temporal_radius": temporal,
        "cross_radius": cross,
        "path": str(out),
    }
    print(f"Wrote {len(pairs):,} pairs for {len(by_frame)} frames -> {out}")
    write_status(work, "match_pairs", True, detail)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return write_pairs_file(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
