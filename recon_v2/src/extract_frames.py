"""Extract high-quality JPEG frames from the source video via ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from paths import ensure_work_dirs, frames_raw_dir, load_config, write_status


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH. Install with: winget install Gyan.FFmpeg")
    return exe


def extract_frames(cfg_path: Path | None = None) -> int:
    cfg = load_config(cfg_path)
    work = ensure_work_dirs(cfg)
    out = frames_raw_dir(work)
    video = Path(cfg["video_path"])
    if not video.is_file():
        print(f"Missing video: {video}", file=sys.stderr)
        return 1

    ext = cfg.get("extract", {})
    fps = float(ext.get("fps", 5.0))
    q = int(ext.get("jpeg_quality", 2))

    # Clear previous raw frames for a clean run
    for old in out.glob("frame_*.jpg"):
        old.unlink()

    pattern = str(out / "frame_%06d.jpg")
    cmd = [
        find_ffmpeg(),
        "-y",
        "-i",
        str(video),
        "-vf",
        f"fps={fps}",
        "-q:v",
        str(q),
        pattern,
    ]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

    n = len(list(out.glob("frame_*.jpg")))
    print(f"Extracted {n} frames at {fps} fps -> {out}")
    if n < 50:
        print("WARNING: very few frames extracted", file=sys.stderr)
        write_status(work, "extract", False, {"frames": n, "fps": fps})
        return 2

    write_status(work, "extract", True, {"frames": n, "fps": fps})
    return 0


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Extract frames from video")
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args()
    return extract_frames(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
