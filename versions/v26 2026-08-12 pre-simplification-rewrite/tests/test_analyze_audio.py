from __future__ import annotations

import hashlib
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts.analyze_audio import analyze_audio, main
from scripts.verify_delivery import preferred_temp_root


ROOT = Path(__file__).resolve().parents[1]


def write_stereo_wav(
    path: Path,
    duration_seconds: float,
    *,
    pulse_windows: list[tuple[float, float, int]] | None = None,
    silence_ranges: list[tuple[float, float]] | None = None,
) -> None:
    sample_rate = 44_100
    total_frames = int(sample_rate * duration_seconds)
    if pulse_windows is None:
        pulse_windows = [
            (index * 0.5, index * 0.5 + 0.025, 24_000)
            for index in range(math.ceil(duration_seconds / 0.5))
        ]
    if silence_ranges is None:
        silence_ranges = [(4.0, 6.0)]
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for frame_index in range(total_frames):
            timestamp = frame_index / sample_rate
            is_silent = any(
                start <= timestamp < end for start, end in silence_ranges
            )
            pulse_amplitude = next(
                (
                    amplitude
                    for start, end, amplitude in pulse_windows
                    if start <= timestamp < end
                ),
                0,
            )
            amplitude = 0 if is_silent else (pulse_amplitude or 6_000)
            sample = int(amplitude * math.sin(2 * math.pi * 440 * timestamp))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True) * 2)
        output.writeframes(frames)


