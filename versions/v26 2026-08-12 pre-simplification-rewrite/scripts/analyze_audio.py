from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

MINIMUM_DURATION_SECONDS = 30.0
ENERGY_WINDOW_SECONDS = 0.5
TEMPO_WINDOW_SECONDS = 0.1
ONSET_WINDOW_SECONDS = 0.025
ONSET_REFRACTORY_SECONDS = 0.2
SILENCE_RMS_THRESHOLD = 0.02
TOOL_TIMEOUT_SECONDS = 600


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")


def _run_tool(
    arguments: list[str], error_context: str
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            arguments,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"Required tool is unavailable: {arguments[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{error_context}: {arguments[0]} exceeded the "
            f"{TOOL_TIMEOUT_SECONDS}-second safety limit"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        message = f"{error_context}: {detail}" if detail else error_context
        raise ValueError(message) from error


def _tool_output(arguments: list[str], error_context: str) -> bytes:
    return _run_tool(arguments, error_context).stdout


def _positive_int_or_none(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _probe_audio(path: Path) -> tuple[int, int, dict[str, object]]:
    raw_probe = _tool_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-of",
            "json",
            "-select_streams",
            "a:0",
            "-show_entries",
            (
                "stream=codec_type,codec_name,codec_long_name,profile,sample_fmt,"
                "sample_rate,channels,bits_per_sample,bits_per_raw_sample,bit_rate"
            ),
            str(path),
        ],
        "Could not inspect the master audio",
    )
    try:
        probe = json.loads(raw_probe)
        streams = probe["streams"]
        stream = next(item for item in streams if item.get("codec_type") == "audio")
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read audio stream facts from: {path}") from error
    if sample_rate <= 0 or channels <= 0:
        raise ValueError(f"Master audio has invalid stream facts: {path}")
    codec_name = stream.get("codec_name")
    if not isinstance(codec_name, str) or not codec_name:
        raise ValueError(f"Could not read source codec from: {path}")
    codec = {
        "name": codec_name,
        "long_name": stream.get("codec_long_name")
        if isinstance(stream.get("codec_long_name"), str)
        else None,
        "profile": stream.get("profile")
        if isinstance(stream.get("profile"), str)
        else None,
        "sample_format": stream.get("sample_fmt")
        if isinstance(stream.get("sample_fmt"), str)
        else None,
        "bits_per_sample": _positive_int_or_none(
            stream.get("bits_per_sample") or stream.get("bits_per_raw_sample")
        ),
        "bit_rate": _positive_int_or_none(stream.get("bit_rate")),
    }
    return sample_rate, channels, codec


def _finite_float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _measure_levels(path: Path) -> dict[str, object]:
    completed = _run_tool(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-nostats",
            "-v",
            "info",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "loudnorm=I=-24:LRA=7:TP=-2:print_format=json",
            "-f",
            "null",
            "-",
        ],
        "Could not measure master loudness and peak",
    )
    diagnostic = completed.stderr.decode("utf-8", errors="replace")
    marker_index = diagnostic.rfind('"input_i"')
    object_start = diagnostic.rfind("{", 0, marker_index)
    object_end = diagnostic.find("}", marker_index)
    if marker_index < 0 or object_start < 0 or object_end < 0:
        raise ValueError("Could not read FFmpeg loudness measurements")
    try:
        measurements = json.loads(diagnostic[object_start : object_end + 1])
    except json.JSONDecodeError as error:
        raise ValueError("Could not parse FFmpeg loudness measurements") from error

    integrated_loudness = _finite_float_or_none(measurements.get("input_i"))
    true_peak = _finite_float_or_none(measurements.get("input_tp"))
    status = (
        "measured"
        if integrated_loudness is not None and true_peak is not None
        else "below_measurement_floor"
    )
    return {
        "measurement_method": "ebu_r128_ffmpeg_loudnorm",
        "status": status,
        "integrated_loudness_lufs": integrated_loudness,
        "true_peak_dbtp": true_peak,
        "loudness_range_lu": _finite_float_or_none(measurements.get("input_lra")),
        "relative_threshold_lufs": _finite_float_or_none(
            measurements.get("input_thresh")
        ),
    }


