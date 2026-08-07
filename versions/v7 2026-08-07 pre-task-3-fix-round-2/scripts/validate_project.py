"""Strict validator for the canonical Scenario Seedance 2.5 project manifest.

The manifest has one exact shape. It records the Task 2 master facts under
``master`` and makes all edit coverage frame based:

* ``master.decoded_duration_seconds`` records measured decoded PCM duration.
* ``delivery.frame_rate`` holds positive integer ``fps_num`` and ``fps_den``.
* each shot has an exclusive integer ``timeline.start_frame`` and
  ``timeline.end_frame``.
* target coverage is ``ceil(master.duration_seconds * fps_num / fps_den)``.
* optional accepted-source trims are Decimal strings at millisecond precision.

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
SEEDANCE_MODES = frozenset({"text", "reference", "first_frame", "first_last_frame", "edit", "extend"})
FIXED_DURATIONS = range(4, 31)
RESOLUTION_GEOMETRY = {
    "480p": {
        "21:9": (1120, 480),
        "16:9": (854, 480),
        "4:3": (640, 480),
        "1:1": (480, 480),
        "3:4": (480, 640),
        "9:16": (480, 854),
    },
    "720p": {
        "21:9": (1680, 720),
        "16:9": (1280, 720),
        "4:3": (960, 720),
        "1:1": (720, 720),
        "3:4": (720, 960),
        "9:16": (720, 1280),
    },
}
ASPECT_RATIOS = frozenset({"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"})
KNOWN_PARAMETERS = frozenset(
    {
        "prompt",
        "image",
        "lastFrameImage",
        "referenceImages",
        "referenceVideos",
        "referenceAudio",
        "duration",
        "resolution",
        "aspectRatio",
        "generateAudio",
        "outputFormat",
    }
)
REFERENCE_LIMITS = {"referenceImages": 30, "referenceVideos": 10, "referenceAudio": 10}
DECIMAL_MILLISECONDS = Decimal("0.001")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL_STRING = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{3}\Z")
SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SAFE_TEXT = re.compile(r"[^\x00-\x1f\x7f]+\Z")
ASSET_ID = re.compile(r"asset_[A-Za-z0-9_-]+\Z")
REFERENCE_TAG = re.compile(r"@(image|video|audio)([A-Za-z0-9_-]*)")
POSITIVE_REFERENCE_INDEX = re.compile(r"[1-9][0-9]*\Z")


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
            parse_float=Decimal,
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
    if (
        not isinstance(value, str)
        or not value
        or not SAFE_TEXT.fullmatch(value)
        or "\\" in value
        or "://" in value
        or re.match(r"^[A-Za-z]:", value) is not None
    ):
        return False
    candidate = Path(value)
    return not candidate.is_absolute() and ".." not in candidate.parts and candidate.parts != (".",)


def _is_asset_id(value: object) -> bool:
    return isinstance(value, str) and ASSET_ID.fullmatch(value) is not None


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _decimal_number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
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
    valid_aspect_ratio = isinstance(aspect_ratio, str) and aspect_ratio in ASPECT_RATIOS
    valid_resolution = isinstance(resolution, str) and resolution in RESOLUTION_GEOMETRY
    if not valid_aspect_ratio:
        diagnostics.append(_diagnostic(f"{prefix}.aspect_ratio", f"{path}.aspect_ratio", "Aspect ratio is unsupported."))
    if not valid_resolution:
        diagnostics.append(_diagnostic(f"{prefix}.resolution", f"{path}.resolution", "Resolution is unsupported."))
    elif valid_aspect_ratio and (width, height) != RESOLUTION_GEOMETRY[resolution][aspect_ratio]:
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


def _validate_audio_policy(diagnostics: list[Diagnostic], value: object) -> None:
    path = "delivery.audio_policy"
    if not _keys_are_exact(
        diagnostics,
        value,
        {"source", "start_seconds", "clip_audio", "codec_policy"},
        path,
        "delivery.audio_policy.keys",
    ):
        return
    assert isinstance(value, dict)
    expected_values = {
        "source": ("supplied_master", "Delivery audio must use only the supplied master."),
        "start_seconds": ("0.000", "The supplied master must begin at zero."),
        "clip_audio": ("discard", "Generated clip audio must be discarded."),
        "codec_policy": (
            "copy_compatible_else_aac_320k",
            "Audio must be stream-copied when compatible or encoded once as AAC 320 kbps.",
        ),
    }
    for field, (expected, message) in expected_values.items():
        if value[field] != expected:
            diagnostics.append(_diagnostic(f"delivery.audio_policy.{field}", f"{path}.{field}", message))


def _validate_delivery(diagnostics: list[Diagnostic], delivery: object) -> tuple[tuple[int, int], str, tuple[int, int], str] | None:
    if not _keys_are_exact(
        diagnostics,
        delivery,
        {"container", "geometry", "aspect_ratio", "frame_rate", "resolution", "audio_policy"},
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
    _validate_audio_policy(diagnostics, delivery["audio_policy"])
    if (
        geometry is None
        or frame_rate is None
        or not isinstance(delivery["aspect_ratio"], str)
        or delivery["aspect_ratio"] not in ASPECT_RATIOS
        or not isinstance(delivery["resolution"], str)
        or delivery["resolution"] not in RESOLUTION_GEOMETRY
    ):
        return None
    return geometry, delivery["aspect_ratio"], frame_rate, delivery["resolution"]


def _validate_reference_pack(diagnostics: list[Diagnostic], value: object) -> set[str]:
    if not isinstance(value, dict):
        diagnostics.append(_diagnostic("reference_pack.keys", "reference_pack", "Reference pack must be an object."))
        return set()
    source = value.get("source")
    approved = True
    if source == "supplied":
        expected = {"source", "assets"}
    elif source == "generated":
        expected = {"source", "approval", "assets"}
        if value.get("approval") != "approved":
            diagnostics.append(_diagnostic("reference_pack.approval", "reference_pack.approval", "Generated reference packs require explicit approval."))
            approved = False
    else:
        diagnostics.append(_diagnostic("reference_pack.source", "reference_pack.source", "Reference pack source must be supplied or generated."))
        return set()
    if set(value) != expected:
        diagnostics.append(_diagnostic("reference_pack.keys", "reference_pack", "Reference-pack keys do not match its source contract."))
        return set()
    assets = value["assets"]
    if not isinstance(assets, list) or not assets:
        diagnostics.append(_diagnostic("reference_pack.assets", "reference_pack.assets", "Reference pack must contain at least one asset."))
        return set()
    manifest_ids: set[str] = set()
    scenario_ids: set[str] = set()
    for index, asset in enumerate(assets):
        asset_path = f"reference_pack.assets[{index}]"
        if not _keys_are_exact(
            diagnostics,
            asset,
            {"id", "path", "scenario_asset_id", "roles"},
            asset_path,
            "reference_pack.asset.keys",
        ):
            continue
        assert isinstance(asset, dict)
        if not isinstance(asset["id"], str) or SAFE_IDENTIFIER.fullmatch(asset["id"]) is None:
            diagnostics.append(_diagnostic("reference_pack.asset.id", f"{asset_path}.id", "Reference asset ID is invalid."))
        elif asset["id"] in manifest_ids:
            diagnostics.append(_diagnostic("reference_pack.asset.id.duplicate", f"{asset_path}.id", "Reference asset IDs must be unique."))
        else:
            manifest_ids.add(asset["id"])
        if not _safe_path(asset["path"]):
            diagnostics.append(_diagnostic("reference_pack.asset.path", f"{asset_path}.path", "Reference asset path must be a safe relative path."))
        if not _is_asset_id(asset["scenario_asset_id"]):
            diagnostics.append(_diagnostic("reference_pack.asset.scenario_asset_id", f"{asset_path}.scenario_asset_id", "Reference asset must include a Scenario asset ID."))
        elif asset["scenario_asset_id"] in scenario_ids:
            diagnostics.append(_diagnostic("reference_pack.asset.scenario_asset_id.duplicate", f"{asset_path}.scenario_asset_id", "Scenario reference asset IDs must be unique."))
        else:
            scenario_ids.add(asset["scenario_asset_id"])
        if not isinstance(asset["roles"], list) or not asset["roles"] or not all(isinstance(role, str) and SAFE_TEXT.fullmatch(role) for role in asset["roles"]):
            diagnostics.append(_diagnostic("reference_pack.asset.roles", f"{asset_path}.roles", "Reference asset roles must be a nonempty array of safe strings."))
    return scenario_ids if approved else set()


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
        {"path", "sha256", "decoded_duration_seconds", "sample_rate", "channels", "rights"},
        "master",
        "master.keys",
    ):
        return None
    assert isinstance(value, dict)
    if not _safe_path(value["path"]):
        diagnostics.append(_diagnostic("master.path", "master.path", "Master path must be a safe relative path."))
    if not isinstance(value["sha256"], str) or SHA256.fullmatch(value["sha256"]) is None:
        diagnostics.append(_diagnostic("master.sha256", "master.sha256", "Master SHA-256 digest is invalid."))
    duration = _decimal_number(value["decoded_duration_seconds"])
    if duration is None:
        diagnostics.append(_diagnostic("master.duration.type", "master.decoded_duration_seconds", "Measured decoded master duration must be a finite JSON number."))
    elif duration < Decimal("30"):
        diagnostics.append(_diagnostic("master.duration.minimum", "master.decoded_duration_seconds", "Measured decoded master duration must be at least 30 seconds."))
        duration = None
    if not _is_positive_int(value["sample_rate"]):
        diagnostics.append(_diagnostic("master.sample_rate", "master.sample_rate", "Master sample rate must be a positive integer."))
    if not _is_positive_int(value["channels"]):
        diagnostics.append(_diagnostic("master.channels", "master.channels", "Master channels must be a positive integer."))
    rights = value["rights"]
    if _keys_are_exact(diagnostics, rights, {"status", "basis"}, "master.rights", "master.rights.keys"):
        assert isinstance(rights, dict)
        if rights["status"] != "authorized":
            diagnostics.append(_diagnostic("master.rights.status", "master.rights.status", "Master rights must be confirmed as authorized."))
        if not isinstance(rights["basis"], str) or SAFE_TEXT.fullmatch(rights["basis"]) is None:
            diagnostics.append(_diagnostic("master.rights.basis", "master.rights.basis", "Master rights basis must be safe nonempty text."))
    return duration


def _validate_shot(
    diagnostics: list[Diagnostic],
    value: object,
    index: int,
    delivery: tuple[tuple[int, int], str, tuple[int, int], str] | None,
    approved_asset_ids: set[str],
) -> tuple[int, int] | None:
    path = f"shots[{index}]"
    required_keys = {"id", "timeline", "expected_output", "generation"}
    if not isinstance(value, dict) or not required_keys.issubset(value) or set(value) - required_keys != {"accepted_source"} and set(value) != required_keys:
        diagnostics.append(_diagnostic("shot.keys", path, "Shot keys do not match the canonical manifest contract."))
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

    source = value.get("accepted_source")
    source_span: Decimal | None = None
    trim_start: Decimal | None = None
    trim_end: Decimal | None = None
    if source is not None and _keys_are_exact(
        diagnostics,
        source,
        {"path", "trim_start_seconds", "trim_end_seconds"},
        f"{path}.accepted_source",
        "source.keys",
    ):
        assert isinstance(source, dict)
        if not _safe_path(source["path"]):
            diagnostics.append(_diagnostic("source.path", f"{path}.accepted_source.path", "Accepted source path must be a safe relative path."))
        trim_start = _decimal_trim(source["trim_start_seconds"])
        trim_end = _decimal_trim(source["trim_end_seconds"])
        if trim_start is None or trim_end is None or trim_end <= trim_start:
            diagnostics.append(_diagnostic("source.trim.range", f"{path}.accepted_source", "Source trim must use increasing Decimal millisecond strings."))
        else:
            source_span = trim_end - trim_start

    expected_output = value["expected_output"]
    if _keys_are_exact(
        diagnostics,
        expected_output,
        {"geometry", "aspect_ratio", "frame_rate", "resolution"},
        f"{path}.expected_output",
        "expected_output.keys",
    ):
        assert isinstance(expected_output, dict)
        _validate_geometry(
            diagnostics,
            expected_output["geometry"],
            expected_output["aspect_ratio"],
            expected_output["resolution"],
            f"{path}.expected_output",
            "expected_output",
        )
        _validate_frame_rate(
            diagnostics, expected_output["frame_rate"], f"{path}.expected_output.frame_rate", "expected_output"
        )
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

    parameters: dict[str, object] | None = _validate_generation(
        diagnostics,
        value["generation"],
        path,
        delivery,
        approved_asset_ids,
    )
    if frame_range is not None and delivery is not None:
        fps_num, fps_den = delivery[2]
        required_span = (Decimal(frame_range[1] - frame_range[0]) * Decimal(fps_den) / Decimal(fps_num)).quantize(DECIMAL_MILLISECONDS, rounding=ROUND_CEILING)
        if source_span is not None and source_span < required_span:
            diagnostics.append(_diagnostic("source.trim.coverage", f"{path}.accepted_source", "Source trim does not cover the planned edit frames."))
        if parameters is not None and isinstance(parameters.get("duration"), int):
            requested_duration = parameters["duration"]
            generation_capacity = Decimal("30") if requested_duration == -1 else Decimal(requested_duration)
            if generation_capacity < required_span:
                diagnostics.append(_diagnostic("generation.parameters.duration.coverage", f"{path}.generation.parameters.duration", "Seedance duration cannot cover the planned edit frames."))
        if (
            parameters is not None
            and trim_end is not None
            and isinstance(parameters.get("duration"), int)
            and parameters["duration"] >= 0
            and trim_end > Decimal(parameters["duration"])
        ):
            diagnostics.append(_diagnostic("source.trim.generation_range", f"{path}.accepted_source.trim_end_seconds", "Source trim exceeds the requested generated duration."))
    return frame_range


def _validate_generation(
    diagnostics: list[Diagnostic],
    value: object,
    shot_path: str,
    delivery: tuple[tuple[int, int], str, tuple[int, int], str] | None,
    approved_asset_ids: set[str],
) -> dict[str, object] | None:
    path = f"{shot_path}.generation"
    if not _keys_are_exact(diagnostics, value, {"model_id", "mode", "parameters"}, path, "generation.keys"):
        return None
    assert isinstance(value, dict)
    if value["model_id"] != MODEL_ID:
        diagnostics.append(_diagnostic("generation.model_id", f"{path}.model_id", "Generation must use the dated Seedance model ID."))
    mode = value["mode"]
    valid_mode = isinstance(mode, str) and mode in SEEDANCE_MODES
    if not valid_mode:
        diagnostics.append(_diagnostic("generation.mode", f"{path}.mode", "Generation mode is unsupported."))
    parameters = value["parameters"]
    if not isinstance(parameters, dict):
        diagnostics.append(_diagnostic("generation.parameters.keys", f"{path}.parameters", "Generation parameters must be an object."))
        return None
    unknown = sorted(set(parameters) - KNOWN_PARAMETERS)
    if unknown:
        diagnostics.append(_diagnostic("generation.parameters.unknown", f"{path}.parameters", "Generation parameters contain names outside the dated Seedance contract."))
    required = {"prompt", "duration", "resolution", "generateAudio", "outputFormat"}
    if not required.issubset(parameters):
        diagnostics.append(_diagnostic("generation.parameters.missing", f"{path}.parameters", "Generation parameters omit required canonical fields."))

    prompt = parameters.get("prompt")
    if not isinstance(prompt, str) or SAFE_TEXT.fullmatch(prompt) is None or len(prompt) > 6000:
        diagnostics.append(_diagnostic("generation.parameters.prompt", f"{path}.parameters.prompt", "Prompt must be safe text."))
    duration = parameters.get("duration")
    if mode == "edit":
        if type(duration) is not int or duration != -1:
            diagnostics.append(_diagnostic("generation.parameters.duration", f"{path}.parameters.duration", "Edit mode requires duration -1 for Auto."))
    elif (
        not isinstance(duration, int)
        or isinstance(duration, bool)
        or duration != -1 and duration not in FIXED_DURATIONS
    ):
        diagnostics.append(_diagnostic("generation.parameters.duration", f"{path}.parameters.duration", "Seedance duration must be -1 for Auto or an integer from 4 through 30 seconds."))

    if delivery is not None:
        _, aspect_ratio, _, resolution = delivery
        if parameters.get("resolution") != resolution:
            diagnostics.append(_diagnostic("generation.parameters.resolution", f"{path}.parameters.resolution", "Generation resolution must match delivery resolution."))
        if isinstance(mode, str) and mode in {"text", "reference"} and parameters.get("aspectRatio") != aspect_ratio:
            diagnostics.append(_diagnostic("generation.parameters.aspect_ratio", f"{path}.parameters.aspectRatio", "Generation aspect ratio must match delivery aspect ratio."))
        if isinstance(mode, str) and mode in {"first_frame", "first_last_frame", "edit", "extend"} and "aspectRatio" in parameters:
            diagnostics.append(_diagnostic("generation.parameters.aspect_ratio", f"{path}.parameters.aspectRatio", "This mode inherits source geometry and must omit ignored aspectRatio."))
    output_format = parameters.get("outputFormat")
    if not isinstance(output_format, str) or output_format not in {"mp4", "mov"}:
        diagnostics.append(_diagnostic("generation.parameters.output_format", f"{path}.parameters.outputFormat", "Generation outputFormat must be mp4 or mov."))
    if type(parameters.get("generateAudio")) is not bool or parameters.get("generateAudio") is not False:
        diagnostics.append(_diagnostic("generation.parameters.generate_audio", f"{path}.parameters.generateAudio", "Every music-video generation must set generateAudio to false."))

    reference_counts = {"image": 0, "video": 0, "audio": 0}
    reference_types = {"referenceImages": "image", "referenceVideos": "video", "referenceAudio": "audio"}
    for parameter_name, limit in REFERENCE_LIMITS.items():
        if parameter_name not in parameters:
            continue
        references = parameters[parameter_name]
        code = re.sub(r"(?<!^)(?=[A-Z])", "_", parameter_name).lower()
        if not isinstance(references, list):
            diagnostics.append(_diagnostic(f"generation.parameters.{code}.array", f"{path}.parameters.{parameter_name}", "Scenario reference inputs must remain arrays."))
            continue
        reference_counts[reference_types[parameter_name]] = len(references)
        if len(references) > limit:
            diagnostics.append(_diagnostic(f"generation.parameters.{code}.limit", f"{path}.parameters.{parameter_name}", "Scenario reference array exceeds the dated model limit."))
        if not all(_is_asset_id(item) for item in references):
            diagnostics.append(_diagnostic(f"generation.parameters.{code}", f"{path}.parameters.{parameter_name}", "Scenario reference arrays must contain asset IDs."))
        elif any(item not in approved_asset_ids for item in references):
            diagnostics.append(_diagnostic(f"generation.parameters.{code}.unapproved", f"{path}.parameters.{parameter_name}", "Scenario reference asset is not present in the approved reference pack."))
        if len(set(item for item in references if isinstance(item, str))) != len(references):
            diagnostics.append(_diagnostic(f"generation.parameters.{code}.duplicate", f"{path}.parameters.{parameter_name}", "Scenario reference arrays must not contain duplicate asset IDs."))

    for parameter_name in ("image", "lastFrameImage"):
        if parameter_name in parameters and not _is_asset_id(parameters[parameter_name]):
            diagnostics.append(_diagnostic("generation.parameters.asset_id", f"{path}.parameters.{parameter_name}", "Frame inputs must be Scenario asset IDs."))
        elif parameter_name in parameters and parameters[parameter_name] not in approved_asset_ids:
            diagnostics.append(_diagnostic(f"generation.parameters.{parameter_name}.unapproved", f"{path}.parameters.{parameter_name}", "Scenario frame asset is not present in the approved reference pack."))

    has_reference = any(
        isinstance(parameters.get(field), list) and bool(parameters[field]) for field in REFERENCE_LIMITS
    )
    direct_frame_fields = {"image", "lastFrameImage"}.intersection(parameters)
    if mode == "text" and (direct_frame_fields or set(REFERENCE_LIMITS).intersection(parameters)):
        diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "Text mode must not include source media."))
    elif mode == "first_frame":
        if not _is_asset_id(parameters.get("image")) or "lastFrameImage" in parameters:
            diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "First-frame mode requires image and forbids lastFrameImage."))
        if {"referenceImages", "referenceVideos"}.intersection(parameters):
            diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "First-frame mode forbids referenceImages and referenceVideos."))
    elif mode == "first_last_frame":
        if not _is_asset_id(parameters.get("image")) or not _is_asset_id(parameters.get("lastFrameImage")):
            diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "First-and-last-frame mode requires image and lastFrameImage."))
        if {"referenceImages", "referenceVideos"}.intersection(parameters):
            diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "First-and-last-frame mode forbids referenceImages and referenceVideos."))
    elif mode == "reference" and (not has_reference or direct_frame_fields):
        diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "Reference mode requires a nonempty reference array and forbids frame inputs."))
    elif isinstance(mode, str) and mode in {"edit", "extend"}:
        videos = parameters.get("referenceVideos")
        if not isinstance(videos, list) or not videos or direct_frame_fields:
            diagnostics.append(_diagnostic("generation.mode.inputs", f"{path}.parameters", "Edit and extend modes require referenceVideos and forbid frame inputs."))

    if isinstance(mode, str) and mode in {"first_frame", "first_last_frame"} and _is_asset_id(parameters.get("image")):
        reference_counts["image"] = 2 if _is_asset_id(parameters.get("lastFrameImage")) else 1
    if isinstance(prompt, str):
        for tag_type, raw_index in REFERENCE_TAG.findall(prompt):
            if POSITIVE_REFERENCE_INDEX.fullmatch(raw_index) is None:
                diagnostics.append(_diagnostic("generation.parameters.prompt_tag.malformed", f"{path}.parameters.prompt", "Scenario prompt tags must use positive integer indexes."))
                continue
            if int(raw_index) > reference_counts[tag_type]:
                diagnostics.append(_diagnostic("generation.parameters.prompt_tag.unbound", f"{path}.parameters.prompt", "Scenario prompt tag does not resolve to a supplied asset."))
    return parameters


def validate_manifest(data: dict[str, object]) -> list[Diagnostic]:
    """Return deterministic diagnostics for a manifest without reading its media files."""
    diagnostics: list[Diagnostic] = []
    if not isinstance(data, dict):
        return [_diagnostic("manifest.root", "manifest", "Manifest root must be an object.")]
    expected_top_level = {"schema_version", "master", "delivery", "reference_pack", "lyrics", "shots"}
    if set(data) != expected_top_level:
        diagnostics.append(_diagnostic("manifest.keys", "manifest", "Manifest keys do not match the canonical contract."))
    if type(data.get("schema_version")) is not int or data.get("schema_version") != SCHEMA_VERSION:
        diagnostics.append(_diagnostic("schema_version", "schema_version", "Schema version is unsupported."))
    master_duration = _validate_master(diagnostics, data.get("master"))
    delivery = _validate_delivery(diagnostics, data.get("delivery"))
    approved_asset_ids = _validate_reference_pack(diagnostics, data.get("reference_pack"))
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
            frame_range = _validate_shot(diagnostics, shot, index, delivery, approved_asset_ids)
            if frame_range is not None:
                planned_ranges.append((frame_range[0], frame_range[1], index))

    if delivery is not None and master_duration is not None and planned_ranges:
        _, _, (fps_num, fps_den), _ = delivery
        target = int((master_duration * Decimal(fps_num) / Decimal(fps_den)).to_integral_value(rounding=ROUND_CEILING))
        expected_start = 0
        previous_start: int | None = None
        for start, end, index in planned_ranges:
            if previous_start is not None and start < previous_start:
                diagnostics.append(_diagnostic("timeline.order", f"shots[{index}].timeline.start_frame", "Shots must appear in chronological timeline order."))
            if start > expected_start:
                diagnostics.append(_diagnostic("timeline.gap", f"shots[{index}].timeline.start_frame", "Shot timeline has a gap."))
            elif start < expected_start:
                diagnostics.append(_diagnostic("timeline.overlap", f"shots[{index}].timeline.start_frame", "Shot timeline has an unintended overlap."))
            expected_start = max(expected_start, end)
            previous_start = start
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
