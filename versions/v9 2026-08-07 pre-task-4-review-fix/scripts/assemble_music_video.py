"""Assemble accepted video clips and mux only the supplied master audio."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from pathlib import Path
from typing import Any

try:
    from scripts.validate_project import ManifestJsonError, load_manifest, validate_manifest
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from validate_project import ManifestJsonError, load_manifest, validate_manifest


MP4_COPY_AUDIO_CODECS = frozenset({"aac", "mp3", "alac"})


class AssemblyError(ValueError):
    """Raised when an input cannot be assembled without violating the contract."""


def _require_tools() -> None:
    for name in ("ffmpeg", "ffprobe"):
        if shutil.which(name) is None:
            raise AssemblyError(f"Required tool is unavailable: {name}")


def _run(arguments: list[str], context: str) -> bytes:
    try:
        completed = subprocess.run(
            arguments,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise AssemblyError(f"Required tool is unavailable: {arguments[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        message = f"{context}: {detail}" if detail else context
        raise AssemblyError(message) from error
    return completed.stdout


def _probe(path: Path, *, count_frames: bool = False) -> dict[str, Any]:
    arguments = ["ffprobe", "-v", "error"]
    if count_frames:
        arguments.append("-count_frames")
    arguments.extend(["-show_streams", "-show_format", "-of", "json", str(path)])
    raw = _run(arguments, f"Could not inspect media: {path}")
    try:
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AssemblyError(f"Could not read media facts: {path}") from error
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise AssemblyError(f"Could not read media facts: {path}")
    return data


def _stream(probe: dict[str, Any], codec_type: str, path: Path) -> dict[str, Any]:
    try:
        return next(item for item in probe["streams"] if item.get("codec_type") == codec_type)
    except (KeyError, StopIteration, TypeError) as error:
        raise AssemblyError(f"Media has no {codec_type} stream: {path}") from error


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise AssemblyError(f"Invalid decimal value for {label}") from error
    if not result.is_finite():
        raise AssemblyError(f"Invalid decimal value for {label}")
    return result


def _format_decimal(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _target_frames(manifest: dict[str, object]) -> tuple[int, int, int, Decimal]:
    master = manifest["master"]
    delivery = manifest["delivery"]
    assert isinstance(master, dict) and isinstance(delivery, dict)
    rate = delivery["frame_rate"]
    assert isinstance(rate, dict)
    fps_num = int(rate["fps_num"])
    fps_den = int(rate["fps_den"])
    duration = _decimal(master["decoded_duration_seconds"], "master duration")
    with localcontext() as context:
        context.prec = max(80, len(duration.as_tuple().digits) + 32)
        frames = int(
            (duration * Decimal(fps_num) / Decimal(fps_den)).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
    return frames, fps_num, fps_den, duration


def _visual_path(output_path: Path) -> Path:
    return output_path.with_name(f".{output_path.name}.visual.mp4")


def _audio_codec(path: Path) -> str:
    probe = _probe(path)
    stream = _stream(probe, "audio", path)
    codec = stream.get("codec_name")
    if not isinstance(codec, str) or not codec:
        raise AssemblyError(f"Could not identify master audio codec: {path}")
    return codec


def build_ffmpeg_command(
    manifest: dict[str, object], output_path: Path
) -> list[str]:
    """Build the final explicit video plus master-audio mux command.

    The manifest passed here must contain a resolved master path. ``assemble``
    creates that safe copy after validating the canonical input manifest.
    """
    output = Path(output_path)
    master = manifest.get("master")
    if not isinstance(master, dict) or not isinstance(master.get("path"), str):
        raise AssemblyError("Manifest has no usable master path")
    master_path = Path(master["path"])
    codec = _audio_codec(master_path)
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-n",
        "-i",
        str(_visual_path(output)),
        "-i",
        str(master_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "copy" if codec in MP4_COPY_AUDIO_CODECS else "aac",
    ]
    if codec not in MP4_COPY_AUDIO_CODECS:
        command.extend(["-b:a", "320k"])
    command.extend(
        [
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return command


def _resolve_media_path(project_root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AssemblyError(f"{label} path is missing")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in value:
        raise AssemblyError(f"{label} path escapes the project root")
    candidate = project_root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise AssemblyError(f"{label} does not exist: {candidate}") from error
    if not resolved.is_relative_to(project_root):
        raise AssemblyError(f"{label} path escapes the project root")
    if not resolved.is_file():
        raise AssemblyError(f"{label} must be a file: {candidate}")
    return resolved


def _validate_and_resolve(
    manifest: dict[str, object], project_root: Path
) -> dict[str, object]:
    diagnostics = validate_manifest(manifest)
    if diagnostics:
        codes = ", ".join(item.code for item in diagnostics)
        raise AssemblyError(f"Manifest validation failed: {codes}")

    shots = manifest.get("shots")
    assert isinstance(shots, list)
    for index, shot in enumerate(shots):
        assert isinstance(shot, dict)
        if not isinstance(shot.get("accepted_source"), dict):
            raise AssemblyError(f"Shot {index + 1} has no accepted source")

    try:
        root = Path(project_root).resolve(strict=True)
    except OSError as error:
        raise AssemblyError(f"Project root does not exist: {project_root}") from error
    if not root.is_dir():
        raise AssemblyError(f"Project root must be a directory: {project_root}")

    resolved_manifest = copy.deepcopy(manifest)
    master = resolved_manifest["master"]
    assert isinstance(master, dict)
    master["path"] = str(_resolve_media_path(root, master["path"], "Master audio"))
    resolved_shots = resolved_manifest["shots"]
    assert isinstance(resolved_shots, list)
    for index, shot in enumerate(resolved_shots):
        assert isinstance(shot, dict)
        source = shot["accepted_source"]
        assert isinstance(source, dict)
        source["path"] = str(
            _resolve_media_path(root, source["path"], f"Shot {index + 1} accepted source")
        )
    return resolved_manifest


def _media_duration(probe: dict[str, Any], stream: dict[str, Any], path: Path) -> Decimal:
    for value in (stream.get("duration"), probe.get("format", {}).get("duration")):
        if value not in (None, "N/A"):
            duration = _decimal(value, f"media duration for {path}")
            if duration >= 0:
                return duration
    raise AssemblyError(f"Could not determine media duration: {path}")


def _check_source_coverage(
    manifest: dict[str, object], fps_num: int, fps_den: int
) -> None:
    shots = manifest["shots"]
    assert isinstance(shots, list)
    for index, shot in enumerate(shots):
        assert isinstance(shot, dict)
        timeline = shot["timeline"]
        source = shot["accepted_source"]
        assert isinstance(timeline, dict) and isinstance(source, dict)
        path = Path(str(source["path"]))
        probe = _probe(path)
        video = _stream(probe, "video", path)
        actual_duration = _media_duration(probe, video, path)
        trim_start = _decimal(source["trim_start_seconds"], "source trim start")
        frame_count = int(timeline["end_frame"]) - int(timeline["start_frame"])
        required_end = trim_start + Decimal(frame_count) * Decimal(fps_den) / Decimal(fps_num)
        if actual_duration + Decimal("0.001") < required_end:
            raise AssemblyError(
                f"Shot {index + 1} source coverage ends at "
                f"{_format_decimal(actual_duration)} seconds but requires "
                f"{_format_decimal(required_end)} seconds"
            )


def _visual_command(
    manifest: dict[str, object], output_path: Path, target_frames: int, fps_num: int, fps_den: int
) -> list[str]:
    delivery = manifest["delivery"]
    shots = manifest["shots"]
    assert isinstance(delivery, dict) and isinstance(shots, list)
    geometry = delivery["geometry"]
    assert isinstance(geometry, dict)
    width = int(geometry["width"])
    height = int(geometry["height"])
    rate = f"{fps_num}/{fps_den}"
    command = ["ffmpeg", "-v", "error", "-n"]
    filters: list[str] = []
    labels: list[str] = []
    one_frame = Decimal(fps_den) / Decimal(fps_num)
    for index, shot in enumerate(shots):
        assert isinstance(shot, dict)
        timeline = shot["timeline"]
        source = shot["accepted_source"]
        assert isinstance(timeline, dict) and isinstance(source, dict)
        command.extend(["-i", str(source["path"])])
        frame_count = int(timeline["end_frame"]) - int(timeline["start_frame"])
        duration = Decimal(frame_count) * Decimal(fps_den) / Decimal(fps_num)
        label = f"v{index}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{index}:v:0]"
            f"trim=start={source['trim_start_seconds']}:duration={_format_decimal(duration)},"
            "setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,"
            f"fps=fps={rate}:round=near,"
            f"tpad=stop_mode=clone:stop_duration={_format_decimal(one_frame)},"
            f"trim=end_frame={frame_count},setpts=PTS-STARTPTS,format=yuv420p[{label}]"
        )
    filters.append(
        f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0,"
        f"trim=end_frame={target_frames},setpts=PTS-STARTPTS,format=yuv420p[vout]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-an",
            "-frames:v",
            str(target_frames),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-threads:v",
            "1",
            "-fps_mode",
            "cfr",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-movflags",
            "+faststart",
            str(_visual_path(output_path)),
        ]
    )
    return command


def _output_facts(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    probe = _probe(path, count_frames=True)
    return probe, _stream(probe, "video", path), _stream(probe, "audio", path)


def assemble(
    manifest: dict[str, object], project_root: Path, output_path: Path
) -> dict[str, object]:
    """Validate, conform, and mux one deterministic MP4 without overwriting output."""
    resolved = _validate_and_resolve(manifest, project_root)
    output = Path(output_path)
    if os.path.lexists(output):
        raise AssemblyError(f"Output already exists: {output}")
    visual = _visual_path(output)
    if os.path.lexists(visual):
        raise AssemblyError(f"Visual intermediate already exists: {visual}")
    if not output.parent.exists() or not output.parent.is_dir():
        raise AssemblyError(f"Output directory does not exist: {output.parent}")
    _require_tools()

    target_frames, fps_num, fps_den, master_duration = _target_frames(resolved)
    _check_source_coverage(resolved, fps_num, fps_den)
    master = resolved["master"]
    assert isinstance(master, dict)
    master_path = Path(str(master["path"]))
    master_probe = _probe(master_path)
    master_stream = _stream(master_probe, "audio", master_path)
    master_codec = str(master_stream.get("codec_name"))
    actual_master_duration = _media_duration(master_probe, master_stream, master_path)
    frame_duration = Decimal(fps_den) / Decimal(fps_num)
    duration_tolerance = frame_duration + Decimal("0.020")
    visual_duration = Decimal(target_frames) * Decimal(fps_den) / Decimal(fps_num)
    if actual_master_duration + duration_tolerance < visual_duration:
        raise AssemblyError(
            "Master audio coverage is too short for the final visual duration"
        )

    _run(
        _visual_command(resolved, output, target_frames, fps_num, fps_den),
        "Could not conform accepted visual sources",
    )
    visual_probe = _probe(visual, count_frames=True)
    visual_stream = _stream(visual_probe, "video", visual)
    try:
        visual_frames = int(visual_stream["nb_read_frames"])
    except (KeyError, TypeError, ValueError) as error:
        raise AssemblyError("Could not count conformed visual frames") from error
    if visual_frames != target_frames:
        raise AssemblyError(
            f"Conformed visual has {visual_frames} frames, expected {target_frames}"
        )

    audio_mode = "copy" if master_codec in MP4_COPY_AUDIO_CODECS else "encode_aac_320k"
    _run(build_ffmpeg_command(resolved, output), "Could not mux supplied master audio")
    final_probe, final_video, final_audio = _output_facts(output)
    try:
        final_frames = int(final_video["nb_read_frames"])
    except (KeyError, TypeError, ValueError) as error:
        raise AssemblyError("Could not count final delivery frames") from error
    if final_frames != target_frames:
        raise AssemblyError(f"Final delivery has {final_frames} frames, expected {target_frames}")

    delivery = resolved["delivery"]
    assert isinstance(delivery, dict)
    geometry = delivery["geometry"]
    assert isinstance(geometry, dict)
    format_record = final_probe.get("format")
    duration_value = format_record.get("duration") if isinstance(format_record, dict) else None
    duration = _decimal(duration_value, "final duration")
    tolerance = duration_tolerance
    if abs(duration - actual_master_duration) > tolerance:
        raise AssemblyError(
            f"Final duration differs from the master by more than {_format_decimal(tolerance)} seconds"
        )
    start_time = _decimal(final_audio.get("start_time", "0"), "audio start time")
    if abs(start_time) > Decimal("0.001"):
        raise AssemblyError("Supplied master audio does not begin at timeline zero")
    if final_video.get("codec_name") != "h264" or final_video.get("pix_fmt") != "yuv420p":
        raise AssemblyError("Final video is not deterministic H.264 yuv420p delivery")
    if (int(final_video.get("width", 0)), int(final_video.get("height", 0))) != (
        int(geometry["width"]),
        int(geometry["height"]),
    ):
        raise AssemblyError("Final video geometry differs from delivery geometry")

    return {
        "output_path": str(output.resolve()),
        "visual_intermediate_path": str(visual.resolve()),
        "frame_count": final_frames,
        "duration_seconds": float(duration),
        "geometry": {"width": int(geometry["width"]), "height": int(geometry["height"])},
        "frame_rate": {"fps_num": fps_num, "fps_den": fps_den},
        "master_audio_codec": master_codec,
        "output_audio_codec": final_audio.get("codec_name"),
        "audio_mode": audio_mode,
        "audio_start_seconds": float(start_time),
    }


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble accepted visuals and mux the supplied master into MP4."
    )
    parser.add_argument("manifest", type=Path, help="Canonical manifest JSON")
    parser.add_argument("output", type=Path, help="New MP4 output path")
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Root beneath which all manifest media must resolve, defaults to the manifest directory",
    )
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_arguments(arguments)
    try:
        manifest = load_manifest(args.manifest)
        project_root = args.project_root or args.manifest.resolve().parent
        result = assemble(manifest, project_root, args.output)
    except (ManifestJsonError, AssemblyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