def _decode_mono_pcm(path: Path) -> array.array[int]:
    raw_pcm = _tool_output(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-f",
            "s16le",
            "-",
        ],
        "Could not decode the master audio",
    )
    samples = array.array("h")
    samples.frombytes(raw_pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError(f"Master audio contains no decodable samples: {path}")
    return samples


def _rms_windows(
    samples: array.array[int], sample_rate: int, window_seconds: float
) -> list[float]:
    window_frames = max(1, round(sample_rate * window_seconds))
    windows: list[float] = []
    for start in range(0, len(samples), window_frames):
        window = samples[start : start + window_frames]
        mean_square = sum(sample * sample for sample in window) / len(window)
        windows.append(math.sqrt(mean_square) / 32_768)
    return windows


def _energy_records(
    values: list[float], window_seconds: float, duration_seconds: float
) -> list[dict[str, float]]:
    return [
        {
            "start_seconds": round(index * window_seconds, 4),
            "end_seconds": round(
                min((index + 1) * window_seconds, duration_seconds), 4
            ),
            "rms": round(value, 6),
        }
        for index, value in enumerate(values)
    ]


def _silence_regions(
    values: list[float], window_seconds: float, duration_seconds: float
) -> list[dict[str, float]]:
    regions: list[dict[str, float]] = []
    start_index: int | None = None
    for index, value in enumerate(values):
        if value <= SILENCE_RMS_THRESHOLD and start_index is None:
            start_index = index
        if value > SILENCE_RMS_THRESHOLD and start_index is not None:
            regions.append(
                {
                    "start_seconds": round(start_index * window_seconds, 4),
                    "end_seconds": round(min(index * window_seconds, duration_seconds), 4),
                }
            )
            start_index = None
    if start_index is not None:
        regions.append(
            {
                "start_seconds": round(start_index * window_seconds, 4),
                "end_seconds": round(
                    min(len(values) * window_seconds, duration_seconds), 4
                ),
            }
        )
    return regions


def _onset_candidates(values: list[float], window_seconds: float) -> list[dict[str, float]]:
    if len(values) < 3:
        return []
    threshold = max(0.01, max(values) * 0.2)
    peaks: list[tuple[float, int]] = []
    for index in range(0, len(values) - 1):
        value = values[index]
        previous = 0.0 if index == 0 else values[index - 1]
        if (
            value >= threshold
            and value >= previous
            and value > values[index + 1]
        ):
            peaks.append((value, index))

    refractory_windows = max(1, round(ONSET_REFRACTORY_SECONDS / window_seconds))
    selected: list[tuple[float, int]] = []
    for strength, index in sorted(peaks, key=lambda peak: (-peak[0], peak[1])):
        if all(abs(index - chosen_index) >= refractory_windows for _, chosen_index in selected):
            selected.append((strength, index))
    selected.sort(key=lambda peak: peak[1])
    return [
        {
            "time_seconds": round(index * window_seconds, 4),
            "strength": round(strength, 6),
        }
        for strength, index in selected
    ]


def _tempo_candidates(values: list[float], window_seconds: float) -> tuple[list[float], str]:
    if len(values) < 8:
        return [], "low"
    mean = sum(values) / len(values)
    centered = [value - mean for value in values]
    energy = sum(value * value for value in centered)
    if energy == 0:
        return [], "low"

    scored_lags: list[tuple[float, int]] = []
    minimum_lag = max(1, math.ceil(60 / (200 * window_seconds)))
    maximum_lag = min(len(centered) - 1, math.floor(60 / (60 * window_seconds)))
    for lag in range(minimum_lag, maximum_lag + 1):
        correlation = sum(
            centered[index] * centered[index - lag]
            for index in range(lag, len(centered))
        ) / energy
        scored_lags.append((correlation, lag))
    scored_lags.sort(key=lambda item: (-item[0], item[1]))

    selected: list[tuple[float, int]] = []
    for score, lag in scored_lags:
        if score <= 0:
            continue
        if any(abs(lag - chosen_lag) <= 1 for _, chosen_lag in selected):
            continue
        selected.append((score, lag))
        if len(selected) == 3:
            break
    candidates = [round(60 / (lag * window_seconds), 2) for _, lag in selected]
    if not selected:
        return candidates, "low"
    best_score = selected[0][0]
    if best_score >= 0.65:
        confidence = "high"
    elif best_score >= 0.35:
        confidence = "medium"
    else:
        confidence = "low"
    return candidates, confidence


def analyze_audio(path: Path, lyrics_path: Path | None = None) -> dict[str, object]:
    """Return deterministic technical facts and candidate timing signals for a master."""
    master_path = Path(path)
    _require_file(master_path, "Master audio")
    sample_rate, channels, codec = _probe_audio(master_path)
    samples = _decode_mono_pcm(master_path)
    duration_seconds = len(samples) / sample_rate
    if duration_seconds < MINIMUM_DURATION_SECONDS:
        raise ValueError(
            f"Master audio must be at least {MINIMUM_DURATION_SECONDS:g} seconds: "
            f"measured {duration_seconds:.3f} seconds"
        )
    energy_values = _rms_windows(samples, sample_rate, ENERGY_WINDOW_SECONDS)
    tempo_values = _rms_windows(samples, sample_rate, TEMPO_WINDOW_SECONDS)
    onset_values = _rms_windows(samples, sample_rate, ONSET_WINDOW_SECONDS)
    tempo_candidates, tempo_confidence = _tempo_candidates(
        tempo_values, TEMPO_WINDOW_SECONDS
    )
    levels = _measure_levels(master_path)

    lyrics: dict[str, object] = {"provided": False}
    if lyrics_path is not None:
        source_lyrics_path = Path(lyrics_path)
        _require_file(source_lyrics_path, "Lyrics")
        lyrics = {
            "provided": True,
            "path": str(source_lyrics_path),
            "sha256": _sha256(source_lyrics_path),
        }

    return {
        "schema_version": 1,
        "master": {
            "path": str(master_path),
            "sha256": _sha256(master_path),
            "duration_seconds": round(duration_seconds, 6),
            "sample_rate": sample_rate,
            "channels": channels,
            "codec": codec,
        },
        "analysis": {
            "levels": levels,
            "energy_windows": _energy_records(
                energy_values, ENERGY_WINDOW_SECONDS, duration_seconds
            ),
            "silence_regions": _silence_regions(
                energy_values, ENERGY_WINDOW_SECONDS, duration_seconds
            ),
            "onset_candidates": _onset_candidates(onset_values, ONSET_WINDOW_SECONDS),
            "tempo_candidates_bpm": tempo_candidates,
            "tempo_confidence": tempo_confidence,
        },
        "lyrics": lyrics,
    }


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a local master audio file without altering it."
    )
    parser.add_argument("master", type=Path, help="Path to the supplied master audio")
    parser.add_argument("--lyrics", type=Path, help="Optional lyrics file to hash")
    parser.add_argument("--output", type=Path, help="Write strict JSON to a new file")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_arguments(arguments)
    try:
        result = analyze_audio(args.master, args.lyrics)
        rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            try:
                with args.output.open("x", encoding="utf-8") as output:
                    output.write(rendered)
            except FileExistsError as error:
                raise FileExistsError(f"Refusing to overwrite output: {args.output}")
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
