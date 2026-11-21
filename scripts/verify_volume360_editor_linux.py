#!/usr/bin/env python3
"""Native Spine Editor 4.3.26 IMPORT + RE-EXPORT + FULL RENDER of 2Spine's real-PSD 360 ZIP.

This is a technical editor gate, NOT artist approval. Does not synthesize animation.
Secrets are never logged, and the downloaded archive is treated as untrusted input.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from PIL import Image

VERSION = "4.3.26"
CLIP = "volume360"
PNG = b"\x89PNG\r\n\x1a\n"


def block(message):
    raise RuntimeError("SPINE_360_EDITOR_BLOCKED: " + message)


def invoke(spine, args, license_code, timeout=600):
    cmd = [str(spine), "-u", VERSION, *map(str, args)]
    result = subprocess.run(cmd, input=license_code + "\n", text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=timeout, check=False)
    log = result.stdout.replace(license_code, "[REDACTED]") if license_code else result.stdout
    log = re.sub(r"(?im)^Licensed to:.*$", "Licensed to: [REDACTED]", log)
    print("SPINE_CLI_EXIT", result.returncode, "TAIL", log[-2800:])
    if result.returncode:
        block("licensed Spine CLI returned nonzero")
    if re.search(r"invalid mesh edge|mesh internal edges lost|mesh has internal vertex outside hull|image for attachment.*not found|data version mismatch|error importing|invalid mesh", log, re.I):
        block("Spine Editor reported a mesh/import/version error")


def safe_unzip(archive, target):
    with zipfile.ZipFile(archive) as source:
        members = source.namelist()
        if len(members) != len(set(members)) or len(members) > 800:
            block("ZIP has duplicate or excessive entries")
        if source.testzip() is not None:
            block("ZIP CRC failed")
        if sum(x.file_size for x in source.infolist()) > 180 * 1024 * 1024:
            block("ZIP expanded data exceeds 180 MB")
        for item in source.infolist():
            p = Path(item.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in item.filename:
                block("ZIP includes unsafe path")
        source.extractall(target)
    for required in ("skeleton.json", "skeleton.atlas", "manifest.json"):
        if not (target / required).is_file():
            block("ZIP lacks " + required)


def read_meshes(skeleton):
    return {
        slot + "/" + name: attachment
        for skin in skeleton.get("skins", [])
        for slot, attachments in skin.get("attachments", {}).items()
        for name, attachment in attachments.items()
        if attachment.get("type") == "mesh"
    }


def duration(clip):
    times = []
    def visit(value):
        if isinstance(value, dict):
            if "time" in value and isinstance(value["time"], (int, float)):
                times.append(value["time"])
            for v in value.values():
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)
    visit(clip)
    if not times or not .4 <= max(times) <= 15:
        block("invalid animated clip duration")
    return max(times)


def run(archive, launcher, output):
    archive = archive.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    license_code = os.getenv("SPINE_LICENSE", "").strip()
    if not license_code or not launcher.is_file() or not os.access(launcher, os.X_OK):
        block("Spine Editor 4.3.26 license or launcher unavailable")
    if not archive.is_file() or archive.stat().st_size > 80 * 1024 * 1024:
        block("missing or oversized source artifact")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    source = output / "source"
    source.mkdir(exist_ok=True)
    safe_unzip(archive, source)
    report = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    skeleton = json.loads((source / "skeleton.json").read_text(encoding="utf-8"))
    if (report.get("kind") != "2spine-real-psd-360-source-audit"
        or report.get("originalRgbaUnchanged") is not True
        or report.get("originalPngSha256Verified") is not True
        or report.get("realRuntimeImported") is not True
        or report.get("editorVerified") is not False
        or report.get("artisticApproval") is not False
        or report.get("sourceLayers", 0) < 1
        or not re.fullmatch("[0-9a-f]{64}", report.get("sourceSha256", ""))):
        block("source PSD 360 provenance contract failed")
    if skeleton.get("skeleton", {}).get("spine") != VERSION:
        block("input skeleton is not Spine 4.3.26")
    if set(skeleton.get("animations", {})) != {CLIP}:
        block("turn animation missing or untrusted extra clips")
    original_slots = [s["name"] for s in skeleton.get("slots", []) if s["name"].startswith("scene_slot_")]
    if len(original_slots) != report["sourceLayers"]:
        block("original PSD slot count differs from source manifest")
    for slot in original_slots:
        item = next(x for x in skeleton["slots"] if x["name"] == slot)
        if item.get("attachment") != slot:
            block("original PSD setup attachment was changed: " + slot)
    meshes = read_meshes(skeleton)
    if len(meshes) < 2 or any(len(m.get("edges", [])) % 2 for m in meshes.values()):
        block("editable 360 mesh geometry incomplete")
    png_files = list((source / "images").glob("*.png"))
    if len(png_files) < report["sourceLayers"] + 2:
        block("PSD and independent derived PNGs are missing")
    if any(p.read_bytes()[:8] != PNG for p in png_files):
        block("bad PNG signature")

    native = output / "real-psd-volume360-editor-4.3.26.spine"
    # Install original image assets beside the eventual native project before importing.
    shutil.copytree(source / "images", output / "images", dirs_exist_ok=True)
    # The official CLI imports a Spine JSON scene and creates its native editable project.
    invoke(launcher, ["-i", source / "skeleton.json", "-o", native,
                      "-r", "cherry_volume360"], license_code)
    if not native.is_file() or native.stat().st_size < 100:
        block("no real native .spine project produced")
    shutil.copytree(source / "images", output / "images", dirs_exist_ok=True)
    exports = output / "roundtrip"
    exports.mkdir(exist_ok=True)
    settings = output / "nonessential.export.json"
    settings.write_text(json.dumps({
        "class": "export-json", "extension": ".json", "format": "JSON",
        "prettyPrint": True, "nonessential": True, "cleanUp": False,
        "packAtlas": None, "warnings": True, "all": True,
        "output": "", "open": False
    }), encoding="utf-8")
    invoke(launcher, ["-i", native, "-o", exports, "-e", settings], license_code)
    candidates = list(exports.rglob("*.json"))
    if len(candidates) != 1:
        block("licensed editor failed to round-trip exactly one JSON")
    back = json.loads(candidates[0].read_text(encoding="utf-8"))
    if back.get("skeleton", {}).get("spine") != VERSION:
        block("roundtrip Editor version is not 4.3.26")
    if [x["name"] for x in back.get("slots", [])] != [x["name"] for x in skeleton["slots"]]:
        block("Spine Editor changed the original slot order")
    if set(back.get("animations", {})) != {CLIP}:
        block("Spine Editor lost the turn animation")
    result_meshes = read_meshes(back)
    if result_meshes.keys() != meshes.keys():
        block("Spine Editor discarded a reconstructed mesh")
    for key, expected in meshes.items():
        mesh = result_meshes[key]
        uv_count = len(mesh.get("uvs", []))
        edges = mesh.get("edges")
        if not isinstance(edges, list) or len(edges) < len(expected.get("edges", [])) or len(edges) % 2:
            block("Spine Editor lost internal mesh edges: " + key)
        if any(not isinstance(v, int) or v % 2 or not 0 <= v < uv_count for v in edges):
            block("Spine Editor roundtrip has invalid mesh edges: " + key)
    clip_duration = duration(skeleton["animations"][CLIP])
    frame_rate = 24
    target = output / "screenshots"
    target.mkdir(exist_ok=True)
    render_settings = output / "turn.export.json"
    render_settings.write_text(json.dumps({
        "class": "export-png", "exportType": "animation",
        "skeletonType": "single", "skeleton": "cherry_volume360",
        "animationType": "single", "animation": CLIP,
        "skinType": "current", "scale": 100,
        "renderImages": True, "renderBones": False,
        "renderOthers": False, "background": None,
        "fps": frame_rate, "lastFrame": True,
        "rangeStart": 0, "rangeEnd": math.ceil(clip_duration * frame_rate),
        "compression": 6, "pad": False, "msaa": 4,
        "renderSelection": False, "open": False
    }), encoding="utf-8")
    invoke(launcher, ["-i", native, "-o", target, "-e", render_settings],
           license_code, timeout=400)
    images = sorted(target.rglob("*.png"))
    expected_frames = math.ceil(clip_duration * frame_rate) + 1
    if len(images) < expected_frames:
        block(f"incomplete native Spine animation render: {len(images)} < {expected_frames}")
    for frame in images:
        with Image.open(frame) as im:
            im.load()
            if im.width < 2 or im.height < 2 or im.convert("RGBA").getchannel("A").getbbox() is None:
                block("blank licensed Editor frame " + frame.name)
    # A checklist for independent artistic review, never a synthetic approval.
    result = {
        "source_archive_sha256": digest,
        "source_psd_sha256": report["sourceSha256"],
        "source_layers_preserved": len(original_slots),
        "original_png_count": report["sourceLayers"],
        "generated_material_png_count": len(png_files) - report["sourceLayers"],
        "native_spine_project_verified": True,
        "editor_import_verified": True,
        "roundtrip_spine_version": VERSION,
        "original_slots_and_order_preserved": True,
        "editable_mesh_count": len(result_meshes),
        "mesh_nonessential_edges_roundtripped": True,
        "turn_clip": CLIP,
        "official_render_frames": len(images),
        "duration_seconds": clip_duration,
        "artistic_quality_approved": False,
        "rear_material_artist_verified": False,
        "publication_ready": False,
        "note": "Native Editor import, nonessential mesh re-export and entire 24fps render. Artist review required."
    }
    (output / "official-360-editor-report.json").write_text(json.dumps(result, indent=2) + "\n")
    print("OFFICIAL_SPINE_360_EDITOR_TECHNICAL_PASS", json.dumps(result))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--spine", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    run(args.archive, args.spine.resolve(), args.output)
