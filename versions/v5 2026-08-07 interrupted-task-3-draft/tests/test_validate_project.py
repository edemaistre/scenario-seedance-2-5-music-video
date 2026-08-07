from __future__ import annotations

import copy
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path

from scripts.validate_project import Diagnostic, ManifestJsonError, load_manifest, main, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def valid_manifest(duration_seconds: Decimal) -> dict[str, object]:
    """Build a literal canonical manifest, independent of validator helpers.

    Break caught by acceptance tests: changing the documented manifest shape or
    making target-frame coverage depend on float rounding.
    """
    data = fixture("valid_30s_project.json")
    master = data["master"]
    assert isinstance(master, dict)
    master["duration_seconds"] = float(duration_seconds)
    delivery = data["delivery"]
    assert isinstance(delivery, dict)
    frame_rate = delivery["frame_rate"]
    assert isinstance(frame_rate, dict)
    target = math.ceil(duration_seconds * frame_rate["fps_num"] / frame_rate["fps_den"])
    shots: list[dict[str, object]] = []
    start = 0
    index = 1
    while start < target:
        end = min(start + 720, target)
        edit_duration = Decimal(end - start) * Decimal(frame_rate["fps_den"]) / Decimal(frame_rate["fps_num"])
        request_duration = max(4, math.ceil(edit_duration))
        source_start = Decimal("0.000")
        source_end = Decimal(request_duration)
        shot = copy.deepcopy(data["shots"][0])
        assert isinstance(shot, dict)
        shot["id"] = f"shot-{index:03d}"
        shot["timeline"] = {"start_frame": start, "end_frame": end}
        shot["source"] = {
            "path": f"clips/shot-{index:03d}.mp4",
            "trim_start_seconds": f"{source_start:.3f}",
            "trim_end_seconds": f"{source_end:.3f}",
        }
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["duration"] = request_duration
        shots.append(shot)
        start = end
        index += 1
    data["shots"] = shots
    return data


def error_codes(data: dict[str, object]) -> set[str]:
    return {diagnostic.code for diagnostic in validate_manifest(data) if diagnostic.severity == "error"}


