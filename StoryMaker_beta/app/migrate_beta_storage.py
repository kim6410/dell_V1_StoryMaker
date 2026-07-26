from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from app.beta_storage import canonical_audio_path, prune_unreferenced_shared_images, store_normalized_image

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "data" / "jobs"
DB_PATH = ROOT / "data" / "storymaker_beta.db"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def is_test_job(name: str) -> bool:
    lowered = name.lower()
    return "_test_" in lowered or lowered.startswith(("beta_reuse_test", "beta_overlay_test", "beta_style_test", "beta_ai_prompt_test"))


def write_json(path: Path, payload: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def migrate_job(job_dir: Path, apply: bool) -> dict[str, int]:
    result_path = job_dir / "result.json"
    if not result_path.exists():
        return {"jobs": 0, "images": 0, "image_bytes": 0, "wav_removed": 0, "wav_bytes": 0, "zip_bytes": 0}
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assets = result.setdefault("assets", {})
    current_images = [Path(str(value)) for value in assets.get("images") or [] if value]
    migrated_images: list[str] = []
    image_sources_to_remove: set[Path] = set()
    image_bytes = 0

    for source in current_images:
        if not source.exists() or source.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        image_bytes += source.stat().st_size
        if apply:
            with source.open("rb") as stream:
                shared = store_normalized_image(stream)
            migrated_images.append(str(shared))
            try:
                if source.resolve().is_relative_to((job_dir / "input").resolve()):
                    image_sources_to_remove.add(source)
            except ValueError:
                pass
        else:
            migrated_images.append(str(source))

    output = job_dir / "output"
    canonical = canonical_audio_path(job_dir)
    mixed_legacy = output / "shortform" / "mixed_voice_music.wav"
    voice_legacy = output / "voice.wav"
    audio_source = mixed_legacy if mixed_legacy.exists() else (canonical if canonical.exists() else (voice_legacy if voice_legacy.exists() else None))
    wav_candidates = [path for path in (voice_legacy, mixed_legacy) if path.exists()]
    wav_bytes = sum(path.stat().st_size for path in wav_candidates)
    wav_removed = len(wav_candidates)

    zip_roots = [output / "download_cache", output / "downloads"]
    zip_bytes = 0
    for root in zip_roots:
        if root.exists():
            zip_bytes += sum(path.stat().st_size for path in root.rglob("*") if path.is_file())

    if apply:
        if migrated_images:
            assets["images"] = migrated_images
        if audio_source is not None:
            canonical.parent.mkdir(parents=True, exist_ok=True)
            if audio_source.resolve() != canonical.resolve():
                temp = canonical.with_suffix(".wav.tmp")
                shutil.copy2(audio_source, temp)
                temp.replace(canonical)
            assets["shortform_mixed_audio"] = str(canonical)
            shortform = result.setdefault("shortform", {})
            shortform["mixed_audio"] = str(canonical)
        write_json(result_path, result)

        for source in image_sources_to_remove:
            source.unlink(missing_ok=True)
        input_dir = job_dir / "input"
        if input_dir.exists() and not any(input_dir.iterdir()):
            input_dir.rmdir()
        for legacy in (voice_legacy, mixed_legacy):
            if legacy.resolve() != canonical.resolve():
                legacy.unlink(missing_ok=True)
        for root in zip_roots:
            if root.exists():
                shutil.rmtree(root)

    return {
        "jobs": 1,
        "images": len(current_images),
        "image_bytes": image_bytes,
        "wav_removed": wav_removed,
        "wav_bytes": wav_bytes,
        "zip_bytes": zip_bytes,
    }


def delete_test_jobs(test_dirs: list[Path], apply: bool) -> tuple[int, int]:
    total_bytes = sum(sum(path.stat().st_size for path in job.rglob("*") if path.is_file()) for job in test_dirs)
    if not apply:
        return len(test_dirs), total_bytes
    with sqlite3.connect(DB_PATH) as connection:
        for job in test_dirs:
            connection.execute("DELETE FROM beta_jobs WHERE beta_job_id=?", (job.name,))
            shutil.rmtree(job)
        connection.commit()
    return len(test_dirs), total_bytes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    totals = {"jobs": 0, "images": 0, "image_bytes": 0, "wav_removed": 0, "wav_bytes": 0, "zip_bytes": 0}
    test_dirs = [path for path in JOBS_DIR.iterdir() if path.is_dir() and is_test_job(path.name)]
    for job_dir in sorted(JOBS_DIR.iterdir()):
        if not job_dir.is_dir() or job_dir in test_dirs or not job_dir.name.startswith("beta_"):
            continue
        stats = migrate_job(job_dir, args.apply)
        for key, value in stats.items():
            totals[key] += value

    test_count, test_bytes = delete_test_jobs(test_dirs, args.apply)
    pruned_count = 0
    pruned_bytes = 0
    if args.apply:
        pruned_count, pruned_bytes = prune_unreferenced_shared_images(JOBS_DIR)

    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        **totals,
        "test_jobs": test_count,
        "test_bytes": test_bytes,
        "shared_images_pruned": pruned_count,
        "shared_bytes_pruned": pruned_bytes,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
