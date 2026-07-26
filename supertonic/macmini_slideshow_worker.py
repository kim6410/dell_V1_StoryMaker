#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")


def bool_text(value, default=False):
    if value is None:
        return "true" if default else "false"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "true" if str(value).strip().lower() in {"1", "true", "yes", "on"} else "false"


def file_report(path):
    if not path.exists():
        return "missing"
    st = path.stat()
    mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
    return f"exists size={st.st_size} mtime={mtime}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, help="Job directory path")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    json_path = job_dir / "job.json"
    if not json_path.exists():
        print(f"ERROR: job.json not found in {job_dir}", file=sys.stderr)
        return 1

    job_data = json.loads(json_path.read_text(encoding="utf-8"))
    opts = job_data.get("options") or {}
    project_key = job_data["project_key"]
    output_name = Path(job_data.get("output_mp4") or f"{project_key}.mp4").name
    output_stem = Path(output_name).stem

    image_folder = job_dir / "images"
    audio_path = job_dir / "audio.mp3"
    srt_path = job_dir / "subtitles.srt"
    output_dir = job_dir / "output"
    script_dir = Path(__file__).parent

    subtitle_enabled = bool_text(opts.get("subtitle_enabled"), True) == "true"

    cmd = [
        sys.executable, str(script_dir / "SLID_Maker.py"),
        "--image-folder", str(image_folder),
        "--audio", str(audio_path),
        "--project-dir", str(output_dir),
        "--project-key", str(output_stem),
        "--brand-name", str(opts.get("brand_name") or ""),
        "--phone-number", str(opts.get("phone_number") or ""),
        "--brand-size", str(int(opts.get("brand_size", 60) or 60)),
        "--phone-size", str(int(opts.get("phone_size", 43) or 43)),
        "--margin-bottom", str(int(opts.get("margin_bottom", 80) or 80)),
        "--box-enabled", bool_text(opts.get("box_enabled"), True),
        "--stroke-enabled", bool_text(opts.get("stroke_enabled"), True),
        "--shadow-enabled", bool_text(opts.get("shadow_enabled"), True),
        "--subtitle-enabled", bool_text(opts.get("subtitle_enabled"), True),
        "--subtitle-font-size", str(int(opts.get("subtitle_font_size", 10) or 10)),
        "--subtitle-margin", str(int(opts.get("subtitle_margin", 30) or 30)),
        "--resolution", str(opts.get("resolution") or "720x1280"),
        "--fps", str(int(opts.get("fps", 20) or 20)),
        "--nvenc-preset", str(opts.get("nvenc_preset") or "p2"),
    ]
    if subtitle_enabled and srt_path.exists():
        cmd.extend(["--srt", str(srt_path)])
    elif subtitle_enabled:
        print(f"WARNING: subtitle_enabled=true but SRT file is missing: {srt_path}", flush=True)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["SLID_IMAGE_SEC"] = str(opts.get("image_sec", 5.5))
    env["SLID_TRANSITION_SEC"] = str(opts.get("transition_sec", 0.7))
    env["SLID_ZOOM_INTENSITY"] = str(opts.get("zoom_intensity", 0))
    env["SLID_ZOOM_CENTER_ONLY"] = bool_text(opts.get("zoom_center_only"), False)
    env["SLID_MM_SUB_BOOST"] = str(int(opts.get("mm_sub_boost", 20) or 20))
    env["SLID_MM_SUB_LIFT"] = str(int(opts.get("mm_sub_lift", 95) or 95))
    env["SLID_MM_WM_LIFT"] = str(int(opts.get("mm_wm_lift", 0) or 0))
    env["SLID_MM_WM_GAP"] = str(int(opts.get("mm_wm_gap", 25) or 25))
    env["SLID_SUBTITLE_SIZE"] = str(int(opts.get("subtitle_font_size", 10) or 10))
    env["SLID_SUBTITLE_MARGIN"] = str(int(opts.get("subtitle_margin", 40) or 40))
    env["SLID_SUBTITLE_SHADOW_STYLE"] = "soft-wide"

    image_count = len([p for p in image_folder.iterdir() if p.is_file()]) if image_folder.exists() else 0
    print(f"Job dir: {job_dir}", flush=True)
    print(f"Images count: {image_count}", flush=True)
    print(f"Audio: {audio_path} {file_report(audio_path)}", flush=True)
    print(f"Subtitles: {srt_path} {file_report(srt_path)}", flush=True)
    print(f"Output dir: {output_dir}", flush=True)
    print(f"Executing: {' '.join(cmd)}", flush=True)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
        cwd=str(script_dir),
        env=env,
    )

    for line in process.stdout:
        print(line, end="")

    return_code = process.wait()
    expected_output = output_dir / output_name
    if return_code == 0 and expected_output.exists() and expected_output.stat().st_size > 0:
        print(f"SUCCESS: Output file generated at {expected_output}")
        return 0

    print(f"ERROR: Render failed with code {return_code}", file=sys.stderr)
    return 1 if return_code == 0 else return_code


if __name__ == "__main__":
    raise SystemExit(main())
