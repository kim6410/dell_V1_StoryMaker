from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps

ROOT = Path(os.getenv("STORYMAKER_BETA_ROOT", "/home/bourne/StoryMaker_1/StoryMaker_beta"))
SHARED_IMAGE_DIR = ROOT / "data" / "media" / "images"
MAX_IMAGE_SIDE = 1920
JPEG_QUALITY = 85


def store_normalized_image(source: BinaryIO) -> Path:
    """Store one normalized JPEG by content hash and return the shared path."""
    SHARED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
        with tempfile.NamedTemporaryFile(dir=SHARED_IMAGE_DIR, suffix=".jpg", delete=False) as stream:
            temp_path = Path(stream.name)
        try:
            image.save(temp_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
            digest = hashlib.sha256(temp_path.read_bytes()).hexdigest()
            target = SHARED_IMAGE_DIR / f"{digest}.jpg"
            if target.exists():
                temp_path.unlink(missing_ok=True)
            else:
                temp_path.replace(target)
            return target
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


def canonical_audio_path(job_dir: Path) -> Path:
    return job_dir / "output" / "audio.wav"


def remove_tree(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def prune_unreferenced_shared_images(jobs_dir: Path) -> tuple[int, int]:
    referenced: set[Path] = set()
    for result_path in jobs_dir.glob("beta_*/result.json"):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        assets = result.get("assets") if isinstance(result.get("assets"), dict) else {}
        for value in assets.get("images") or []:
            try:
                path = Path(str(value)).resolve()
            except Exception:
                continue
            if path.parent == SHARED_IMAGE_DIR.resolve():
                referenced.add(path)

    removed = 0
    removed_bytes = 0
    if not SHARED_IMAGE_DIR.exists():
        return removed, removed_bytes
    for path in SHARED_IMAGE_DIR.glob("*.jpg"):
        resolved = path.resolve()
        if resolved in referenced:
            continue
        try:
            removed_bytes += path.stat().st_size
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed, removed_bytes
