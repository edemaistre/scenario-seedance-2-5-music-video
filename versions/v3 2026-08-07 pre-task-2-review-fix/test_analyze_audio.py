from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from scripts.analyze_audio import analyze_audio


ROOT = Path(__file__).resolve().parents[1]


def write_stereo_wav(path: Path, duration_seconds: float) -> None:
    sample_rate = 44_100
    total_frames = int(sample_rate * duration_seconds)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for frame_index in range(total_frames):
            timestamp = frame_index / sample_rate
            is_silent = 4.0 <= timestamp < 6.0
            pulse = (timestamp % 0.5) < 0.025
            amplitude = 0 if is_silent else (24_000 if pulse else 6_000)
            sample = int(amplitude * math.sin(2 * math.pi * 440 * timestamp))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True) * 2)
        output.writeframes(frames)


class AnalyzeAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_dir = Path(
            tempfile.mkdtemp(prefix="scenario-seedance-audio-tests-", dir="/private/tmp")
        )
        cls.master_path = cls.fixture_dir / "master with spaces.wav"
        cls.short_master_path = cls.fixture_dir / "short master.wav"
        cls.non_audio_path = cls.fixture_dir / "not audio.txt"
        cls.lyrics_path = cls.fixture_dir / "lyrics with spaces.txt"
        write_stereo_wav(cls.master_path, 31.0)
        write_stereo_wav(cls.short_master_path, 29.0)
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


if __name__ == "__main__":
    unittest.main()
