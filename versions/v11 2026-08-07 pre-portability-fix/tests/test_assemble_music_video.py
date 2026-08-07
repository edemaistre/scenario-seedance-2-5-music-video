from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assemble_music_video import AssemblyError, assemble, build_ffmpeg_command


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "valid_30s_project.json"


def run_tool(arguments: list[str]) -> bytes:
    return subprocess.run(arguments, check=True, capture_output=True).stdout


def make_manifest(project_root: Path, master_name: str) -> dict[str, object]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    master = data["master"]
    delivery = data["delivery"]
    assert isinstance(master, dict) and isinstance(delivery, dict)
    master_path = project_root / "masters" / master_name
    master["path"] = f"masters/{master_name}"
    master["sha256"] = hashlib.sha256(master_path.read_bytes()).hexdigest()
    master["decoded_duration_seconds"] = 30.0
    master["sample_rate"] = 48_000
    master["channels"] = 1
    delivery["geometry"] = {"width": 480, "height": 480}
    delivery["aspect_ratio"] = "1:1"
    delivery["frame_rate"] = {"fps_num": 10, "fps_den": 1}
    delivery["resolution"] = "480p"

    shots: list[dict[str, object]] = []
    for index, (clip_name, start_frame, end_frame, trim_start) in enumerate(
        (
            ("first generated clip.mp4", 0, 150, "5.000"),
            ("second generated clip.mp4", 150, 300, "2.000"),
        ),
        start=1,
    ):
        shot = copy.deepcopy(data["shots"][0])
        assert isinstance(shot, dict)
        shot["id"] = f"shot-{index:03d}"
        shot["timeline"] = {"start_frame": start_frame, "end_frame": end_frame}
        shot["accepted_source"] = {
            "path": f"clips/{clip_name}",
            "trim_start_seconds": trim_start,
            "trim_end_seconds": f"{float(trim_start) + 15:.3f}",
        }
        shot["expected_output"] = {
            "geometry": {"width": 480, "height": 480},
            "aspect_ratio": "1:1",
            "frame_rate": {"fps_num": 10, "fps_den": 1},
            "resolution": "480p",
        }
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["duration"] = 30
        parameters["resolution"] = "480p"
        parameters["aspectRatio"] = "1:1"
        shots.append(shot)
    data["shots"] = shots
    return data


def make_fractional_rate_manifest(
    project_root: Path, master_name: str
) -> dict[str, object]:
    data = make_manifest(project_root, master_name)
    master = data["master"]
    delivery = data["delivery"]
    shots = data["shots"]
    assert isinstance(master, dict) and isinstance(delivery, dict)
    assert isinstance(shots, list)
    master["decoded_duration_seconds"] = 30.001
    delivery["frame_rate"] = {"fps_num": 30_000, "fps_den": 1_001}
    for shot, timeline, trim_end in zip(
        shots,
        (
            {"start_frame": 0, "end_frame": 450},
            {"start_frame": 450, "end_frame": 900},
        ),
        ("20.015", "17.015"),
        strict=True,
    ):
        assert isinstance(shot, dict)
        shot["timeline"] = timeline
        source = shot["accepted_source"]
        expected = shot["expected_output"]
        assert isinstance(source, dict) and isinstance(expected, dict)
        source["trim_end_seconds"] = trim_end
        expected["frame_rate"] = {"fps_num": 30_000, "fps_den": 1_001}
    return data


def video_probe(path: Path) -> dict[str, object]:
    raw = run_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(raw)


def center_rgb(path: Path, timestamp: float) -> tuple[int, int, int]:
    raw = run_tool(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(timestamp),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "crop=1:1:240:240,format=rgb24",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    return raw[0], raw[1], raw[2]


def tone_score(path: Path, frequency: float) -> float:
    sample_rate = 8_000
    raw = run_tool(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-t",
            "1",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "s16le",
            "-",
        ]
    )
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    real = sum(value * math.cos(2 * math.pi * frequency * index / sample_rate) for index, value in enumerate(samples))
    imaginary = sum(value * math.sin(2 * math.pi * frequency * index / sample_rate) for index, value in enumerate(samples))
    return math.hypot(real, imaginary)


class AssembleMusicVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            raise unittest.SkipTest("FFmpeg integration tests require ffmpeg and ffprobe")
        cls.project_root = Path(
            tempfile.mkdtemp(prefix="scenario-seedance-assembly tests-", dir="/private/tmp")
        )
        (cls.project_root / "clips").mkdir()
        (cls.project_root / "masters").mkdir()
        cls.first_clip = cls.project_root / "clips" / "first generated clip.mp4"
        cls.second_clip = cls.project_root / "clips" / "second generated clip.mp4"
        cls._make_clip(cls.first_clip, "red", 5, "yellow", 16, 330)
        cls._make_clip(cls.second_clip, "blue", 2, "cyan", 19, 550)
        for filename, codec in (
            ("master.wav", "pcm_s16le"),
            ("master.flac", "flac"),
            ("master.m4a", "aac"),
            ("master.mp3", "libmp3lame"),
            ("master-alac.m4a", "alac"),
        ):
            cls._make_master(cls.project_root / "masters" / filename, codec)
        cls._make_master(cls.project_root / "masters" / "short master.wav", "pcm_s16le", 5)
        cls._make_master(cls.project_root / "masters" / "long master.wav", "pcm_s16le", 30.2)
        cls._make_master(
            cls.project_root / "masters" / "fractional master.wav", "pcm_s16le", 30.001
        )

    @classmethod
    def _make_clip(
        cls,
        path: Path,
        first_color: str,
        first_duration: int,
        second_color: str,
        second_duration: int,
        frequency: int,
    ) -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c={first_color}:s=480x480:r=10:d={first_duration}",
                "-f",
                "lavfi",
                "-i",
                f"color=c={second_color}:s=480x480:r=10:d={second_duration}",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration={first_duration + second_duration}",
                "-filter_complex",
                "[0:v:0][1:v:0]concat=n=2:v=1:a=0[v]",
                "-map",
                "[v]",
                "-map",
                "2:a:0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-y",
                str(path),
            ],
            check=True,
        )

    @classmethod
    def _make_master(cls, path: Path, codec: str, duration: float = 30) -> None:
        arguments = [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=880:sample_rate=48000:duration={duration}",
            "-c:a",
            codec,
        ]
        if codec in {"aac", "libmp3lame"}:
            arguments.extend(["-b:a", "320k"])
        arguments.extend(["-y", str(path)])
        subprocess.run(arguments, check=True)

    def test_assembles_declared_trims_in_order_and_uses_only_master_audio(self) -> None:
        """Break caught: sorting sources, ignoring trims, or retaining generated clip audio."""
        manifest = make_manifest(self.project_root, "master.wav")
        output = self.project_root / "delivery with spaces.mp4"

        result = assemble(manifest, self.project_root, output)

        probe = video_probe(output)
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
        self.assertEqual((video["width"], video["height"]), (480, 480))
        self.assertEqual(video["pix_fmt"], "yuv420p")
        self.assertEqual(video["codec_name"], "h264")
        self.assertEqual(video["avg_frame_rate"], "10/1")
        self.assertEqual(int(video["nb_read_frames"]), 300)
        self.assertEqual(audio["codec_name"], "aac")
        self.assertAlmostEqual(float(audio["start_time"]), 0.0, places=3)
        self.assertAlmostEqual(float(probe["format"]["duration"]), 30.0, delta=0.12)
        self.assertGreater(center_rgb(output, 2.0)[0], 220)
        self.assertGreater(center_rgb(output, 2.0)[1], 220)
        self.assertLess(center_rgb(output, 2.0)[2], 40)
        self.assertLess(center_rgb(output, 17.0)[0], 40)
        self.assertGreater(center_rgb(output, 17.0)[1], 220)
        self.assertGreater(center_rgb(output, 17.0)[2], 220)
        self.assertGreater(tone_score(output, 880), tone_score(output, 330) * 8)
        self.assertGreater(tone_score(output, 880), tone_score(output, 550) * 8)
        self.assertEqual(result["frame_count"], 300)
        self.assertEqual(result["audio_mode"], "encode_aac_320k")

    def test_stream_copies_mp4_compatible_master_audio(self) -> None:
        """Break caught: needlessly re-encoding an MP4-compatible supplied master."""
        manifest = make_manifest(self.project_root, "master.m4a")
        output = self.project_root / "delivery copied audio.mp4"

        result = assemble(manifest, self.project_root, output)

        probe = video_probe(output)
        audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
        self.assertEqual(audio["codec_name"], "aac")
        self.assertEqual(result["audio_mode"], "copy")
        self.assertAlmostEqual(float(probe["format"]["duration"]), 30.0, delta=0.12)

    def test_build_command_copies_compatible_codecs_and_encodes_lossless_sources_once(self) -> None:
        """Break caught: applying an audio filter or choosing the wrong delivery codec path."""
        for filename in ("master.m4a", "master.mp3", "master-alac.m4a"):
            with self.subTest(filename=filename):
                manifest = make_manifest(self.project_root, filename)
                master = manifest["master"]
                assert isinstance(master, dict)
                master["path"] = str((self.project_root / "masters" / filename).resolve())
                command = build_ffmpeg_command(manifest, self.project_root / f"{filename}.mp4")
                self.assertEqual(command[command.index("-c:a") + 1], "copy")
                self.assertNotIn("-shortest", command)
                self.assertNotIn("-af", command)
                self.assertNotIn("-filter:a", command)
                self.assertEqual(command.count("-map"), 2)

        for filename in ("master.wav", "master.flac"):
            with self.subTest(filename=filename):
                manifest = make_manifest(self.project_root, filename)
                master = manifest["master"]
                assert isinstance(master, dict)
                master["path"] = str((self.project_root / "masters" / filename).resolve())
                command = build_ffmpeg_command(manifest, self.project_root / f"{filename}.mp4")
                self.assertEqual(command[command.index("-c:a") + 1], "aac")
                self.assertEqual(command[command.index("-b:a") + 1], "320k")
                self.assertEqual(command.count("-c:a"), 1)
                self.assertNotIn("-af", command)

    def test_rejects_invalid_or_incomplete_inputs_before_encoding(self) -> None:
        """Break caught: assembling an invalid EDL, missing source, or physically short clip."""
        no_acceptance = make_manifest(self.project_root, "master.wav")
        shots = no_acceptance["shots"]
        assert isinstance(shots, list) and isinstance(shots[0], dict)
        del shots[0]["accepted_source"]

        invalid_coverage = make_manifest(self.project_root, "master.wav")
        invalid_shots = invalid_coverage["shots"]
        assert isinstance(invalid_shots, list) and isinstance(invalid_shots[-1], dict)
        invalid_shots[-1]["timeline"] = {"start_frame": 150, "end_frame": 299}

        missing_clip = make_manifest(self.project_root, "master.wav")
        missing_shots = missing_clip["shots"]
        assert isinstance(missing_shots, list) and isinstance(missing_shots[0], dict)
        missing_source = missing_shots[0]["accepted_source"]
        assert isinstance(missing_source, dict)
        missing_source["path"] = "clips/not present.mp4"

        short_clip = make_manifest(self.project_root, "master.wav")
        short_shots = short_clip["shots"]
        assert isinstance(short_shots, list) and isinstance(short_shots[0], dict)
        short_source = short_shots[0]["accepted_source"]
        assert isinstance(short_source, dict)
        short_source["trim_start_seconds"] = "10.000"
        short_source["trim_end_seconds"] = "25.000"

        for name, manifest in (
            ("accepted source", no_acceptance),
            ("timeline", invalid_coverage),
            ("does not exist", missing_clip),
            ("coverage", short_clip),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(AssemblyError, name):
                    assemble(manifest, self.project_root, self.project_root / f"rejected {name}.mp4")

    def test_rejects_master_that_cannot_cover_the_final_video(self) -> None:
        """Break caught: trusting stale manifest duration while the real soundtrack ends early."""
        manifest = make_manifest(self.project_root, "short master.wav")

        with self.assertRaisesRegex(AssemblyError, "Master audio coverage"):
            assemble(manifest, self.project_root, self.project_root / "short master rejected.mp4")

    def test_rejects_master_hash_mismatch_before_ffmpeg_work(self) -> None:
        """Break caught: assembling media whose bytes do not match the approved master."""
        manifest = make_manifest(self.project_root, "master.wav")
        master = manifest["master"]
        assert isinstance(master, dict)
        master["sha256"] = "0" * 64
        output = self.project_root / "hash mismatch rejected.mp4"

        with self.assertRaisesRegex(AssemblyError, "SHA-256"):
            assemble(manifest, self.project_root, output)

        self.assertFalse(output.exists())

    def test_rejects_stale_master_duration_and_stream_facts(self) -> None:
        """Break caught: trusting metadata that describes a different master timeline."""
        longer = make_manifest(self.project_root, "long master.wav")
        longer_output = self.project_root / "long stale master rejected.mp4"
        with self.assertRaisesRegex(AssemblyError, "duration metadata"):
            assemble(longer, self.project_root, longer_output)
        self.assertFalse(longer_output.exists())

        for field, value, label in (
            ("sample_rate", 44_100, "sample rate"),
            ("channels", 2, "channel count"),
        ):
            with self.subTest(field=field):
                stale = make_manifest(self.project_root, "master.wav")
                master = stale["master"]
                assert isinstance(master, dict)
                master[field] = value
                output = self.project_root / f"stale {field} rejected.mp4"
                with self.assertRaisesRegex(AssemblyError, label):
                    assemble(stale, self.project_root, output)
                self.assertFalse(output.exists())

    def test_preserves_fractional_rate_and_ceil_frame_for_partial_final_frame(self) -> None:
        """Break caught: rounding 30000/1001 or dropping the partial final timeline frame."""
        manifest = make_fractional_rate_manifest(self.project_root, "fractional master.wav")
        output = self.project_root / "fractional frame delivery.mp4"

        result = assemble(manifest, self.project_root, output)

        probe = video_probe(output)
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        self.assertEqual(video["avg_frame_rate"], "30000/1001")
        self.assertEqual(int(video["nb_read_frames"]), 900)
        self.assertEqual(result["frame_count"], 900)
        self.assertEqual(result["probed_frame_rate"], {"fps_num": 30_000, "fps_den": 1_001})
        self.assertTrue(Path(result["work_directory"]).is_dir())
        self.assertTrue(Path(result["mux_candidate_path"]).is_file())

    def test_rejects_probed_frame_rate_that_differs_from_manifest(self) -> None:
        """Break caught: returning the declared rate without checking the mux candidate."""
        import scripts.assemble_music_video as assembler_module

        manifest = make_manifest(self.project_root, "master.wav")
        output = self.project_root / "rate mismatch rejected.mp4"
        real_output_facts = assembler_module._output_facts

        def mismatched_facts(path: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
            probe, video, audio = real_output_facts(path)
            mismatched_video = dict(video)
            mismatched_video["avg_frame_rate"] = "30/1"
            return probe, mismatched_video, audio

        with patch("scripts.assemble_music_video._output_facts", side_effect=mismatched_facts):
            with self.assertRaisesRegex(AssemblyError, "frame rate"):
                assemble(manifest, self.project_root, output)

        self.assertFalse(output.exists())

    def test_post_mux_rejection_never_creates_intended_output(self) -> None:
        """Break caught: leaving a rejected mux candidate at the delivery path."""
        manifest = make_manifest(self.project_root, "master.wav")
        output = self.project_root / "post mux rejected.mp4"
        probed_paths: list[Path] = []

        def reject_written_candidate(path: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
            probed_paths.append(path)
            self.assertTrue(path.is_file())
            raise AssemblyError("forced post-mux rejection")

        with patch(
            "scripts.assemble_music_video._output_facts",
            side_effect=reject_written_candidate,
        ):
            with self.assertRaisesRegex(AssemblyError, "post-mux rejection"):
                assemble(manifest, self.project_root, output)

        self.assertFalse(output.exists())
        self.assertEqual(probed_paths[0].name, "candidate.mp4")
        self.assertTrue(probed_paths[0].exists())

    def test_publish_race_preserves_destination_byte_for_byte(self) -> None:
        """Break caught: overwriting a file that wins the destination during publication."""
        manifest = make_manifest(self.project_root, "master.wav")
        output = self.project_root / "publish race.mp4"
        winner = b"race winner remains intact"
        real_link = os.link

        def win_publish_race(source: Path, destination: Path) -> None:
            Path(destination).write_bytes(winner)
            real_link(source, destination)

        with patch("scripts.assemble_music_video.os.link", side_effect=win_publish_race):
            with self.assertRaisesRegex(AssemblyError, "already exists"):
                assemble(manifest, self.project_root, output)

        self.assertEqual(output.read_bytes(), winner)

    def test_rejects_absent_tools_escaped_paths_and_existing_output(self) -> None:
        """Break caught: shell escape, tool failure, or overwrite of an existing delivery."""
        escaped = make_manifest(self.project_root, "master.wav")
        shots = escaped["shots"]
        assert isinstance(shots, list) and isinstance(shots[0], dict)
        source = shots[0]["accepted_source"]
        assert isinstance(source, dict)
        source["path"] = "clips/../masters/master.wav"
        with self.assertRaises(AssemblyError):
            assemble(escaped, self.project_root, self.project_root / "escaped.mp4")

        manifest = make_manifest(self.project_root, "master.wav")
        existing = self.project_root / "existing output.mp4"
        existing.write_bytes(b"keep me")
        with self.assertRaisesRegex(AssemblyError, "already exists"):
            assemble(manifest, self.project_root, existing)
        self.assertEqual(existing.read_bytes(), b"keep me")

        with patch("scripts.assemble_music_video.shutil.which", return_value=None):
            with self.assertRaisesRegex(AssemblyError, "ffmpeg"):
                assemble(manifest, self.project_root, self.project_root / "no ffmpeg.mp4")

    def test_cli_runs_directly_outside_the_repository(self) -> None:
        """Break caught: direct script execution cannot import its sibling validator."""
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "assemble_music_video.py"), "--help"],
            cwd="/private/tmp",
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--project-root", completed.stdout)


if __name__ == "__main__":
    unittest.main()
