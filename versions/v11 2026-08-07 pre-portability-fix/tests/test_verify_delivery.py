from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_delivery import verify_delivery


def run(arguments: list[str]) -> None:
    subprocess.run(arguments, check=True, capture_output=True)


def make_manifest(master: Path) -> dict[str, object]:
    return {
        "master": {
            "sha256": hashlib.sha256(master.read_bytes()).hexdigest(),
            "decoded_duration_seconds": 30.0,
            "channels": 2,
        },
        "delivery": {
            "geometry": {"width": 160, "height": 90},
            "frame_rate": {"fps_num": 10, "fps_den": 1},
            "audio_policy": {
                "source": "supplied_master",
                "start_seconds": "0.000",
                "clip_audio": "discard",
                "codec_policy": "copy_compatible_else_aac_320k",
            },
        },
    }


class VerifyDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            raise unittest.SkipTest("FFmpeg integration tests require ffmpeg and ffprobe")
        cls.fixture_dir = Path(
            tempfile.mkdtemp(prefix="scenario-seedance-delivery-tests-", dir="/private/tmp")
        )
        cls.master = cls.fixture_dir / "approved master.m4a"
        run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=880:sample_rate=48000:duration=30",
                "-ac", "2", "-c:a", "aac", "-b:a", "192k", "-y", str(cls.master),
            ]
        )
        cls.manifest = make_manifest(cls.master)
        cls.valid = cls.fixture_dir / "valid copied master.mp4"
        cls._make_delivery(cls.valid, audio_input=cls.master, audio_codec="copy")

    @classmethod
    def _make_delivery(
        cls,
        output: Path,
        *,
        audio_input: Path | None,
        audio_codec: str | None = "copy",
        video_duration: int = 30,
        video_rate: int = 10,
        geometry: str = "160x90",
        audio_duration: int | None = None,
        audio_input_duration: int | None = None,
        audio_bitrate: str | None = None,
        extra_audio: bool = False,
    ) -> None:
        arguments = [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            f"color=c=black:s={geometry}:r={video_rate}:d={video_duration}",
        ]
        if audio_input is not None:
            if audio_input_duration is not None:
                arguments.extend(["-t", str(audio_input_duration)])
            arguments.extend(["-i", str(audio_input)])
        if extra_audio:
            arguments.extend([
                "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=30",
            ])
        arguments.extend(["-map", "0:v:0"])
        if audio_input is not None:
            arguments.extend(["-map", "1:a:0"])
        if extra_audio:
            arguments.extend(["-map", "2:a:0"])
        arguments.extend(["-c:v", "mpeg4"])
        if audio_input is not None and audio_codec is not None:
            arguments.extend(["-c:a", audio_codec])
            if audio_bitrate is not None:
                arguments.extend(["-b:a", audio_bitrate])
        if audio_duration is not None:
            arguments.extend(["-t", str(audio_duration)])
        arguments.extend(["-y", str(output)])
        run(arguments)

    @classmethod
    def _make_tone(cls, name: str, *, channels: int = 2) -> Path:
        output = cls.fixture_dir / name
        run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "sine=frequency=330:sample_rate=48000:duration=30",
                "-ac", str(channels), "-c:a", "aac", "-b:a", "192k", "-y", str(output),
            ]
        )
        return output

    @classmethod
    def _make_wav_master(cls, name: str, frequency: int = 660) -> Path:
        output = cls.fixture_dir / name
        run(
            [
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration=30",
                "-ac", "2", "-c:a", "pcm_s16le", "-y", str(output),
            ]
        )
        return output

    def test_accepts_stream_copied_master_with_matching_elementary_audio_hash(self) -> None:
        """Break caught: claiming stream copy without comparing compressed elementary audio."""
        result = verify_delivery(self.valid, self.master, self.manifest)

        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["audio_bit_exact"])
        self.assertEqual(result["technical"]["audio_integrity"]["mode"], "stream_copy")
        self.assertEqual(
            result["technical"]["audio_integrity"]["final_elementary_sha256"],
            result["technical"]["audio_integrity"]["master_elementary_sha256"],
        )

    def test_rejects_wrong_delivery_duration(self) -> None:
        """Break caught: accepting a delivery whose soundtrack was truncated."""
        truncated = self.fixture_dir / "wrong duration.mp4"
        self._make_delivery(truncated, audio_input=self.master, audio_duration=28)

        result = verify_delivery(truncated, self.master, self.manifest)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["duration_compatible"])

    def test_rejects_missing_video_or_audio_stream(self) -> None:
        """Break caught: treating an audio-only or video-only file as a delivery."""
        audio_only = self.fixture_dir / "audio only.m4a"
        run(["ffmpeg", "-v", "error", "-i", str(self.master), "-c", "copy", "-y", str(audio_only)])
        video_only = self.fixture_dir / "video only.mp4"
        self._make_delivery(video_only, audio_input=None)

        for path, check in ((audio_only, "single_video_stream"), (video_only, "single_audio_stream")):
            with self.subTest(path=path.name):
                result = verify_delivery(path, self.master, self.manifest)
                self.assertFalse(result["passed"])
                self.assertFalse(result["checks"][check])

    def test_rejects_multiple_audio_streams(self) -> None:
        """Break caught: accidental generated clip audio surviving alongside the master."""
        multiple = self.fixture_dir / "multiple audio.mp4"
        self._make_delivery(multiple, audio_input=self.master, extra_audio=True)

        result = verify_delivery(multiple, self.master, self.manifest)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["single_audio_stream"])
        self.assertIn("multiple audio", " ".join(result["warnings"]).lower())

    def test_rejects_channel_geometry_and_frame_rate_mismatches(self) -> None:
        """Break caught: accepting files that do not match the approved delivery contract."""
        mono_master = self._make_tone("mono accidental audio.m4a", channels=1)
        mono = self.fixture_dir / "mono delivery.mp4"
        self._make_delivery(mono, audio_input=mono_master, audio_codec="copy")
        wrong_video = self.fixture_dir / "wrong geometry fps.mp4"
        self._make_delivery(wrong_video, audio_input=self.master, video_rate=12, geometry="120x90")

        mono_result = verify_delivery(mono, self.master, self.manifest)
        video_result = verify_delivery(wrong_video, self.master, self.manifest)

        self.assertFalse(mono_result["checks"]["audio_channels_match"])
        self.assertFalse(video_result["checks"]["geometry_match"])
        self.assertFalse(video_result["checks"]["frame_rate_match"])

    def test_detects_a_single_generated_audio_track(self) -> None:
        """Break caught: a generated soundtrack replacing the supplied master unnoticed."""
        generated = self._make_tone("generated soundtrack.m4a")
        final = self.fixture_dir / "generated audio final.mp4"
        self._make_delivery(final, audio_input=generated, audio_codec="copy")

        result = verify_delivery(final, self.master, self.manifest)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["generated_audio_absent"])
        self.assertFalse(result["checks"]["audio_bit_exact"])

    def test_reports_transcode_as_non_bit_exact_while_preserving_timing(self) -> None:
        """Break caught: falsely promising byte identity after the documented AAC delivery encode."""
        wav_master = self._make_wav_master("lossless master.wav")
        transcoded = self.fixture_dir / "aac transcode final.mp4"
        self._make_delivery(
            transcoded,
            audio_input=wav_master,
            audio_codec="aac",
            audio_bitrate="320k",
        )

        result = verify_delivery(transcoded, wav_master, make_manifest(wav_master))

        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["audio_timing_preserved"])
        self.assertIsNone(result["checks"]["audio_bit_exact"])
        self.assertEqual(result["technical"]["audio_integrity"]["mode"], "transcoded")
        self.assertTrue(result["checks"].get("derived_audio_matches_master"))
        self.assertIn("not bit-exact", " ".join(result["warnings"]).lower())

    def test_rejects_truncated_transcoded_audio_when_video_remains_full_length(self) -> None:
        """Break caught: using video or container duration as proof that final audio is complete."""
        wav_master = self._make_wav_master("duration master.wav", frequency=700)
        final = self.fixture_dir / "full video truncated audio.mp4"
        self._make_delivery(
            final,
            audio_input=wav_master,
            audio_codec="aac",
            audio_bitrate="320k",
            audio_input_duration=27,
        )

        result = verify_delivery(final, wav_master, make_manifest(wav_master))

        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"].get("audio_duration_compatible"), False)

    def test_rejects_unrelated_aac_replacement_on_transcode_path(self) -> None:
        """Break caught: calling timing and channels proof that transcoded audio came from the master."""
        wav_master = self._make_wav_master("provenance master.wav", frequency=700)
        unrelated = self._make_wav_master("unrelated replacement.wav", frequency=330)
        final = self.fixture_dir / "unrelated replacement final.mp4"
        self._make_delivery(
            final,
            audio_input=unrelated,
            audio_codec="aac",
            audio_bitrate="320k",
        )

        result = verify_delivery(final, wav_master, make_manifest(wav_master))

        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"].get("derived_audio_matches_master"), False)
        self.assertFalse(result["checks"]["generated_audio_absent"])

    def test_rejects_unauthorized_codec_paths_and_audio_policies(self) -> None:
        """Break caught: accepting codec changes or manifests without the exact approved audio path."""
        wav_master = self._make_wav_master("codec policy master.wav", frequency=710)
        alac_final = self.fixture_dir / "unauthorized alac final.mp4"
        self._make_delivery(alac_final, audio_input=wav_master, audio_codec="alac")
        aac_to_mp3 = self.fixture_dir / "unauthorized mp3 final.mp4"
        self._make_delivery(aac_to_mp3, audio_input=self.master, audio_codec="libmp3lame")

        for name, final, master in (
            ("lossless master must become AAC", alac_final, wav_master),
            ("AAC master must remain AAC", aac_to_mp3, self.master),
        ):
            with self.subTest(name=name):
                result = verify_delivery(final, master, make_manifest(master))
                self.assertFalse(result["passed"])
                self.assertEqual(result["checks"].get("audio_codec_path_authorized"), False)

        for name, audio_policy in (
            ("missing", None),
            ("wrong", {"source": "supplied_master", "start_seconds": "0.000", "clip_audio": "discard", "codec_policy": "always_aac"}),
        ):
            with self.subTest(audio_policy=name):
                manifest = make_manifest(self.master)
                delivery = manifest["delivery"]
                assert isinstance(delivery, dict)
                if audio_policy is None:
                    del delivery["audio_policy"]
                else:
                    delivery["audio_policy"] = audio_policy
                result = verify_delivery(self.valid, self.master, manifest)
                self.assertFalse(result["passed"])
                self.assertEqual(result["checks"].get("audio_policy_authorized"), False)

    def test_returns_failed_report_when_master_hash_open_fails(self) -> None:
        """Break caught: an unreadable or raced master escaping instead of returning a failed report."""
        with patch("scripts.verify_delivery._sha256", side_effect=PermissionError("denied")):
            try:
                result = verify_delivery(self.valid, self.master, self.manifest)
            except PermissionError as error:
                self.fail(f"Verifier allowed master hash failure to escape: {error}")

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["source_master_sha256_unchanged"])
        self.assertIn("hash", " ".join(result["warnings"]).lower())

    def test_rejects_master_replaced_during_verification(self) -> None:
        """Break caught: a master changing after its initial hash while verification is running."""
        master_hash_calls = 0

        def raced_sha256(path: Path) -> str:
            nonlocal master_hash_calls
            if path == self.master:
                master_hash_calls += 1
                if master_hash_calls > 1:
                    return "f" * 64
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with patch("scripts.verify_delivery._sha256", side_effect=raced_sha256):
            result = verify_delivery(self.valid, self.master, self.manifest)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["source_master_sha256_unchanged"])
        self.assertIn("changed during verification", " ".join(result["warnings"]).lower())


if __name__ == "__main__":
    unittest.main()
