# HANDOFF: Extract JPEG frames from video via ffmpeg. Output: frames_raw/frame_*.jpg
# Config: extract_fps, max_frames. See handoff/docs/CODE_ANNOTATIONS.md

"""Extract equirectangular or perspective frames from the repaired video."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from config_paths import load_config

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def extract_with_ffmpeg(video: Path, out_dir: Path, fps: float, max_frames: int) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%06d.jpg"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vf",
        f"fps={fps}",
        "-q:v",
        "2",
        "-frames:v",
        str(max_frames),
        str(pattern),
    ]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob("frame_*.jpg"))


def extract_with_opencv(video: Path, out_dir: Path, fps: float, max_frames: int) -> list[Path]:
    if cv2 is None:
        raise RuntimeError("OpenCV not installed and ffmpeg not on PATH")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV cannot open video: {video}")
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(native_fps / fps)))
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    idx = 0
    frame_i = 0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    total_est = min(max_frames, total // step if total else max_frames)
    pbar = tqdm(total=total_est, desc="extract") if tqdm else None
    while len(saved) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_i % step == 0:
            path = out_dir / f"frame_{idx:06d}.jpg"
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            saved.append(path)
            idx += 1
            if pbar:
                pbar.update(1)
        frame_i += 1
    cap.release()
    if pbar:
        pbar.close()
    return saved


def main(cfg_path: Path | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    cfg = load_config(args.config or cfg_path or (root / "config.yaml"))
    video = Path(cfg["video_path"])
    work = Path(cfg["work_dir"])
    raw_dir = work / "frames_raw"
    fps = float(cfg.get("extract_fps", 2.0))
    max_frames = int(cfg.get("max_frames", 600))

    if shutil.which("ffmpeg"):
        paths = extract_with_ffmpeg(video, raw_dir, fps, max_frames)
    else:
        paths = extract_with_opencv(video, raw_dir, fps, max_frames)

    print(f"Extracted {len(paths)} frames to {raw_dir}")


if __name__ == "__main__":
    main()