def decoded_pcm_duration(path: Path, sample_rate: int) -> float:
    completed = subprocess.run(
        [
            "ffmpeg",
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
        check=True,
        capture_output=True,
    )
    return len(completed.stdout) / 2 / sample_rate


def container_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-of",
            "json",
            "-show_format",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return float(json.loads(completed.stdout)["format"]["duration"])


class AnalyzeAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_dir = Path(
            tempfile.mkdtemp(prefix="scenario-seedance-audio-tests-", dir=preferred_temp_root())
        )
        cls.master_path = cls.fixture_dir / "master with spaces.wav"
        cls.short_master_path = cls.fixture_dir / "short master.wav"
        cls.non_aligned_master_path = cls.fixture_dir / "non aligned master.wav"
        cls.compressed_master_path = cls.fixture_dir / "compressed master.mp4"
        cls.short_compressed_master_path = cls.fixture_dir / "short compressed master.mp4"
        cls.onset_master_path = cls.fixture_dir / "onset master.wav"
        cls.zero_onset_master_path = cls.fixture_dir / "zero onset master.wav"
        cls.silent_master_path = cls.fixture_dir / "silent master.wav"
        cls.non_audio_path = cls.fixture_dir / "not audio.txt"
        cls.lyrics_path = cls.fixture_dir / "lyrics with spaces.txt"
        write_stereo_wav(cls.master_path, 31.0)
        write_stereo_wav(cls.short_master_path, 29.0)
        write_stereo_wav(
            cls.non_aligned_master_path,
            30.25,
            silence_ranges=[(30.0, 30.25)],
        )
        write_stereo_wav(
            cls.onset_master_path,
            30.25,
            pulse_windows=[(1.13, 1.17, 24_000), (1.20, 1.24, 12_000), (2.05, 2.09, 24_000)],
            silence_ranges=[(0.0, 1.13), (1.17, 1.20), (1.24, 2.05), (2.09, 30.25)],
        )
        write_stereo_wav(
            cls.zero_onset_master_path,
            30.25,
            pulse_windows=[(0.0, 0.025, 24_000)],
            silence_ranges=[(0.025, 30.25)],
        )
        write_stereo_wav(
            cls.silent_master_path,
            30.25,
            pulse_windows=[],
            silence_ranges=[(0.0, 30.25)],
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=16x16:r=1:d=31",
                "-i",
                str(cls.non_aligned_master_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                str(cls.compressed_master_path),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=16x16:r=1:d=31",
                "-i",
                str(cls.short_master_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                str(cls.short_compressed_master_path),
            ],
            check=True,
        )
        cls.non_audio_path.write_text("not an audio file", encoding="utf-8")
        cls.lyrics_path.write_text("private lyric body\nthat must never appear", encoding="utf-8")

    def test_returns_hashed_master_facts_and_candidate_analysis(self) -> None:
        """Break caught: returning source facts from a proxy or omitting analysis fields."""
        result = analyze_audio(self.master_path)

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["master"]["path"], str(self.master_path))
        self.assertEqual(
            result["master"]["sha256"],
            hashlib.sha256(self.master_path.read_bytes()).hexdigest(),
        )
        self.assertAlmostEqual(result["master"]["duration_seconds"], 31.0, places=3)
        self.assertEqual(result["master"]["sample_rate"], 44_100)
        self.assertEqual(result["master"]["channels"], 2)
        self.assertTrue(result["analysis"]["energy_windows"])
        self.assertTrue(result["analysis"]["silence_regions"])
        self.assertTrue(result["analysis"]["onset_candidates"])
        self.assertIsInstance(result["analysis"]["tempo_candidates_bpm"], list)
        self.assertIn(result["analysis"]["tempo_confidence"], {"low", "medium", "high"})
        self.assertEqual(result["lyrics"], {"provided": False})

    def test_reports_source_codec_and_deterministic_level_measurements(self) -> None:
        """Break caught: promising codec, loudness, and peak facts without measuring them."""
        first = analyze_audio(self.master_path)
        second = analyze_audio(self.master_path)

        codec = first["master"]["codec"]
        self.assertEqual(codec["name"], "pcm_s16le")
        self.assertEqual(codec["sample_format"], "s16")
        self.assertEqual(codec["bits_per_sample"], 16)
        self.assertEqual(codec["bit_rate"], 1_411_200)
        self.assertIsInstance(codec["long_name"], str)

        levels = first["analysis"]["levels"]
        self.assertEqual(levels["measurement_method"], "ebu_r128_ffmpeg_loudnorm")
        self.assertEqual(levels["status"], "measured")
        self.assertIsInstance(levels["integrated_loudness_lufs"], float)
        self.assertIsInstance(levels["true_peak_dbtp"], float)
        self.assertIsInstance(levels["loudness_range_lu"], float)
        self.assertTrue(math.isfinite(levels["integrated_loudness_lufs"]))
        self.assertTrue(math.isfinite(levels["true_peak_dbtp"]))
        self.assertLessEqual(levels["true_peak_dbtp"], 0.0)
        self.assertEqual(levels, second["analysis"]["levels"])

    def test_reports_compressed_source_codec_instead_of_decode_target(self) -> None:
        """Break caught: labeling every master as PCM because analysis decodes to PCM."""
        result = analyze_audio(self.compressed_master_path)

        codec = result["master"]["codec"]
        self.assertEqual(codec["name"], "aac")
        self.assertNotEqual(codec["sample_format"], "s16")
        self.assertGreater(codec["bit_rate"], 0)

    def test_uses_null_finite_json_fields_when_silence_has_no_measurable_level(self) -> None:
        """Break caught: emitting infinity tokens for a silent master's level facts."""
        result = analyze_audio(self.silent_master_path)
        levels = result["analysis"]["levels"]

        self.assertEqual(levels["status"], "below_measurement_floor")
        self.assertIsNone(levels["integrated_loudness_lufs"])
        self.assertIsNone(levels["true_peak_dbtp"])
        self.assertEqual(json.dumps(result, allow_nan=False), json.dumps(result))

    def test_uses_decoded_pcm_duration_for_compressed_master_and_duration_gate(self) -> None:
        """Break caught: trusting compressed container duration instead of decoded samples."""
        decoded_duration = decoded_pcm_duration(self.compressed_master_path, 44_100)
        format_duration = container_duration(self.compressed_master_path)
        result = analyze_audio(self.compressed_master_path)

        self.assertGreaterEqual(decoded_duration, 30.0)
        self.assertNotAlmostEqual(format_duration, decoded_duration, places=4)
        self.assertAlmostEqual(
            result["master"]["duration_seconds"], decoded_duration, places=6
        )

    def test_clamps_final_analysis_endpoints_to_non_window_aligned_duration(self) -> None:
        """Break caught: analysis windows or silence regions extending beyond decoded audio."""
        result = analyze_audio(self.non_aligned_master_path)
        duration = result["master"]["duration_seconds"]

        self.assertAlmostEqual(duration, 30.25, places=6)
        self.assertLessEqual(result["analysis"]["energy_windows"][-1]["end_seconds"], duration)
        self.assertLessEqual(result["analysis"]["silence_regions"][-1]["end_seconds"], duration)

    def test_rejects_compressed_master_when_only_its_container_reaches_thirty_seconds(self) -> None:
        """Break caught: admitting a sub-30-second audio stream from a longer container."""
        decoded_duration = decoded_pcm_duration(
            self.short_compressed_master_path, 44_100
        )

        self.assertGreaterEqual(container_duration(self.short_compressed_master_path), 30.0)
        self.assertLess(decoded_duration, 30.0)
        with self.assertRaisesRegex(ValueError, "30"):
            analyze_audio(self.short_compressed_master_path)

    def test_uses_short_hop_local_maxima_with_refractory_onset_candidates(self) -> None:
        """Break caught: locating peaks on coarse windows or emitting adjacent onset duplicates."""
        first = analyze_audio(self.onset_master_path)
        second = analyze_audio(self.onset_master_path)
        onset_times = [
            candidate["time_seconds"]
            for candidate in first["analysis"]["onset_candidates"]
        ]

        self.assertEqual(first["analysis"]["onset_candidates"], second["analysis"]["onset_candidates"])
        self.assertTrue(any(1.10 <= time_seconds <= 1.18 for time_seconds in onset_times))
        self.assertFalse(any(1.19 <= time_seconds < 1.40 for time_seconds in onset_times))
        self.assertTrue(any(2.02 <= time_seconds <= 2.12 for time_seconds in onset_times))

    def test_detects_a_real_onset_at_zero_without_marking_silence(self) -> None:
        """Break caught: skipping the first envelope peak or treating silent audio as an onset."""
        zero_onsets = analyze_audio(self.zero_onset_master_path)["analysis"][
            "onset_candidates"
        ]
        silent_onsets = analyze_audio(self.silent_master_path)["analysis"][
            "onset_candidates"
        ]

        self.assertEqual(len(zero_onsets), 1)
        self.assertEqual(zero_onsets[0]["time_seconds"], 0.0)
        self.assertGreater(zero_onsets[0]["strength"], 0.1)
        self.assertEqual(silent_onsets, [])

    def test_rejects_missing_master(self) -> None:
        """Break caught: silently analyzing a nonexistent input."""
        with self.assertRaises(FileNotFoundError):
            analyze_audio(self.fixture_dir / "missing.wav")

    def test_rejects_master_shorter_than_thirty_seconds(self) -> None:
        """Break caught: accepting a master below the skill's minimum duration."""
        with self.assertRaisesRegex(ValueError, "30"):
            analyze_audio(self.short_master_path)

    def test_rejects_non_audio_input(self) -> None:
        """Break caught: treating a non-audio file as an analyzable master."""
        with self.assertRaises(ValueError):
            analyze_audio(self.non_audio_path)

    def test_hashes_lyrics_without_returning_the_lyric_body(self) -> None:
        """Break caught: leaking supplied lyric text into the analysis record."""
        result = analyze_audio(self.master_path, self.lyrics_path)
        serialized = json.dumps(result, sort_keys=True)

        self.assertEqual(
            result["lyrics"],
            {
                "provided": True,
                "path": str(self.lyrics_path),
                "sha256": hashlib.sha256(self.lyrics_path.read_bytes()).hexdigest(),
            },
        )
        self.assertNotIn("private lyric body", serialized)

    def test_cli_prints_strict_json_for_paths_with_spaces(self) -> None:
        """Break caught: emitting logs or malformed JSON when an input path contains spaces."""
        completed = subprocess.run(
            [sys.executable, "-m", "scripts.analyze_audio", str(self.master_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.stderr, "")
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["master"]["path"], str(self.master_path))
        self.assertEqual(json.dumps(payload, allow_nan=False), json.dumps(payload))

    def test_cli_writes_strict_json_without_stdout(self) -> None:
        """Break caught: writing a corrupt analysis file or mixing it with console output."""
        output_path = self.fixture_dir / "analysis output.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.analyze_audio",
                str(self.master_path),
                "--lyrics",
                str(self.lyrics_path),
                "--output",
                str(output_path),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["lyrics"]["provided"])
        self.assertNotIn("private lyric body", output_path.read_text(encoding="utf-8"))

    def test_cli_preserves_existing_output_on_collision(self) -> None:
        """Break caught: overwriting a preexisting output when another writer won the path."""
        output_path = self.fixture_dir / "existing analysis.json"
        original_contents = "existing analysis must survive\n"
        output_path.write_text(original_contents, encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.analyze_audio",
                str(self.master_path),
                "--output",
                str(output_path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Refusing to overwrite output", completed.stderr)
        self.assertEqual(output_path.read_text(encoding="utf-8"), original_contents)

    def test_cli_uses_exclusive_creation_when_output_appears_after_preflight(self) -> None:
        """Break caught: overwriting an output that appears between a check and file creation."""
        output_path = self.fixture_dir / "racing analysis.json"
        original_contents = "another writer created this file\n"
        output_path.write_text(original_contents, encoding="utf-8")
        original_exists = Path.exists

        def exists_before_race(path: Path) -> bool:
            if path == output_path:
                return False
            return original_exists(path)

        stderr = io.StringIO()
        with patch.object(Path, "exists", autospec=True, side_effect=exists_before_race):
            with redirect_stderr(stderr):
                return_code = main([str(self.master_path), "--output", str(output_path)])

        self.assertEqual(return_code, 2)
        self.assertIn("Refusing to overwrite output", stderr.getvalue())
        self.assertEqual(output_path.read_text(encoding="utf-8"), original_contents)


if __name__ == "__main__":
    unittest.main()
