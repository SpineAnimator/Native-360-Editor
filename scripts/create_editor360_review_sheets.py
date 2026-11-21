#!/usr/bin/env python3
"""Passive all-frame visual review sheets from real Spine Editor PNGs.

This tool NEVER makes a Spine animation, regenerates PSD pixels, approves
artwork, or changes a source image. The invoking workflow is responsible for
the provenance of its licensed Editor screenshots.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont


_FRAME_NUMBER = re.compile(r"(\d+)\.png$", re.IGNORECASE)
_MAX_FRAME_PIXELS = 16_000_000


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _number(path):
    match = _FRAME_NUMBER.search(path.name)
    if not match:
        raise ValueError(f"Unnumbered Editor PNG: {path.name}")
    return int(match.group(1))


def _load_frames(directory, expected_count):
    paths = list(directory.rglob("*.png"))
    if len(paths) != expected_count:
        raise ValueError(f"Expected {expected_count} official Editor PNGs, found {len(paths)}")
    indexed = sorted((_number(path), path) for path in paths)
    ids = [index for index, _ in indexed]
    if ids != list(range(expected_count)):
        raise ValueError("Duplicate, missing or out-of-order Editor frame indexes")
    frames, evidence = [], []
    expected_size = None
    for index, path in indexed:
        raw = path.read_bytes()
        with Image.open(path) as file:
            file.load()
            rgba = file.convert("RGBA")
        if rgba.width * rgba.height > _MAX_FRAME_PIXELS:
            raise ValueError("Editor frame exceeds safe pixel review budget")
        if expected_size is None:
            expected_size = rgba.size
        if rgba.size != expected_size:
            raise ValueError(f"Editor frame {index} has inconsistent dimensions")
        evidence.append({
            "frame": index,
            "filename": path.name,
            "png_sha256": _sha256(raw),
            "rgba_sha256": _sha256(rgba.tobytes()),
            "width": rgba.width,
            "height": rgba.height
        })
        frames.append(rgba)
    if frames[0].tobytes() != frames[-1].tobytes():
        raise ValueError("Original first-frame source pixels do not return at final frame")
    return frames, evidence


def _compose(frames, indexes, target, columns, max_width, max_height, subtitle):
    margin, header, label_height = 12, 53, 24
    cell_width, cell_height = max_width + margin * 2, max_height + label_height + margin * 2
    rows = math.ceil(len(indexes) / columns)
    width = columns * cell_width + margin
    height = header + rows * cell_height + margin
    if width * height > 30_000_000:
        raise ValueError("Review sheet would exceed safe image budget")
    sheet = Image.new("RGB", (width, height), "#f7f7f7")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((margin, 10), "SPINE EDITOR 4.3.26  |  REAL RENDER FRAMES  |  NOT ART APPROVED",
              fill="#161616", font=font)
    draw.text((margin, 28), subtitle, fill="#555555", font=font)
    for n, index in enumerate(indexes):
        row, col = divmod(n, columns)
        x, y = margin + col * cell_width, header + row * cell_height
        draw.rectangle((x, y, x + cell_width - margin, y + cell_height - margin),
                       fill="#ffffff", outline="#cccccc")
        frame = frames[index].convert("RGB")
        frame.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        px = x + (cell_width - margin - frame.width) // 2
        py = y + margin + (max_height - frame.height) // 2
        sheet.paste(frame, (px, py))
        draw.text((x + margin, y + margin + max_height + 2),
                  f"Frame {index:02d} / {len(frames)-1:02d}", fill="#222222", font=font)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, format="JPEG", quality=92, subsampling=0, optimize=True)


def build(frames_dir, sheet_path, focus_path, report_path, expected_count=40, source_ref=""):
    if not 30 <= expected_count <= 240:
        raise ValueError("Expected full Editor sequence must contain 30..240 frames")
    if source_ref and not re.fullmatch(r"[a-f0-9]{40}", source_ref):
        raise ValueError("Source reference must be an exact 40-character commit SHA")
    frames, evidence = _load_frames(Path(frames_dir), expected_count)
    all_indexes = list(range(expected_count))
    if expected_count == 40:
        focus = [0, 8, 12, 15, 16, 19, 20, 24, 25, 26, 27, 28, 29, 31, 36, 39]
    else:
        focus = sorted(set(round((expected_count - 1) * i / 15) for i in range(16)))
    sheet_path, focus_path, report_path = map(Path, (sheet_path, focus_path, report_path))
    _compose(frames, all_indexes, sheet_path, 8, 278, 266,
             "Complete sequential review: every frame must be judged, including draw order and motion")
    _compose(frames, focus, focus_path, 4, 420, 399,
             "Detail review: silhouettes, side thickness, rear material, leaves, seams and overlap")
    report = {
        "kind": "2spine-official-editor-360-frame-review",
        "input": "licensed-editor-rendered-PNGs-provided-by-workflow",
        "source_git_sha": source_ref or None,
        "spine_editor_version": "4.3.26",
        "expected_frames": expected_count,
        "actual_frames": len(frames),
        "all_frame_indexes_verified": True,
        "source_pixel_closure_exact": True,
        "original_pngs_modified": False,
        "artistic_quality_approved": False,
        "publication_ready": False,
        "review_sheet": sheet_path.name,
        "review_sheet_sha256": _sha256(sheet_path.read_bytes()),
        "focus_sheet": focus_path.name,
        "focus_sheet_sha256": _sha256(focus_path.read_bytes()),
        "focused_frame_indexes": focus,
        "frames": evidence,
        "notice": "Only passive previews and SHA-256 evidence; NOT artistic approval or additional generated frames."
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--sheet-out", type=Path, required=True)
    parser.add_argument("--focus-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=40)
    parser.add_argument("--source-ref", default="")
    args = parser.parse_args()
    report = build(args.frames_dir, args.sheet_out, args.focus_out, args.report_out,
                   args.expected_count, args.source_ref)
    print("OFFICIAL_SPINE_360_REVIEW_EVIDENCE", json.dumps({
        "frames": report["actual_frames"],
        "exact_source_return": report["source_pixel_closure_exact"],
        "full_sheet_sha256": report["review_sheet_sha256"],
        "focused_frames": report["focused_frame_indexes"],
        "artistic_quality_approved": False
    }))


if __name__ == "__main__":
    main()
