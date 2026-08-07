"""Verify a final music-video delivery against its immutable supplied master."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any


COPY_AUDIO_CODECS = frozenset({"aac", "mp3", "alac"})
MP4_MAJOR_BRANDS = frozenset(
    {
        "avc1",
        "dash",
        "f4v",
        "iso2",
        "iso3",
        "iso4",
        "iso5",
        "iso6",
        "isom",
        "m4v",
        "mp41",
        "mp42",
    }
)
ZERO_TOLERANCE = Decimal("0.001")
DELIVERY_EXTRA_TOLERANCE = Decimal("0.020")
AUTHORIZED_AUDIO_POLICY = {
    "source": "supplied_master",
    "start_seconds": "0.000",
    "clip_audio": "discard",
    "codec_policy": "copy_compatible_else_aac_320k",
}


def preferred_temp_root() -> Path:
    """Return the retained-artifact root for macOS and portable CI environments."""
    macos_temp_root = Path("/private/tmp")
    return macos_temp_root if macos_temp_root.is_dir() else Path(tempfile.gettempdir())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(arguments: list[str]) -> bytes:
    return subprocess.run(
        arguments,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _probe(path: Path, *, count_frames: bool = False) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error"]
    if count_frames:
        command.append("-count_frames")
    command.extend(["-show_streams", "-show_format", "-of", "json", str(path)])
    raw = _run(command)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise ValueError("FFprobe did not return a stream list")
    return data


def _decimal(value: object) -> Decimal | None:
    if value in (None, "N/A"):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _duration(probe: dict[str, Any], stream: dict[str, Any] | None) -> Decimal | None:
    if stream is not None:
        value = _decimal(stream.get("duration"))
        if value is not None and value >= 0:
            return value
    format_record = probe.get("format")
    if isinstance(format_record, dict):
        value = _decimal(format_record.get("duration"))
        if value is not None and value >= 0:
            return value
    return None


def _stream_duration(stream: dict[str, Any] | None) -> Decimal | None:
    if stream is None:
        return None
    value = _decimal(stream.get("duration"))
    return value if value is not None and value >= 0 else None


def _rational(value: object) -> Fraction | None:
    if not isinstance(value, str) or "/" not in value:
        return None
    numerator, denominator = value.split("/", 1)
    try:
        parsed = Fraction(int(numerator), int(denominator))
    except (ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0 else None


def _manifest_mapping(manifest: dict[str, object], key: str) -> dict[str, object]:
    value = manifest.get(key)
    return value if isinstance(value, dict) else {}


def _expected_delivery(manifest: dict[str, object]) -> tuple[int, int, Fraction, int] | None:
    master = _manifest_mapping(manifest, "master")
    delivery = _manifest_mapping(manifest, "delivery")
    geometry = delivery.get("geometry")
    frame_rate = delivery.get("frame_rate")
    duration = _decimal(master.get("decoded_duration_seconds"))
    if not isinstance(geometry, dict) or not isinstance(frame_rate, dict) or duration is None:
        return None
    try:
        width = int(geometry["width"])
        height = int(geometry["height"])
        fps = Fraction(int(frame_rate["fps_num"]), int(frame_rate["fps_den"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    if width <= 0 or height <= 0 or fps <= 0 or duration < 0:
        return None
    with localcontext() as context:
        context.prec = 50
        target_frames = int(
            (duration * Decimal(fps.numerator) / Decimal(fps.denominator)).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
    return width, height, fps, target_frames


def _extract_elementary_audio(path: Path, artifact_dir: Path, label: str) -> tuple[str, str]:
    """Return the packet-data hash and retained artifact path for one audio stream."""
    output = artifact_dir / f"{label}.elementary"
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-n",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy",
            "-f",
            "data",
            str(output),
        ]
    )
    return _sha256(output), str(output)


def _create_reference_aac(master: Path, artifact_dir: Path) -> Path:
    """Encode the immutable master with the assembly AAC delivery parameters."""
    output = artifact_dir / "reference-aac-320k.m4a"
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-n",
            "-i",
            str(master),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            str(output),
        ]
    )
    return output


def _stream_list(probe: dict[str, Any], codec_type: str) -> list[dict[str, Any]]:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return []
    return [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == codec_type]


def verify_delivery(
    final_path: Path, master_path: Path, manifest: dict[str, object]
) -> dict[str, object]:
    """Return deterministic technical checks for one final MP4 and its source master.

    Copied AAC, MP3, and ALAC streams must retain identical compressed packet
    bytes. A documented delivery transcode is timing-checked but explicitly
    reported as non-bit-exact.
    """
    final = Path(final_path)
    master = Path(master_path)
    checks: dict[str, bool | None] = {
        "source_master_sha256_unchanged": False,
        "mp4_container": False,
        "single_video_stream": False,
        "single_audio_stream": False,
        "geometry_match": False,
        "frame_rate_match": False,
        "exact_target_frame_count": False,
        "duration_compatible": False,
        "audio_duration_compatible": False,
        "audio_channels_match": False,
        "audio_starts_at_zero": False,
        "audio_timing_preserved": False,
        "audio_policy_authorized": False,
        "audio_codec_path_authorized": False,
        "audio_bit_exact": None,
        "derived_audio_matches_master": None,
        "generated_audio_absent": False,
    }
    warnings: list[str] = []
    technical: dict[str, object] = {
        "final_path": str(final),
        "master_path": str(master),
        "audio_integrity": {"mode": "unverified"},
    }

    expected = _expected_delivery(manifest)
    if expected is None:
        warnings.append("Manifest lacks usable delivery geometry, frame rate, or master duration.")
    master_record = _manifest_mapping(manifest, "master")
    delivery_record = _manifest_mapping(manifest, "delivery")
    audio_policy = delivery_record.get("audio_policy")
    checks["audio_policy_authorized"] = audio_policy == AUTHORIZED_AUDIO_POLICY
    technical["audio_policy"] = audio_policy
    if not checks["audio_policy_authorized"]:
        warnings.append("Manifest audio policy is missing or differs from the authorized delivery policy.")
    expected_master_hash = master_record.get("sha256")
    try:
        master_available = master.is_file()
        if master_available and isinstance(expected_master_hash, str):
            actual_master_hash = _sha256(master)
            technical["master_sha256"] = actual_master_hash
            checks["source_master_sha256_unchanged"] = actual_master_hash == expected_master_hash
            if not checks["source_master_sha256_unchanged"]:
                warnings.append("The source master SHA-256 does not match the manifest.")
        else:
            warnings.append("The source master or its manifest SHA-256 is unavailable.")
    except OSError as error:
        technical["master_hash_error"] = str(error)
        warnings.append(f"Could not hash source master: {error}")
    if not isinstance(expected_master_hash, str):
        warnings.append("The source master or its manifest SHA-256 is unavailable.")

    try:
        master_probe = _probe(master)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as error:
        warnings.append(f"Could not probe source master: {error}")
        master_probe = None
    try:
        final_probe = _probe(final, count_frames=True)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as error:
        warnings.append(f"Could not probe final delivery: {error}")
        final_probe = None

    if master_probe is None or final_probe is None:
        return {"passed": False, "checks": checks, "warnings": warnings, "technical": technical}

    format_record = final_probe.get("format")
    format_record = format_record if isinstance(format_record, dict) else {}
    format_name = format_record.get("format_name")
    format_names = (
        {name.strip().lower() for name in format_name.split(",")}
        if isinstance(format_name, str)
        else set()
    )
    format_tags = format_record.get("tags")
    format_tags = format_tags if isinstance(format_tags, dict) else {}
    major_brand = format_tags.get("major_brand")
    normalized_major_brand = (
        major_brand.strip().lower() if isinstance(major_brand, str) else None
    )
    compatible_brands = format_tags.get("compatible_brands")
    checks["mp4_container"] = bool(
        "mp4" in format_names and normalized_major_brand in MP4_MAJOR_BRANDS
    )
    technical["container"] = {
        "format_name": format_name if isinstance(format_name, str) else None,
        "major_brand": major_brand if isinstance(major_brand, str) else None,
        "compatible_brands": (
            compatible_brands if isinstance(compatible_brands, str) else None
        ),
    }
    if not checks["mp4_container"]:
        warnings.append("Final delivery is not a recognized MP4-family container and brand.")

    master_audio_streams = _stream_list(master_probe, "audio")
    videos = _stream_list(final_probe, "video")
    audios = _stream_list(final_probe, "audio")
    checks["single_video_stream"] = len(videos) == 1
    checks["single_audio_stream"] = len(audios) == 1
    technical["master_stream_counts"] = {"audio": len(master_audio_streams)}
    technical["final_stream_counts"] = {"video": len(videos), "audio": len(audios)}
    if len(videos) != 1:
        warnings.append(f"Final delivery has {len(videos)} video streams, expected one.")
    if len(audios) != 1:
        warnings.append(f"Final delivery has {len(audios)} audio streams, expected one; multiple audio tracks can retain generated audio.")

    video = videos[0] if len(videos) == 1 else None
    audio = audios[0] if len(audios) == 1 else None
    master_audio = master_audio_streams[0] if len(master_audio_streams) == 1 else None
    master_duration = _duration(master_probe, master_audio)
    final_duration = _duration(final_probe, video)
    final_audio_duration = _stream_duration(audio)
    technical["master_duration_seconds"] = float(master_duration) if master_duration is not None else None
    technical["final_duration_seconds"] = float(final_duration) if final_duration is not None else None
    technical["final_audio_duration_seconds"] = (
        float(final_audio_duration) if final_audio_duration is not None else None
    )

    if expected is not None and video is not None:
        width, height, fps, target_frames = expected
        checks["geometry_match"] = (video.get("width"), video.get("height")) == (width, height)
        actual_rate = _rational(video.get("avg_frame_rate"))
        checks["frame_rate_match"] = actual_rate == fps
        try:
            frame_count = int(video["nb_read_frames"])
        except (KeyError, TypeError, ValueError):
            frame_count = None
        checks["exact_target_frame_count"] = frame_count == target_frames
        technical["expected_video"] = {
            "width": width,
            "height": height,
            "frame_rate": f"{fps.numerator}/{fps.denominator}",
            "target_frame_count": target_frames,
        }
        technical["final_video"] = {
            "width": video.get("width"),
            "height": video.get("height"),
            "frame_rate": video.get("avg_frame_rate"),
            "frame_count": frame_count,
        }
        if not checks["geometry_match"]:
            warnings.append("Final video geometry does not match the manifest.")
        if not checks["frame_rate_match"]:
            warnings.append("Final video frame rate does not match the manifest rational frame rate.")
        if not checks["exact_target_frame_count"]:
            warnings.append("Final video frame count does not equal the manifest target frame count.")

    if expected is not None and master_duration is not None and final_duration is not None:
        tolerance = Decimal(expected[2].denominator) / Decimal(expected[2].numerator) + DELIVERY_EXTRA_TOLERANCE
        checks["duration_compatible"] = abs(final_duration - master_duration) <= tolerance
        technical["duration_tolerance_seconds"] = float(tolerance)
        if not checks["duration_compatible"]:
            warnings.append("Final duration differs from the master by more than one frame plus 20 ms.")

        checks["audio_duration_compatible"] = (
            final_audio_duration is not None
            and abs(final_audio_duration - master_duration) <= tolerance
        )
        if not checks["audio_duration_compatible"]:
            warnings.append("Final audio duration differs from the master by more than one frame plus 20 ms.")

    if audio is not None and master_audio is not None:
        final_channels = audio.get("channels")
        master_channels = master_audio.get("channels")
        manifest_channels = master_record.get("channels")
        checks["audio_channels_match"] = (
            isinstance(final_channels, int)
            and final_channels == master_channels
            and (not isinstance(manifest_channels, int) or final_channels == manifest_channels)
        )
        start = _decimal(audio.get("start_time"))
        checks["audio_starts_at_zero"] = start is not None and abs(start) <= ZERO_TOLERANCE
        checks["audio_timing_preserved"] = bool(
            checks["duration_compatible"]
            and checks["audio_duration_compatible"]
            and checks["audio_starts_at_zero"]
            and checks["audio_channels_match"]
        )
        technical["master_audio"] = {
            "codec": master_audio.get("codec_name"),
            "channels": master_channels,
            "duration_seconds": float(_duration(master_probe, master_audio) or Decimal(0)),
        }
        technical["final_audio"] = {
            "codec": audio.get("codec_name"),
            "channels": final_channels,
            "start_seconds": float(start) if start is not None else None,
            "duration_seconds": float(final_audio_duration or Decimal(0)),
        }
        if not checks["audio_channels_match"]:
            warnings.append("Final audio channel count does not match the supplied master.")
        if not checks["audio_starts_at_zero"]:
            warnings.append("Final audio does not begin at timeline zero.")

        master_codec = master_audio.get("codec_name")
        final_codec = audio.get("codec_name")
        copy_path = master_codec in COPY_AUDIO_CODECS
        checks["audio_codec_path_authorized"] = (
            final_codec == master_codec if copy_path else final_codec == "aac"
        )
        if not checks["audio_codec_path_authorized"]:
            warnings.append("Final audio codec does not follow the authorized copy-or-AAC path.")

        if copy_path and checks["audio_codec_path_authorized"]:
            artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-delivery-", dir=preferred_temp_root()))
            try:
                master_hash, master_artifact = _extract_elementary_audio(master, artifact_dir, "master")
                final_hash, final_artifact = _extract_elementary_audio(final, artifact_dir, "final")
                checks["audio_bit_exact"] = master_hash == final_hash
                checks["generated_audio_absent"] = bool(checks["audio_bit_exact"])
                technical["audio_integrity"] = {
                    "mode": "stream_copy",
                    "master_elementary_sha256": master_hash,
                    "final_elementary_sha256": final_hash,
                    "artifacts": [master_artifact, final_artifact],
                }
                if not checks["audio_bit_exact"]:
                    warnings.append("Compressed master audio differs from the final stream, indicating altered or generated audio.")
            except (OSError, subprocess.CalledProcessError) as error:
                checks["audio_bit_exact"] = False
                technical["audio_integrity"] = {"mode": "stream_copy", "error": str(error), "artifact_dir": str(artifact_dir)}
                warnings.append("Could not compare copied audio packet data.")
        elif not copy_path and checks["audio_codec_path_authorized"]:
            checks["audio_bit_exact"] = None
            artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-delivery-", dir=preferred_temp_root()))
            try:
                reference_aac = _create_reference_aac(master, artifact_dir)
                reference_hash, reference_artifact = _extract_elementary_audio(
                    reference_aac, artifact_dir, "reference"
                )
                final_hash, final_artifact = _extract_elementary_audio(
                    final, artifact_dir, "final"
                )
                checks["derived_audio_matches_master"] = reference_hash == final_hash
                checks["generated_audio_absent"] = bool(
                    checks["derived_audio_matches_master"]
                )
                technical["audio_integrity"] = {
                    "mode": "transcoded",
                    "master_codec": master_codec,
                    "final_codec": final_codec,
                    "source_bit_exact": None,
                    "reference_encode": ["-c:a", "aac", "-b:a", "320k"],
                    "reference_aac_path": str(reference_aac),
                    "reference_elementary_sha256": reference_hash,
                    "final_elementary_sha256": final_hash,
                    "artifacts": [str(reference_aac), reference_artifact, final_artifact],
                }
                if not checks["derived_audio_matches_master"]:
                    warnings.append("Final AAC packet data does not match the deterministic master-derived reference.")
            except (OSError, subprocess.CalledProcessError) as error:
                checks["derived_audio_matches_master"] = False
                technical["audio_integrity"] = {
                    "mode": "transcoded",
                    "error": str(error),
                    "artifact_dir": str(artifact_dir),
                }
                warnings.append("Could not compare final AAC with the deterministic master-derived reference.")
            warnings.append("Audio was transcoded and is not bit-exact; timing and stream facts were checked.")
        else:
            checks["audio_bit_exact"] = False if copy_path else None
            checks["derived_audio_matches_master"] = None
            checks["generated_audio_absent"] = False
            technical["audio_integrity"] = {
                "mode": "unauthorized_codec",
                "master_codec": master_codec,
                "final_codec": final_codec,
            }

    try:
        closing_master_hash = _sha256(master)
        technical["master_sha256_after_verification"] = closing_master_hash
        if (
            not checks["source_master_sha256_unchanged"]
            or closing_master_hash != expected_master_hash
            or closing_master_hash != technical.get("master_sha256")
        ):
            checks["source_master_sha256_unchanged"] = False
            warnings.append("The source master changed during verification.")
    except OSError as error:
        checks["source_master_sha256_unchanged"] = False
        technical["master_closing_hash_error"] = str(error)
        warnings.append(f"Could not hash source master after verification: {error}")

    required_keys = {
        "source_master_sha256_unchanged",
        "mp4_container",
        "single_video_stream",
        "single_audio_stream",
        "geometry_match",
        "frame_rate_match",
        "exact_target_frame_count",
        "duration_compatible",
        "audio_duration_compatible",
        "audio_channels_match",
        "audio_starts_at_zero",
        "audio_timing_preserved",
        "audio_policy_authorized",
        "audio_codec_path_authorized",
        "generated_audio_absent",
    }
    provenance_check = (
        "audio_bit_exact"
        if master_audio is not None and master_audio.get("codec_name") in COPY_AUDIO_CODECS
        else "derived_audio_matches_master"
    )
    required_keys.add(provenance_check)
    passed = all(checks[key] is True for key in required_keys)
    return {"passed": passed, "checks": checks, "warnings": warnings, "technical": technical}
