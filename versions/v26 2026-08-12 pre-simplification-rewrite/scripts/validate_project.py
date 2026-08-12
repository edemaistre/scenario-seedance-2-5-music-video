"""Strict validator for the canonical Scenario Seedance 2.5 project manifest.

The manifest has one exact shape. It records the Task 2 master facts under
``master`` and makes all edit coverage frame based:

* ``master.decoded_duration_seconds`` records measured decoded PCM duration.
* ``delivery.frame_rate`` holds positive integer ``fps_num`` and ``fps_den``.
* each shot has an exclusive integer ``timeline.start_frame`` and
  ``timeline.end_frame``.
* each shot carries a complete ``planning`` brief and strict ``production``
  disposition with ordered paid-attempt provenance.
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
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
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
REFERENCE_ROLE_TAG = re.compile(r"@(image|video|audio)([1-9][0-9]*)\Z")
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
MIN_JSON_DECIMAL_ADJUSTED_EXPONENT = -324
MAX_JSON_DECIMAL_ADJUSTED_EXPONENT = 308
MAX_JSON_DECIMAL_DIGITS = 1000
MAX_JSON_INTEGER = (1 << 63) - 1


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


def _decimal_is_transport_safe(value: Decimal) -> bool:
    return (
        value.is_finite()
        and MIN_JSON_DECIMAL_ADJUSTED_EXPONENT <= value.adjusted() <= MAX_JSON_DECIMAL_ADJUSTED_EXPONENT
        and len(value.as_tuple().digits) <= MAX_JSON_DECIMAL_DIGITS
    )


def _parse_bounded_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ManifestJsonError("Manifest JSON contains an invalid number.") from error
    if not _decimal_is_transport_safe(parsed):
        raise ManifestJsonError("Manifest JSON number exceeds transport-safe bounds.")
    return parsed


def _parse_bounded_integer(value: str) -> int:
    try:
        parsed = int(value)
    except (ValueError, OverflowError) as error:
        raise ManifestJsonError("Manifest JSON contains an invalid integer.") from error
    if abs(parsed) > MAX_JSON_INTEGER:
        raise ManifestJsonError("Manifest JSON integer exceeds transport-safe bounds.")
    return parsed


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
            parse_float=_parse_bounded_decimal,
            parse_int=_parse_bounded_integer,
        )
    except ManifestJsonError:
        raise
    except (json.JSONDecodeError, ValueError, OverflowError, InvalidOperation) as error:
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
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= MAX_JSON_INTEGER


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_JSON_INTEGER


def _is_safe_nonempty_text(value: object, maximum_length: int = 2000) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= maximum_length
        and SAFE_TEXT.fullmatch(value) is not None
    )


def _decimal_number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if _decimal_is_transport_safe(parsed) else None


def _decimal_trim(value: object) -> Decimal | None:
    if not isinstance(value, str) or DECIMAL_STRING.fullmatch(value) is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if _decimal_is_transport_safe(parsed) else None


def _decimal_precision(*values: Decimal | int) -> int:
    digit_count = 0
    for value in values:
        if isinstance(value, Decimal):
            digit_count += len(value.as_tuple().digits)
        else:
            digit_count += len(str(abs(value)))
    return max(80, digit_count + 16)


def _target_frame_count(duration: Decimal, fps_num: int, fps_den: int) -> int:
    with localcontext() as context:
        context.prec = _decimal_precision(duration, fps_num, fps_den)
        scaled = duration * Decimal(fps_num) / Decimal(fps_den)
        return int(scaled.to_integral_value(rounding=ROUND_CEILING))


def _frame_span_seconds(frame_count: int, fps_num: int, fps_den: int) -> Decimal:
    with localcontext() as context:
        context.prec = _decimal_precision(frame_count, fps_num, fps_den)
        scaled = Decimal(frame_count) * Decimal(fps_den) / Decimal(fps_num)
        return scaled.quantize(DECIMAL_MILLISECONDS, rounding=ROUND_CEILING)


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
    if not isinstance(source, str) or source not in {"supplied", "generated"}:
        diagnostics.append(_diagnostic("reference_pack.source", "reference_pack.source", "Reference pack source must be supplied or generated."))
        return set()
    expected = {"source", "approval", "assets"}
    approved = value.get("approval") == "approved"
    if not approved:
        diagnostics.append(_diagnostic("reference_pack.approval", "reference_pack.approval", "Supplied and generated reference packs require explicit approval."))
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


def _validate_text_array(
    diagnostics: list[Diagnostic], value: object, path: str, code: str, *, allow_empty: bool
) -> bool:
    if (
        not isinstance(value, list)
        or not allow_empty and not value
        or not all(_is_safe_nonempty_text(item, 500) for item in value)
    ):
        diagnostics.append(_diagnostic(code, path, "Value must be an array of safe nonempty strings."))
        return False
    return True


def _generation_reference_map(parameters: dict[str, object] | None) -> dict[str, str]:
    if parameters is None:
        return {}
    references: dict[str, str] = {}
    image = parameters.get("image")
    last_image = parameters.get("lastFrameImage")
    if _is_asset_id(image):
        references["@image1"] = image
        if _is_asset_id(last_image):
            references["@image2"] = last_image
    else:
        images = parameters.get("referenceImages")
        if isinstance(images, list):
            for index, asset_id in enumerate(images, start=1):
                if _is_asset_id(asset_id):
                    references[f"@image{index}"] = asset_id
    videos = parameters.get("referenceVideos")
    if isinstance(videos, list):
        for index, asset_id in enumerate(videos, start=1):
            if _is_asset_id(asset_id):
                references[f"@video{index}"] = asset_id
    audio = parameters.get("referenceAudio")
    if isinstance(audio, list):
        for index, asset_id in enumerate(audio, start=1):
            if _is_asset_id(asset_id):
                references[f"@audio{index}"] = asset_id
    return references


def _validate_planning(
    diagnostics: list[Diagnostic],
    value: object,
    shot_path: str,
    frame_range: tuple[int, int] | None,
    parameters: dict[str, object] | None,
) -> tuple[Decimal, Decimal] | None:
    path = f"{shot_path}.planning"
    expected = {
        "section",
        "music_or_lyric_function",
        "sync_events",
        "information_density",
        "handles",
        "shot_family",
        "subject",
        "action",
        "shot_size",
        "camera_move",
        "lens_or_optics",
        "lighting",
        "palette",
        "realism",
        "texture",
        "film_stock_or_grain",
        "opening_composition",
        "closing_state",
        "screen_direction",
        "motion_vector",
        "transition_logic",
        "continuity",
        "reference_roles",
    }
    if not _keys_are_exact(diagnostics, value, expected, path, "planning.keys"):
        return None
    assert isinstance(value, dict)
    text_fields = expected - {
        "sync_events", "information_density", "handles", "continuity", "reference_roles"
    }
    for field in sorted(text_fields):
        if not _is_safe_nonempty_text(value[field]):
            diagnostics.append(_diagnostic("planning.text", f"{path}.{field}", "Planning text must be safe and nonempty."))

    density = value["information_density"]
    if not isinstance(density, str) or density not in {"low", "medium", "high", "peak"}:
        diagnostics.append(_diagnostic("planning.information_density", f"{path}.information_density", "Information density is unsupported."))

    events = value["sync_events"]
    if not isinstance(events, list):
        diagnostics.append(_diagnostic("planning.sync_events", f"{path}.sync_events", "Sync events must be an array."))
    else:
        for event_index, event in enumerate(events):
            event_path = f"{path}.sync_events[{event_index}]"
            if not _keys_are_exact(
                diagnostics,
                event,
                {"master_frame", "description", "verified"},
                event_path,
                "planning.sync_events.keys",
            ):
                continue
            assert isinstance(event, dict)
            master_frame = event["master_frame"]
            if not _is_nonnegative_int(master_frame) or (
                frame_range is not None and not frame_range[0] <= master_frame < frame_range[1]
            ):
                diagnostics.append(_diagnostic("planning.sync_events.frame", f"{event_path}.master_frame", "Sync event frame must fall within the shot timeline."))
            if not _is_safe_nonempty_text(event["description"], 500):
                diagnostics.append(_diagnostic("planning.sync_events.description", f"{event_path}.description", "Sync event description must be safe and nonempty."))
            if event["verified"] is not True:
                diagnostics.append(_diagnostic("planning.sync_events.verified", f"{event_path}.verified", "Recorded sync events must be verified."))

    handles = value["handles"]
    opening: Decimal | None = None
    closing: Decimal | None = None
    if _keys_are_exact(
        diagnostics,
        handles,
        {"opening_seconds", "closing_seconds"},
        f"{path}.handles",
        "planning.handles.keys",
    ):
        assert isinstance(handles, dict)
        opening = _decimal_trim(handles["opening_seconds"])
        closing = _decimal_trim(handles["closing_seconds"])
        if opening is None or closing is None or opening < 0 or closing < 0:
            diagnostics.append(_diagnostic("planning.handles", f"{path}.handles", "Edit handles must be nonnegative Decimal millisecond strings."))

    continuity = value["continuity"]
    continuity_keys = {"identity", "wardrobe", "product", "props", "world", "state"}
    if _keys_are_exact(
        diagnostics, continuity, continuity_keys, f"{path}.continuity", "planning.continuity.keys"
    ):
        assert isinstance(continuity, dict)
        has_invariant = False
        for field in sorted(continuity_keys):
            if _validate_text_array(
                diagnostics,
                continuity[field],
                f"{path}.continuity.{field}",
                "planning.continuity.values",
                allow_empty=True,
            ):
                has_invariant = has_invariant or bool(continuity[field])
        if not has_invariant:
            diagnostics.append(_diagnostic("planning.continuity.empty", f"{path}.continuity", "Planning must record at least one continuity invariant."))

    expected_references = _generation_reference_map(parameters)
    role_records = value["reference_roles"]
    observed_references: dict[str, str] = {}
    if not isinstance(role_records, list):
        diagnostics.append(_diagnostic("planning.reference_roles", f"{path}.reference_roles", "Reference roles must be an array."))
    else:
        for role_index, role_record in enumerate(role_records):
            role_path = f"{path}.reference_roles[{role_index}]"
            if not _keys_are_exact(
                diagnostics,
                role_record,
                {"tag", "scenario_asset_id", "role", "inherits", "excludes"},
                role_path,
                "planning.reference_roles.keys",
            ):
                continue
            assert isinstance(role_record, dict)
            tag = role_record["tag"]
            asset_id = role_record["scenario_asset_id"]
            if not isinstance(tag, str) or REFERENCE_ROLE_TAG.fullmatch(tag) is None:
                diagnostics.append(_diagnostic("planning.reference_roles.tag", f"{role_path}.tag", "Reference role tag is invalid."))
            elif tag in observed_references:
                diagnostics.append(_diagnostic("planning.reference_roles.tag.duplicate", f"{role_path}.tag", "Reference role tags must be unique."))
            elif _is_asset_id(asset_id):
                observed_references[tag] = asset_id
            if not _is_asset_id(asset_id):
                diagnostics.append(_diagnostic("planning.reference_roles.asset_id", f"{role_path}.scenario_asset_id", "Reference role asset ID is invalid."))
            if not _is_safe_nonempty_text(role_record["role"], 500):
                diagnostics.append(_diagnostic("planning.reference_roles.role", f"{role_path}.role", "Reference role must be safe and nonempty."))
            _validate_text_array(
                diagnostics,
                role_record["inherits"],
                f"{role_path}.inherits",
                "planning.reference_roles.inherits",
                allow_empty=False,
            )
            _validate_text_array(
                diagnostics,
                role_record["excludes"],
                f"{role_path}.excludes",
                "planning.reference_roles.excludes",
                allow_empty=False,
            )
    if parameters is not None and observed_references != expected_references:
        diagnostics.append(_diagnostic("planning.reference_roles.coverage", f"{path}.reference_roles", "Reference roles must exactly map the ordered generation inputs."))
    if opening is None or closing is None:
        return None
    return opening, closing


def _validate_cost_record(
    diagnostics: list[Diagnostic], value: object, path: str, code: str
) -> bool:
    if not _keys_are_exact(diagnostics, value, {"amount", "unit"}, path, f"{code}.keys"):
        return False
    assert isinstance(value, dict)
    amount = _decimal_number(value["amount"])
    if amount is None or amount < 0:
        diagnostics.append(_diagnostic(f"{code}.amount", f"{path}.amount", "Cost amount must be a finite nonnegative JSON number."))
    if not _is_safe_nonempty_text(value["unit"], 40):
        diagnostics.append(_diagnostic(f"{code}.unit", f"{path}.unit", "Cost unit must be safe nonempty text."))
    return amount is not None and amount >= 0 and _is_safe_nonempty_text(value["unit"], 40)


def _validate_production(
    diagnostics: list[Diagnostic], value: object, shot_path: str, has_accepted_source: bool
) -> None:
    path = f"{shot_path}.production"
    if not _keys_are_exact(
        diagnostics, value, {"disposition", "attempts"}, path, "production.keys"
    ):
        return
    assert isinstance(value, dict)
    disposition = value["disposition"]
    dispositions = {"planned", "in_progress", "needs_reroll", "timed_out", "accepted"}
    if not isinstance(disposition, str) or disposition not in dispositions:
        diagnostics.append(_diagnostic("production.disposition", f"{path}.disposition", "Production disposition is unsupported."))

    attempts = value["attempts"]
    if not isinstance(attempts, list):
        diagnostics.append(_diagnostic("production.attempts", f"{path}.attempts", "Production attempts must be an array."))
        return
    attempt_ids: set[str] = set()
    states: list[tuple[str | None, bool, str | None, bool]] = []
    accepted_count = 0
    for attempt_index, attempt in enumerate(attempts):
        attempt_path = f"{path}.attempts[{attempt_index}]"
        expected = {
            "id",
            "schema_checked_on",
            "dry_run_estimate",
            "approval",
            "job_id",
            "output_id",
            "known_cost",
            "acceptance",
            "reroll_diagnosis",
        }
        if not _keys_are_exact(
            diagnostics, attempt, expected, attempt_path, "production.attempt.keys"
        ):
            states.append((None, False, None, False))
            continue
        assert isinstance(attempt, dict)
        attempt_id = attempt["id"]
        if not isinstance(attempt_id, str) or SAFE_IDENTIFIER.fullmatch(attempt_id) is None:
            diagnostics.append(_diagnostic("production.attempt.id", f"{attempt_path}.id", "Production attempt ID is invalid."))
        elif attempt_id in attempt_ids:
            diagnostics.append(_diagnostic("production.attempt.id.duplicate", f"{attempt_path}.id", "Production attempt IDs must be unique within a shot."))
        else:
            attempt_ids.add(attempt_id)
        schema_checked_on = attempt["schema_checked_on"]
        if not isinstance(schema_checked_on, str) or ISO_DATE.fullmatch(schema_checked_on) is None:
            diagnostics.append(_diagnostic("production.attempt.schema_checked_on", f"{attempt_path}.schema_checked_on", "Schema check date must use YYYY-MM-DD."))
        _validate_cost_record(
            diagnostics,
            attempt["dry_run_estimate"],
            f"{attempt_path}.dry_run_estimate",
            "production.attempt.dry_run_estimate",
        )

        approval = attempt["approval"]
        approval_status: str | None = None
        if _keys_are_exact(
            diagnostics,
            approval,
            {"status", "record"},
            f"{attempt_path}.approval",
            "production.attempt.approval.keys",
        ):
            assert isinstance(approval, dict)
            raw_approval_status = approval["status"]
            if isinstance(raw_approval_status, str) and raw_approval_status in {"pending", "approved", "rejected"}:
                approval_status = raw_approval_status
            else:
                diagnostics.append(_diagnostic("production.attempt.approval.status", f"{attempt_path}.approval.status", "Approval status is unsupported."))
            record = approval["record"]
            if approval_status == "pending":
                if record is not None:
                    diagnostics.append(_diagnostic("production.attempt.approval.record", f"{attempt_path}.approval.record", "Pending approval must not claim an approval record."))
            elif approval_status in {"approved", "rejected"} and not _is_safe_nonempty_text(record, 1000):
                diagnostics.append(_diagnostic("production.attempt.approval.record", f"{attempt_path}.approval.record", "Completed approval requires a safe explicit record."))

        job_id = attempt["job_id"]
        output_id = attempt["output_id"]
        job_supplied = job_id is not None
        output_supplied = output_id is not None
        if job_supplied and (not isinstance(job_id, str) or SAFE_IDENTIFIER.fullmatch(job_id) is None):
            diagnostics.append(_diagnostic("production.attempt.job_id", f"{attempt_path}.job_id", "Job ID must be null or a safe identifier."))
        if output_supplied and (not isinstance(output_id, str) or SAFE_IDENTIFIER.fullmatch(output_id) is None):
            diagnostics.append(_diagnostic("production.attempt.output_id", f"{attempt_path}.output_id", "Output ID must be null or a safe identifier."))
        if job_supplied and approval_status != "approved":
            diagnostics.append(_diagnostic("production.attempt.job.approval", f"{attempt_path}.job_id", "A paid job requires explicit approval of its exact dry-run estimate."))
        if output_supplied and not job_supplied:
            diagnostics.append(_diagnostic("production.attempt.output.job", f"{attempt_path}.output_id", "An output ID requires its original job ID."))

        known_cost = attempt["known_cost"]
        if known_cost is not None:
            _validate_cost_record(
                diagnostics,
                known_cost,
                f"{attempt_path}.known_cost",
                "production.attempt.known_cost",
            )
            if not job_supplied:
                diagnostics.append(_diagnostic("production.attempt.cost.job", f"{attempt_path}.known_cost", "Known paid cost requires its original job ID."))

        acceptance = attempt["acceptance"]
        acceptance_status: str | None = None
        if _keys_are_exact(
            diagnostics,
            acceptance,
            {"status", "reason"},
            f"{attempt_path}.acceptance",
            "production.attempt.acceptance.keys",
        ):
            assert isinstance(acceptance, dict)
            raw_acceptance_status = acceptance["status"]
            acceptance_states = {
                "not_run", "running", "pending_review", "timed_out", "failed", "rejected", "accepted"
            }
            if isinstance(raw_acceptance_status, str) and raw_acceptance_status in acceptance_states:
                acceptance_status = raw_acceptance_status
            else:
                diagnostics.append(_diagnostic("production.attempt.acceptance.status", f"{attempt_path}.acceptance.status", "Acceptance status is unsupported."))
            reason = acceptance["reason"]
            if acceptance_status in {"not_run", "running", "pending_review"}:
                if reason is not None:
                    diagnostics.append(_diagnostic("production.attempt.acceptance.reason", f"{attempt_path}.acceptance.reason", "Nonterminal acceptance must not claim a terminal reason."))
            elif acceptance_status is not None and not _is_safe_nonempty_text(reason, 1000):
                diagnostics.append(_diagnostic("production.attempt.acceptance.reason", f"{attempt_path}.acceptance.reason", "Terminal acceptance requires a safe reason."))

        if not job_supplied and acceptance_status != "not_run":
            diagnostics.append(_diagnostic("production.attempt.acceptance.job", f"{attempt_path}.acceptance", "Acceptance state requires its original job ID."))
        if job_supplied and acceptance_status == "not_run":
            diagnostics.append(_diagnostic("production.attempt.acceptance.job", f"{attempt_path}.acceptance", "A submitted job must record its current acceptance state."))
        if output_supplied and acceptance_status not in {"pending_review", "rejected", "accepted"}:
            diagnostics.append(_diagnostic("production.attempt.output.acceptance", f"{attempt_path}.output_id", "Output ID requires a reviewable acceptance state."))
        if not output_supplied and acceptance_status in {"pending_review", "rejected", "accepted"}:
            diagnostics.append(_diagnostic("production.attempt.acceptance.output", f"{attempt_path}.acceptance", "Reviewable acceptance requires its output ID."))
        if acceptance_status == "accepted":
            accepted_count += 1

        reroll_diagnosis = attempt["reroll_diagnosis"]
        has_reroll_diagnosis = reroll_diagnosis is not None
        if has_reroll_diagnosis and not _is_safe_nonempty_text(reroll_diagnosis, 1000):
            diagnostics.append(_diagnostic("production.attempt.reroll_diagnosis", f"{attempt_path}.reroll_diagnosis", "Reroll diagnosis must be null or safe nonempty text."))
            has_reroll_diagnosis = False
        if has_reroll_diagnosis and acceptance_status not in {"failed", "rejected"}:
            diagnostics.append(_diagnostic("production.attempt.reroll_status", f"{attempt_path}.reroll_diagnosis", "Only a failed or rejected result may authorize a diagnosed reroll."))
        states.append((acceptance_status, has_reroll_diagnosis, approval_status, job_supplied))

    for attempt_index in range(1, len(states)):
        previous_status, previous_has_diagnosis, previous_approval, previous_has_job = states[attempt_index - 1]
        attempt_path = f"{path}.attempts[{attempt_index}]"
        rejected_before_call = (
            previous_status == "not_run"
            and previous_approval == "rejected"
            and not previous_has_job
        )
        if previous_status == "timed_out":
            diagnostics.append(_diagnostic("production.attempt.timeout.retry", attempt_path, "A timed-out job must be inspected by its original job ID and cannot be replaced."))
        elif previous_status not in {"failed", "rejected"} and not rejected_before_call:
            diagnostics.append(_diagnostic("production.attempt.lifecycle", attempt_path, "A new attempt requires a failed or rejected result or an explicitly rejected pre-call request."))
        if previous_status in {"failed", "rejected"} and not previous_has_diagnosis:
            diagnostics.append(_diagnostic("production.attempt.reroll_diagnosis", attempt_path, "A reroll requires one recorded diagnosis on the previous attempt."))

    if accepted_count > 1:
        diagnostics.append(_diagnostic("production.attempt.accepted.duplicate", f"{path}.attempts", "At most one production attempt may be accepted."))
    expected_disposition = "planned"
    if states:
        last_status = states[-1][0]
        expected_disposition = {
            "not_run": "planned",
            "running": "in_progress",
            "pending_review": "in_progress",
            "timed_out": "timed_out",
            "failed": "needs_reroll",
            "rejected": "needs_reroll",
            "accepted": "accepted",
        }.get(last_status, "planned")
    if isinstance(disposition, str) and disposition in dispositions and disposition != expected_disposition:
        diagnostics.append(_diagnostic("production.disposition.state", f"{path}.disposition", "Production disposition does not match the latest attempt."))
    if has_accepted_source and accepted_count != 1:
        diagnostics.append(_diagnostic("production.accepted_source", f"{shot_path}.accepted_source", "Accepted source requires exactly one accepted production attempt."))


def _validate_shot(
    diagnostics: list[Diagnostic],
    value: object,
    index: int,
    delivery: tuple[tuple[int, int], str, tuple[int, int], str] | None,
    approved_asset_ids: set[str],
) -> tuple[int, int] | None:
    path = f"shots[{index}]"
    required_keys = {"id", "timeline", "planning", "expected_output", "generation", "production"}
    allowed_keys = required_keys | {"accepted_source"}
    if not isinstance(value, dict) or set(value) != required_keys and set(value) != allowed_keys:
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
        if not _is_nonnegative_int(start) or not _is_positive_int(end) or end <= start:
            diagnostics.append(_diagnostic("timeline.range", f"{path}.timeline", "Timeline frames must be nonnegative exclusive integers with end after start."))
        else:
            frame_range = start, end

    source_present = "accepted_source" in value
    source = value.get("accepted_source")
    source_span: Decimal | None = None
    trim_start: Decimal | None = None
    trim_end: Decimal | None = None
    if source_present:
        if _keys_are_exact(
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
    handles = _validate_planning(
        diagnostics,
        value["planning"],
        path,
        frame_range,
        parameters,
    )
    _validate_production(diagnostics, value["production"], path, source_present)
    if frame_range is not None and delivery is not None:
        fps_num, fps_den = delivery[2]
        required_span = _frame_span_seconds(frame_range[1] - frame_range[0], fps_num, fps_den)
        if source_span is not None and source_span < required_span:
            diagnostics.append(_diagnostic("source.trim.coverage", f"{path}.accepted_source", "Source trim does not cover the planned edit frames."))
        if parameters is not None and isinstance(parameters.get("duration"), int):
            requested_duration = parameters["duration"]
            generation_capacity = Decimal("30") if requested_duration == -1 else Decimal(requested_duration)
            if generation_capacity < required_span:
                diagnostics.append(_diagnostic("generation.parameters.duration.coverage", f"{path}.generation.parameters.duration", "Seedance duration cannot cover the planned edit frames."))
            if handles is not None and generation_capacity < required_span + handles[0] + handles[1]:
                diagnostics.append(_diagnostic("planning.handles.coverage", f"{path}.planning.handles", "Seedance duration cannot cover the planned edit frames plus both handles."))
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
        target = _target_frame_count(master_duration, fps_num, fps_den)
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
