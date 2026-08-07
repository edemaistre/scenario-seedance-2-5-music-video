"""Strict validator for the canonical Scenario Seedance 2.5 project manifest.

The manifest has one exact shape. It records the Task 2 master facts under
``master`` and makes all edit coverage frame based:

* ``delivery.frame_rate`` holds positive integer ``fps_num`` and ``fps_den``.
* each shot has an exclusive integer ``timeline.start_frame`` and
  ``timeline.end_frame``.
* target coverage is ``ceil(master.duration_seconds * fps_num / fps_den)``.
* only ``source.trim_start_seconds`` and ``source.trim_end_seconds`` are
  Decimal strings, formatted to millisecond precision.

Tasks 4 and 5 consume the validated ``master``, ``delivery``, and ordered
``shots`` fields without reconstructing a floating-point edit timeline.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MODEL_ID = "model_bytedance-seedance-2-5"
SEEDANCE_MODES = frozenset({"reference", "first_frame", "first_last_frame", "edit", "extend", "auto"})
FIXED_DURATIONS = range(4, 31)
RESOLUTION_GEOMETRY = {"480p": (854, 480), "720p": (1280, 720)}
ASPECT_RATIOS = frozenset({"16:9", "9:16", "1:1"})
DECIMAL_MILLISECONDS = Decimal("0.001")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL_STRING = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{3}\Z")
SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SAFE_TEXT = re.compile(r"[^\x00-\x1f\x7f]+\Z")


class ManifestJsonError(ValueError):
    """Raised when a manifest is unreadable, ambiguous, or not a JSON object."""


@dataclass(frozen=True, order=True)
class Diagnostic:
    """A deterministic, control-character-safe validation result."""

    code: str
    path: str
    severity: str
    message: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestJsonError("Manifest JSON contains a duplicate object key.")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ManifestJsonError("Manifest JSON contains a nonfinite number.")


def load_manifest(path: Path) -> dict[str, object]:
    """Read one strict JSON object, rejecting duplicates and nonfinite numbers."""
    manifest_path = Path(path)
    try:
        rendered = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ManifestJsonError("Manifest JSON could not be read.") from error
    try:
        data = json.loads(
            rendered,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (json.JSONDecodeError, ManifestJsonError) as error:
        if isinstance(error, ManifestJsonError):
            raise
        raise ManifestJsonError("Manifest JSON is invalid.") from error
    if not isinstance(data, dict):
        raise ManifestJsonError("Manifest JSON root must be an object.")
    return data


def _diagnostic(code: str, path: str, message: str) -> Diagnostic:
    return Diagnostic(code=code, path=path, severity="error", message=message)


def _safe_path(value: object) -> bool:
    if not isinstance(value, str) or not value or not SAFE_TEXT.fullmatch(value):
        return False
    candidate = Path(value)
    return not candidate.is_absolute() and ".." not in candidate.parts and candidate.parts != (".",)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _decimal_number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _decimal_trim(value: object) -> Decimal | None:
    if not isinstance(value, str) or DECIMAL_STRING.fullmatch(value) is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _keys_are_exact(
    diagnostics: list[Diagnostic],
    value: object,
    required: set[str],
    path: str,
    code: str,
) -> bool:
    if not isinstance(value, dict) or set(value) != required:
        diagnostics.append(_diagnostic(code, path, "Object keys do not match the canonical manifest contract."))
        return False
    return True


def _validate_geometry(
    diagnostics: list[Diagnostic],
    geometry: object,
    aspect_ratio: object,
    resolution: object,
    path: str,
    prefix: str,
) -> tuple[int, int] | None:
    if not _keys_are_exact(diagnostics, geometry, {"width", "height"}, f"{path}.geometry", f"{prefix}.geometry"):
        return None
    assert isinstance(geometry, dict)
    width = geometry["width"]
    height = geometry["height"]
    if not _is_positive_int(width) or not _is_positive_int(height):
        diagnostics.append(_diagnostic(f"{prefix}.geometry", f"{path}.geometry", "Geometry dimensions must be positive integers."))
        return None
    if aspect_ratio not in ASPECT_RATIOS:
        diagnostics.append(_diagnostic(f"{prefix}.aspect_ratio", f"{path}.aspect_ratio", "Aspect ratio is unsupported."))
    else:
        left, right = (int(part) for part in str(aspect_ratio).split(":"))
        if Decimal(width) * right != Decimal(height) * left:
            diagnostics.append(_diagnostic(f"{prefix}.geometry", f"{path}.geometry", "Geometry does not match the declared aspect ratio."))
    if resolution not in RESOLUTION_GEOMETRY:
        diagnostics.append(_diagnostic(f"{prefix}.resolution", f"{path}.resolution", "Resolution is unsupported."))
    elif (width, height) != RESOLUTION_GEOMETRY[resolution]:
        diagnostics.append(_diagnostic(f"{prefix}.geometry", f"{path}.geometry", "Geometry does not match the declared resolution."))
    return (width, height)


def _validate_frame_rate(
    diagnostics: list[Diagnostic], value: object, path: str, prefix: str
) -> tuple[int, int] | None:
    if not _keys_are_exact(diagnostics, value, {"fps_num", "fps_den"}, path, f"{prefix}.frame_rate"):
        return None
    assert isinstance(value, dict)
    numerator = value["fps_num"]
    denominator = value["fps_den"]
    if not _is_positive_int(numerator) or not _is_positive_int(denominator):
        diagnostics.append(_diagnostic(f"{prefix}.frame_rate", path, "Frame rate parts must be positive integers."))
        return None
    return numerator, denominator


def _validate_delivery(diagnostics: list[Diagnostic], delivery: object) -> tuple[tuple[int, int], str, tuple[int, int], str] | None:
    if not _keys_are_exact(
        diagnostics,
        delivery,
        {"container", "geometry", "aspect_ratio", "frame_rate", "resolution"},
        "delivery",
        "delivery.keys",
    ):
        return None
    assert isinstance(delivery, dict)
    if delivery["container"] != "mp4":
        diagnostics.append(_diagnostic("delivery.container", "delivery.container", "Delivery container must be mp4."))
    geometry = _validate_geometry(
        diagnostics, delivery["geometry"], delivery["aspect_ratio"], delivery["resolution"], "delivery", "delivery"
    )
    frame_rate = _validate_frame_rate(diagnostics, delivery["frame_rate"], "delivery.frame_rate", "delivery")
    if geometry is None or frame_rate is None or delivery["aspect_ratio"] not in ASPECT_RATIOS or delivery["resolution"] not in RESOLUTION_GEOMETRY:
        return None
    return geometry, delivery["aspect_ratio"], frame_rate, delivery["resolution"]


def _validate_reference_pack(diagnostics: list[Diagnostic], value: object) -> None:
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("reference_pack.keys", "reference_pack", "Reference pack must be an object."))
        return
    source = value.get("source")
    if source == "supplied":
        expected = {"source", "assets"}
    elif source == "generated":
        expected = {"source", "approval", "assets"}
        if value.get("approval") != "approved":
            diagnostics.append(_diagnostic("reference_pack.approval", "reference_pack.approval", "Generated reference packs require explicit approval."))
    else:
        diagnostics.append(_diagnostic("reference_pack.source", "reference_pack.source", "Reference pack source must be supplied or generated."))
        return
    if set(value) != expected:
        diagnostics.append(_diagnostic("reference_pack.keys", "reference_pack", "Reference-pack keys do not match its source contract."))
        return
    assets = value["assets"]
    if not isinstance(assets, list) or not assets:
        diagnostics.append(_diagnostic("reference_pack.assets", "reference_pack.assets", "Reference pack must contain at least one asset."))
        return
    for index, asset in enumerate(assets):
        asset_path = f"reference_pack.assets[{index}]"
        if not _keys_are_exact(diagnostics, asset, {"id", "path", "roles"}, asset_path, "reference_pack.asset.keys"):
            continue
        assert isinstance(asset, dict)
        if not isinstance(asset["id"], str) or SAFE_IDENTIFIER.fullmatch(asset["id"]) is None:
            diagnostics.append(_diagnostic("reference_pack.asset.id", f"{asset_path}.id", "Reference asset ID is invalid."))
        if not _safe_path(asset["path"]):
            diagnostics.append(_diagnostic("reference_pack.asset.path", f"{asset_path}.path", "Reference asset path must be a safe relative path."))
        if not isinstance(asset["roles"], list) or not asset["roles"] or not all(isinstance(role, str) and SAFE_TEXT.fullmatch(role) for role in asset["roles"]):
            diagnostics.append(_diagnostic("reference_pack.asset.roles", f"{asset_path}.roles", "Reference asset roles must be a nonempty array of safe strings."))


def _validate_lyrics(diagnostics: list[Diagnostic], value: object) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("state"), str):
        diagnostics.append(_diagnostic("lyrics.keys", "lyrics", "Lyrics record must be an object with a state."))
        return
    state = value["state"]
    expected: set[str]
    if state == "provided":
        expected = {"state", "certainty", "source_path", "sha256"}
        if value.get("certainty") != "certain":
            diagnostics.append(_diagnostic("lyrics.certainty", "lyrics.certainty", "Provided lyrics must be marked certain."))
        if not _safe_path(value.get("source_path")):
            diagnostics.append(_diagnostic("lyrics.source_path", "lyrics.source_path", "Provided lyric source must use a safe relative path."))
        if not isinstance(value.get("sha256"), str) or SHA256.fullmatch(value["sha256"]) is None:
            diagnostics.append(_diagnostic("lyrics.sha256", "lyrics.sha256", "Provided lyrics require a SHA-256 digest."))
    elif state == "scenario_transcription":
        expected = {"state", "certainty", "transcript_path"}
        if value.get("certainty") != "uncertain":
            diagnostics.append(_diagnostic("lyrics.certainty", "lyrics.certainty", "Scenario transcription must remain explicitly uncertain."))
        if not _safe_path(value.get("transcript_path")):
            diagnostics.append(_diagnostic("lyrics.transcript_path", "lyrics.transcript_path", "Transcript path must be a safe relative path."))
    elif state == "instrumental":
        expected = {"state"}
    elif state == "uncertain":
        expected = {"state", "reason"}
        if not isinstance(value.get("reason"), str) or SAFE_TEXT.fullmatch(value["reason"]) is None:
            diagnostics.append(_diagnostic("lyrics.reason", "lyrics.reason", "Uncertain lyrics require a safe explanation."))
    else:
        diagnostics.append(_diagnostic("lyrics.state", "lyrics.state", "Lyrics state is unsupported."))
        return
    if set(value) != expected:
        diagnostics.append(_diagnostic("lyrics.keys", "lyrics", "Lyrics keys do not match the declared state."))


def _validate_master(diagnostics: list[Diagnostic], value: object) -> Decimal | None:
    if not _keys_are_exact(
        diagnostics,
        value,
        {"path", "sha256", "duration_seconds", "sample_rate", "channels"},
        "master",
        "master.keys",
    ):
        return None
    assert isinstance(value, dict)
    if not _safe_path(value["path"]):
        diagnostics.append(_diagnostic("master.path", "master.path", "Master path must be a safe relative path."))
    if not isinstance(value["sha256"], str) or SHA256.fullmatch(value["sha256"]) is None:
        diagnostics.append(_diagnostic("master.sha256", "master.sha256", "Master SHA-256 digest is invalid."))
    duration = _decimal_number(value["duration_seconds"])
    if duration is None or duration < Decimal("30"):
        diagnostics.append(_diagnostic("master.duration.minimum", "master.duration_seconds", "Measured master duration must be at least 30 seconds."))
        duration = None
    if not _is_positive_int(value["sample_rate"]):
        diagnostics.append(_diagnostic("master.sample_rate", "master.sample_rate", "Master sample rate must be a positive integer."))
    if not _is_positive_int(value["channels"]):
        diagnostics.append(_diagnostic("master.channels", "master.channels", "Master channels must be a positive integer."))
    return duration


def _validate_shot(
    diagnostics: list[Diagnostic],
    value: object,
    index: int,
    delivery: tuple[tuple[int, int], str, tuple[int, int], str] | None,
) -> tuple[int, int] | None:
    path = f"shots[{index}]"
    if not _keys_are_exact(
        diagnostics, value, {"id", "timeline", "source", "expected_output", "generation"}, path, "shot.keys"
    ):
        return None
    assert isinstance(value, dict)
    if not isinstance(value["id"], str) or SAFE_IDENTIFIER.fullmatch(value["id"]) is None:
        diagnostics.append(_diagnostic("shots.id", f"{path}.id", "Shot ID is invalid."))
    timeline = value["timeline"]
    frame_range: tuple[int, int] | None = None
    if not _keys_are_exact(diagnostics, timeline, {"start_frame", "end_frame"}, f"{path}.timeline", "timeline.keys"):
        pass
    else:
        assert isinstance(timeline, dict)
        start = timeline["start_frame"]
        end = timeline["end_frame"]
        if not isinstance(start, int) or isinstance(start, bool) or start < 0 or not _is_positive_int(end) or end <= start:
            diagnostics.append(_diagnostic("timeline.range", f"{path}.timeline", "Timeline frames must be nonnegative exclusive integers with end after start."))
        else:
            frame_range = start, end

    source = value["source"]
    source_span: Decimal | None = None
    if not _keys_are_exact(diagnostics, source, {"path", "trim_start_seconds", "trim_end_seconds"}, f"{path}.source", "source.keys"):
        pass
    else:
        assert isinstance(source, dict)
        if not _safe_path(source["path"]):
            diagnostics.append(_diagnostic("source.path", f"{path}.source.path", "Source path must be a safe relative path."))
        trim_start = _decimal_trim(source["trim_start_seconds"])
        trim_end = _decimal_trim(source["trim_end_seconds"])
        if trim_start is None or trim_end is None or trim_end <= trim_start:
            diagnostics.append(_diagnostic("source.trim.range", f"{path}.source", "Source trim must use increasing Decimal millisecond strings."))
        else:
            source_span = trim_end - trim_start

    expected_output = value["expected_output"]
    output_contract: tuple[tuple[int, int], str, tuple[int, int], str] | None = None
    if _keys_are_exact(
        diagnostics,
        expected_output,
        {"geometry", "aspect_ratio", "frame_rate", "resolution"},
        f"{path}.expected_output",
        "expected_output.keys",
    ):
        assert isinstance(expected_output, dict)
        geometry = _validate_geometry(
            diagnostics,
            expected_output["geometry"],
            expected_output["aspect_ratio"],
            expected_output["resolution"],
            f"{path}.expected_output",
            "expected_output",
        )
        frame_rate = _validate_frame_rate(
            diagnostics, expected_output["frame_rate"], f"{path}.expected_output.frame_rate", "expected_output"
        )
        if geometry is not None and frame_rate is not None and expected_output["aspect_ratio"] in ASPECT_RATIOS and expected_output["resolution"] in RESOLUTION_GEOMETRY:
            output_contract = geometry, expected_output["aspect_ratio"], frame_rate, expected_output["resolution"]
            if delivery is not None and output_contract != delivery:
                geometry_match = output_contract[0] == delivery[0]
                ratio_match = output_contract[1] == delivery[1]
                rate_match = output_contract[2] == delivery[2]
                resolution_match = output_contract[3] == delivery[3]
                if not geometry_match:
                    diagnostics.append(_diagnostic("expected_output.geometry", f"{path}.expected_output.geometry", "Shot geometry differs from delivery geometry."))
                if not ratio_match:
                    diagnostics.append(_diagnostic("expected_output.aspect_ratio", f"{path}.expected_output.aspect_ratio", "Shot aspect ratio differs from delivery aspect ratio."))
                if not rate_match:
                    diagnostics.append(_diagnostic("expected_output.frame_rate", f"{path}.expected_output.frame_rate", "Shot frame rate differs from delivery frame rate."))
                if not resolution_match:
                    diagnostics.append(_diagnostic("expected_output.resolution", f"{path}.expected_output.resolution", "Shot resolution differs from delivery resolution."))
        if delivery is not None:
            declared_geometry = expected_output["geometry"]
            if not isinstance(declared_geometry, dict) or (
                declared_geometry.get("width"), declared_geometry.get("height")
            ) != delivery[0]:
                diagnostics.append(_diagnostic("expected_output.geometry", f"{path}.expected_output.geometry", "Shot geometry differs from delivery geometry."))
            if expected_output["aspect_ratio"] != delivery[1]:
                diagnostics.append(_diagnostic("expected_output.aspect_ratio", f"{path}.expected_output.aspect_ratio", "Shot aspect ratio differs from delivery aspect ratio."))
            declared_rate = expected_output["frame_rate"]
            if not isinstance(declared_rate, dict) or (
                declared_rate.get("fps_num"), declared_rate.get("fps_den")
            ) != delivery[2]:
                diagnostics.append(_diagnostic("expected_output.frame_rate", f"{path}.expected_output.frame_rate", "Shot frame rate differs from delivery frame rate."))
            if expected_output["resolution"] != delivery[3]:
                diagnostics.append(_diagnostic("expected_output.resolution", f"{path}.expected_output.resolution", "Shot resolution differs from delivery resolution."))

    parameters: dict[str, object] | None = _validate_generation(diagnostics, value["generation"], path, delivery)
    if frame_range is not None and source_span is not None and delivery is not None:
        fps_num, fps_den = delivery[2]
        required_span = (Decimal(frame_range[1] - frame_range[0]) * Decimal(fps_den) / Decimal(fps_num)).quantize(DECIMAL_MILLISECONDS, rounding=ROUND_CEILING)
        if source_span < required_span:
            diagnostics.append(_diagnostic("source.trim.coverage", f"{path}.source", "Source trim does not cover the planned edit frames."))
        if parameters is not None and isinstance(parameters.get("duration"), int) and parameters["duration"] < required_span:
            diagnostics.append(_diagnostic("generation.parameters.duration.coverage", f"{path}.generation.parameters.duration", "Seedance duration cannot cover the planned edit frames."))
    return frame_range


def _validate_generation(
    diagnostics: list[Diagnostic], value: object, shot_path: str, delivery: tuple[tuple[int, int], str, tuple[int, int], str] | None
) -> dict[str, object] | None:
    path = f"{shot_path}.generation"
    if not _keys_are_exact(diagnostics, value, {"model_id", "mode", "tags", "parameters"}, path, "generation.keys"):
        return None
    assert isinstance(value, dict)
    if value["model_id"] != MODEL_ID:
        diagnostics.append(_diagnostic("generation.model_id", f"{path}.model_id", "Generation must use the dated Seedance model ID."))
    mode = value["mode"]
    if mode not in SEEDANCE_MODES:
        diagnostics.append(_diagnostic("generation.mode", f"{path}.mode", "Generation mode is unsupported."))
    tags = value["tags"]
    if not isinstance(tags, list) or not all(isinstance(tag, str) and SAFE_TEXT.fullmatch(tag) for tag in tags):
        diagnostics.append(_diagnostic("generation.tags.array", f"{path}.tags", "Generation tags must remain an array of safe strings."))
    parameters = value["parameters"]
    expected_keys = {"prompt", "negativePrompt", "duration", "resolution", "format", "aspectRatio", "generateAudio", "referenceImages", "referenceAudio"}
    if not _keys_are_exact(diagnostics, parameters, expected_keys, f"{path}.parameters", "generation.parameters.keys"):
        return None
    assert isinstance(parameters, dict)
    if not isinstance(parameters["prompt"], str) or SAFE_TEXT.fullmatch(parameters["prompt"]) is None:
        diagnostics.append(_diagnostic("generation.parameters.prompt", f"{path}.parameters.prompt", "Prompt must be safe text."))
    if not isinstance(parameters["negativePrompt"], str) or SAFE_TEXT.fullmatch(parameters["negativePrompt"]) is None:
        diagnostics.append(_diagnostic("generation.parameters.negative_prompt", f"{path}.parameters.negativePrompt", "Negative prompt must be safe text."))
    duration = parameters["duration"]
    if mode == "auto":
        if duration != "Auto":
            diagnostics.append(_diagnostic("generation.parameters.duration", f"{path}.parameters.duration", "Auto mode requires the documented Auto duration."))
    elif not isinstance(duration, int) or isinstance(duration, bool) or duration not in FIXED_DURATIONS:
        diagnostics.append(_diagnostic("generation.parameters.duration", f"{path}.parameters.duration", "Fixed Seedance duration must be an integer from 4 through 30 seconds."))
    if delivery is not None:
        _, aspect_ratio, _, resolution = delivery
        if parameters["resolution"] != resolution:
            diagnostics.append(_diagnostic("generation.parameters.resolution", f"{path}.parameters.resolution", "Generation resolution must match delivery resolution."))
        if parameters["aspectRatio"] != aspect_ratio:
            diagnostics.append(_diagnostic("generation.parameters.aspect_ratio", f"{path}.parameters.aspectRatio", "Generation aspect ratio must match delivery aspect ratio."))
    if parameters["format"] != "mp4":
        diagnostics.append(_diagnostic("generation.parameters.format", f"{path}.parameters.format", "Generation format must be mp4."))
    if type(parameters["generateAudio"]) is not bool or parameters["generateAudio"] is not False:
        diagnostics.append(_diagnostic("generation.parameters.generate_audio", f"{path}.parameters.generateAudio", "Every music-video generation must set generateAudio to false."))
    for parameter_name, code in (("referenceImages", "reference_images"), ("referenceAudio", "reference_audio")):
        references = parameters[parameter_name]
        if not isinstance(references, list):
            diagnostics.append(_diagnostic(f"generation.parameters.{code}.array", f"{path}.parameters.{parameter_name}", "Scenario reference inputs must remain arrays."))
        elif not references or not all(_safe_path(item) for item in references):
            diagnostics.append(_diagnostic(f"generation.parameters.{code}", f"{path}.parameters.{parameter_name}", "Scenario reference inputs must contain safe relative paths."))
    return parameters


def validate_manifest(data: dict[str, object]) -> list[Diagnostic]:
    """Return deterministic diagnostics for a manifest without reading its media files."""
    diagnostics: list[Diagnostic] = []
    if not isinstance(data, dict):
        return [_diagnostic("manifest.root", "manifest", "Manifest root must be an object.")]
    expected_top_level = {"schema_version", "master", "delivery", "reference_pack", "lyrics", "shots"}
    if set(data) != expected_top_level:
        diagnostics.append(_diagnostic("manifest.keys", "manifest", "Manifest keys do not match the canonical contract."))
    if data.get("schema_version") != SCHEMA_VERSION:
        diagnostics.append(_diagnostic("schema_version", "schema_version", "Schema version is unsupported."))
    master_duration = _validate_master(diagnostics, data.get("master"))
    delivery = _validate_delivery(diagnostics, data.get("delivery"))
    _validate_reference_pack(diagnostics, data.get("reference_pack"))
    _validate_lyrics(diagnostics, data.get("lyrics"))

    shots = data.get("shots")
    planned_ranges: list[tuple[int, int, int]] = []
    shot_ids: set[str] = set()
    if not isinstance(shots, list) or not shots:
        diagnostics.append(_diagnostic("shots.array", "shots", "Manifest must contain a nonempty shot array."))
    else:
        for index, shot in enumerate(shots):
            if isinstance(shot, dict) and isinstance(shot.get("id"), str):
                shot_id = shot["id"]
                if shot_id in shot_ids:
                    diagnostics.append(_diagnostic("shots.id.duplicate", f"shots[{index}].id", "Shot IDs must be unique."))
                shot_ids.add(shot_id)
            frame_range = _validate_shot(diagnostics, shot, index, delivery)
            if frame_range is not None:
                planned_ranges.append((frame_range[0], frame_range[1], index))

    if delivery is not None and master_duration is not None and planned_ranges:
        _, _, (fps_num, fps_den), _ = delivery
        target = int((master_duration * Decimal(fps_num) / Decimal(fps_den)).to_integral_value(rounding=ROUND_CEILING))
        expected_start = 0
        for start, end, index in sorted(planned_ranges):
            if start > expected_start:
                diagnostics.append(_diagnostic("timeline.gap", f"shots[{index}].timeline.start_frame", "Shot timeline has a gap."))
            elif start < expected_start:
                diagnostics.append(_diagnostic("timeline.overlap", f"shots[{index}].timeline.start_frame", "Shot timeline has an unintended overlap."))
            expected_start = max(expected_start, end)
        if expected_start != target:
            diagnostics.append(_diagnostic("timeline.final_coverage", "shots", "Shot timeline does not end at the required target frame."))
    return sorted(diagnostics)


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a strict Scenario music-video project manifest.")
    parser.add_argument("manifest", type=Path, help="Path to the project manifest JSON")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_arguments(arguments)
    try:
        manifest = load_manifest(args.manifest)
    except ManifestJsonError as error:
        print(str(error), file=sys.stderr)
        return 2
    diagnostics = validate_manifest(manifest)
    for diagnostic in diagnostics:
        print(f"{diagnostic.severity} {diagnostic.code} {diagnostic.path}: {diagnostic.message}", file=sys.stderr)
    return 1 if any(diagnostic.severity == "error" for diagnostic in diagnostics) else 0


if __name__ == "__main__":
    raise SystemExit(main())