class ValidateProjectTests(unittest.TestCase):
    def test_accepts_complete_projects_at_required_durations(self) -> None:
        """Break caught: rejecting valid minimum, standard, and long complete timelines."""
        cases = {
            "valid_30s_project.json": Decimal("30"),
            "generated_60": Decimal("60"),
            "valid_157s_project.json": Decimal("157"),
            "generated_360": Decimal("360"),
        }
        for name, duration in cases.items():
            with self.subTest(name=name):
                data = fixture(name) if name.startswith("valid_") else valid_manifest(duration)
                self.assertEqual(validate_manifest(data), [])
                delivery = data["delivery"]
                assert isinstance(delivery, dict)
                frame_rate = delivery["frame_rate"]
                assert isinstance(frame_rate, dict)
                expected_target = math.ceil(duration * frame_rate["fps_num"] / frame_rate["fps_den"])
                shots = data["shots"]
                assert isinstance(shots, list)
                last = shots[-1]
                assert isinstance(last, dict)
                timeline = last["timeline"]
                assert isinstance(timeline, dict)
                self.assertEqual(timeline["end_frame"], expected_target)

    def test_accepts_documented_auto_operation(self) -> None:
        """Break caught: rejecting the only documented exception to fixed Seedance duration."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        generation["mode"] = "auto"
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["duration"] = "Auto"

        self.assertEqual(validate_manifest(data), [])

    def test_rejects_master_below_thirty_seconds(self) -> None:
        """Break caught: permitting a master that Task 2 would have rejected."""
        data = valid_manifest(Decimal("30"))
        master = data["master"]
        assert isinstance(master, dict)
        master["duration_seconds"] = 29.999

        self.assertIn("master.duration.minimum", error_codes(data))

    def test_rejects_wrong_model_and_parameter_contract(self) -> None:
        """Break caught: sending unsupported model or unrecognized Scenario parameters."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        generation["model_id"] = "model_other"
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["audio"] = []

        codes = error_codes(data)
        self.assertIn("generation.model_id", codes)
        self.assertIn("generation.parameters.keys", codes)

    def test_rejects_generated_audio_and_non_array_scenario_fields(self) -> None:
        """Break caught: allowing audio generation or scalar fields where the MCP contract needs arrays."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        generation["tags"] = "music-video"
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["generateAudio"] = 0
        parameters["referenceImages"] = "references/artist.png"

        codes = error_codes(data)
        self.assertIn("generation.tags.array", codes)
        self.assertIn("generation.parameters.generate_audio", codes)
        self.assertIn("generation.parameters.reference_images.array", codes)

    def test_rejects_duration_outside_fixed_seedance_bounds(self) -> None:
        """Break caught: requesting an invalid fixed-duration Seedance generation."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["duration"] = 3

        self.assertIn("generation.parameters.duration", error_codes(data))

    def test_rejects_duplicate_shot_ids(self) -> None:
        """Break caught: accepting duplicate IDs that make acceptance and recovery ambiguous."""
        data = valid_manifest(Decimal("60"))
        shots = data["shots"]
        assert isinstance(shots, list)
        first, second = shots
        assert isinstance(first, dict) and isinstance(second, dict)
        second["id"] = first["id"]

        self.assertIn("shots.id.duplicate", error_codes(data))

    def test_rejects_gaps_and_unintended_overlaps(self) -> None:
        """Break caught: allowing a timeline that cannot be assembled as one contiguous visual track."""
        gap = fixture("invalid_gap_project.json")
        overlap = valid_manifest(Decimal("60"))
        shots = overlap["shots"]
        assert isinstance(shots, list)
        second = shots[1]
        assert isinstance(second, dict)
        timeline = second["timeline"]
        assert isinstance(timeline, dict)
        timeline["start_frame"] = 719

        self.assertIn("timeline.gap", error_codes(gap))
        self.assertIn("timeline.overlap", error_codes(overlap))

    def test_rejects_invalid_source_trim_and_unsafe_local_path(self) -> None:
        """Break caught: assembly receiving backward trims, too-short coverage, or a path outside the project."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        source = shot["source"]
        assert isinstance(source, dict)
        source["path"] = "../outside.mp4"
        source["trim_start_seconds"] = "30.000"
        source["trim_end_seconds"] = "29.000"

        codes = error_codes(data)
        self.assertIn("source.path", codes)
        self.assertIn("source.trim.range", codes)

    def test_rejects_incomplete_final_frame_coverage(self) -> None:
        """Break caught: accepting a final visual track shorter than ceil(master duration times fps)."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        timeline = shot["timeline"]
        assert isinstance(timeline, dict)
        timeline["end_frame"] = 719

        self.assertIn("timeline.final_coverage", error_codes(data))

    def test_rejects_inconsistent_delivery_properties(self) -> None:
        """Break caught: mixing different geometry, aspect ratio, resolution, or frame rate within one delivery."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        expected_output = shot["expected_output"]
        assert isinstance(expected_output, dict)
        expected_output["resolution"] = "480p"
        expected_output["aspect_ratio"] = "4:3"
        geometry = expected_output["geometry"]
        assert isinstance(geometry, dict)
        geometry["width"] = 640
        frame_rate = expected_output["frame_rate"]
        assert isinstance(frame_rate, dict)
        frame_rate["fps_num"] = 30

        codes = error_codes(data)
        self.assertIn("expected_output.resolution", codes)
        self.assertIn("expected_output.aspect_ratio", codes)
        self.assertIn("expected_output.geometry", codes)
        self.assertIn("expected_output.frame_rate", codes)

    def test_requires_supplied_pack_or_approved_generated_pack(self) -> None:
        """Break caught: paying for Seedance work without usable supplied references or approved generated references."""
        missing = valid_manifest(Decimal("30"))
        missing["reference_pack"] = {"source": "generated", "approval": "pending", "assets": []}
        supplied = valid_manifest(Decimal("30"))
        supplied["reference_pack"] = {
            "source": "supplied",
            "assets": [{"id": "artist", "path": "references/artist.png", "roles": ["performer"]}],
        }
        generated = valid_manifest(Decimal("30"))
        generated["reference_pack"] = {
            "source": "generated",
            "approval": "approved",
            "assets": [{"id": "world", "path": "references/world.png", "roles": ["world"]}],
        }

        self.assertIn("reference_pack.approval", error_codes(missing))
        self.assertEqual(validate_manifest(supplied), [])
        self.assertEqual(validate_manifest(generated), [])

    def test_rejects_invented_lyrics_marked_certain(self) -> None:
        """Break caught: treating an unverified Scenario transcription as supplied, certain lyrics."""
        data = valid_manifest(Decimal("30"))
        data["lyrics"] = {
            "state": "scenario_transcription",
            "certainty": "certain",
            "transcript_path": "analysis/transcript.txt",
        }

        self.assertIn("lyrics.certainty", error_codes(data))

    def test_accepts_all_documented_lyric_states(self) -> None:
        """Break caught: making provided, Scenario transcription, instrumental, or uncertainty impossible to express."""
        cases = [
            {"state": "provided", "certainty": "certain", "source_path": "lyrics/source.txt", "sha256": "a" * 64},
            {"state": "scenario_transcription", "certainty": "uncertain", "transcript_path": "analysis/transcript.txt"},
            {"state": "instrumental"},
            {"state": "uncertain", "reason": "Vocal content is masked."},
        ]
        for lyrics in cases:
            with self.subTest(state=lyrics["state"]):
                data = valid_manifest(Decimal("30"))
                data["lyrics"] = lyrics
                self.assertEqual(validate_manifest(data), [])

    def test_returns_frozen_sorted_diagnostics_without_control_character_echoes(self) -> None:
        """Break caught: nondeterministic diagnostics or user-controlled line breaks in an error stream."""
        data = valid_manifest(Decimal("30"))
        data["schema_version"] = 2
        data["shots"] = "not an array\nwith injected output"

        diagnostics = validate_manifest(data)
        self.assertTrue(diagnostics)
        self.assertTrue(all(isinstance(item, Diagnostic) for item in diagnostics))
        self.assertEqual(diagnostics, sorted(diagnostics))
        with self.assertRaises(Exception):
            diagnostics[0].code = "changed"  # type: ignore[misc]
        rendered = "\n".join(item.message for item in diagnostics)
        self.assertNotIn("not an array\nwith injected output", rendered)
        self.assertNotIn("\x00", rendered)

    def test_rejects_duplicate_keys_nonfinite_json_and_non_object_roots(self) -> None:
        """Break caught: normalizing ambiguous or nonportable JSON before the manifest is validated."""
        artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-manifest-tests-", dir="/private/tmp"))
        duplicate = artifact_dir / "duplicate.json"
        nonfinite = artifact_dir / "nonfinite.json"
        scalar = artifact_dir / "scalar.json"
        duplicate.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
        nonfinite.write_text('{"schema_version": NaN}', encoding="utf-8")
        scalar.write_text('["not a manifest"]', encoding="utf-8")

        for path in (duplicate, nonfinite, scalar):
            with self.subTest(path=path.name):
                with self.assertRaises(ManifestJsonError):
                    load_manifest(path)

    def test_cli_has_contract_and_json_error_exit_codes(self) -> None:
        """Break caught: callers being unable to distinguish a bad manifest from unreadable or invalid JSON."""
        artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-manifest-cli-tests-", dir="/private/tmp"))
        invalid_path = artifact_dir / "invalid.json"
        valid_path = artifact_dir / "valid.json"
        bad_json_path = artifact_dir / "bad.json"
        invalid_path.write_text(json.dumps(fixture("invalid_gap_project.json")), encoding="utf-8")
        valid_path.write_text(json.dumps(fixture("valid_30s_project.json")), encoding="utf-8")
        bad_json_path.write_text('{"schema_version":', encoding="utf-8")

        for expected, path in ((1, invalid_path), (0, valid_path), (2, bad_json_path)):
            with self.subTest(expected=expected, path=path.name):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = main([str(path)])
                self.assertEqual(exit_code, expected)
                self.assertEqual(stdout.getvalue(), "")
                if expected:
                    self.assertTrue(stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
