# HANDOFF: ffprobe video validation before pipeline. Step 1 of pipeline.py.

"""Check MP4 health and repair / finalize guidance for Insta360-style files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_atom(data: bytes, name: bytes) -> int:
    return data.find(name)


def probe_mp4(path: Path) -> dict:
    size = path.stat().st_size
    with path.open("rb") as f:
        head = f.read(min(size, 512))
        f.seek(max(0, size - 50 * 1024 * 1024))
        tail = f.read()
    return {
        "size_bytes": size,
        "has_moov": find_atom(head, b"moov") >= 0 or find_atom(tail, b"moov") >= 0,
        "has_moof": find_atom(head, b"moof") >= 0 or find_atom(tail, b"moof") >= 0,
        "has_mdat": find_atom(head, b"mdat") >= 0,
        "ffmpeg_signature": b"avc60" in head or b"Lavc" in head,
    }


def run_ffprobe(path: Path) -> tuple[bool, str]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False, "ffprobe not on PATH (install FFmpeg)"
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,duration,codec_name",
        "-of",
        "default=noprint_wrappers=1",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip()
    return True, proc.stdout.strip()


def try_faststart(src: Path, dst: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode == 0 and dst.is_file() and probe_mp4(dst)["has_moov"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose and attempt basic MP4 repair")
    parser.add_argument("video", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Repaired output path")
    parser.add_argument("--reference", type=Path, help="Reference MP4 from same camera/mode")
    args = parser.parse_args()

    if not args.video.is_file():
        print(f"Not found: {args.video}", file=sys.stderr)
        return 1

    info = probe_mp4(args.video)
    print(f"File size: {info['size_bytes'] / (1024**3):.2f} GB")
    print(f"mdat present: {info['has_mdat']}")
    print(f"moov present: {info['has_moov']}")
    print(f"moof present (fragmented): {info['has_moof']}")
    if info["ffmpeg_signature"]:
        print("Note: mdat starts with FFmpeg encoder metadata — file may be an interrupted export.")

    ok, detail = run_ffprobe(args.video)
    if ok:
        print("ffprobe OK:")
        print(detail)
        return 0

    print("ffprobe failed:")
    print(detail)

    if not info["has_moov"]:
        print(
            "\nYour file cannot be decoded until metadata (moov) exists.\n"
            "  1) Wait if file is still copying\n"
            "  2) Insta360 File Repair with a reference MP4\n"
            "  3) ffmpeg -i input.mp4 -c copy -movflags +faststart output.mp4\n"
        )

    if args.output:
        print(f"\nTrying ffmpeg remux -> {args.output}")
        if try_faststart(args.video, args.output):
            print("Remux succeeded; use the output file in config.yaml.")
            return 0
        print("Remux did not produce a playable file.")

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
