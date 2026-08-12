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
from scripts.verify_delivery import preferred_temp_root


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
    master["decoded_duration_seconds"] = float(duration_seconds)
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
        shot["accepted_source"] = {
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


def canonical_planning() -> dict[str, object]:
    """Return the literal per-shot planning contract used by validator tests."""
    return {
        "section": "chorus 1",
        "music_or_lyric_function": "Introduce the main hook.",
        "sync_events": [
            {
                "master_frame": 0,
                "description": "Verified chorus downbeat.",
                "verified": True,
            }
        ],
        "information_density": "high",
        "handles": {"opening_seconds": "0.000", "closing_seconds": "0.000"},
        "shot_family": "performance anchor",
        "subject": "approved performer",
        "action": "The performer advances through the space.",
        "shot_size": "medium wide",
        "camera_move": "slow forward track",
        "lens_or_optics": "50 mm spherical",
        "lighting": "soft directional key",
        "palette": "approved treatment palette",
        "realism": "cinematic realism",
        "texture": "clean natural texture",
        "film_stock_or_grain": "none",
        "opening_composition": "Performer centered with forward space.",
        "closing_state": "Performer holds frame-right with a stable camera.",
        "screen_direction": "left to right",
        "motion_vector": "forward",
        "transition_logic": "Hard cut on the verified downbeat.",
        "continuity": {
            "identity": ["match the approved performer"],
            "wardrobe": ["preserve approved wardrobe"],
            "product": [],
            "props": [],
            "world": ["preserve the approved location"],
            "state": ["maintain established screen direction"],
        },
        "reference_roles": [
            {
                "tag": "@image1",
                "scenario_asset_id": "asset_i",
                "role": "performer identity",
                "inherits": ["identity", "wardrobe"],
                "excludes": ["background", "text"],
            },
            {
                "tag": "@audio1",
                "scenario_asset_id": "asset_a",
                "role": "timing and energy",
                "inherits": ["pulse", "phrase energy"],
                "excludes": ["voice", "lyrics", "soundtrack"],
            },
        ],
    }


def canonical_attempt(
    *,
    attempt_id: str = "attempt-001",
    acceptance_status: str = "accepted",
    reroll_diagnosis: str | None = None,
) -> dict[str, object]:
    """Return one literal paid-attempt record with nullable pre-call identifiers."""
    terminal = acceptance_status in {"accepted", "rejected", "failed"}
    return {
        "id": attempt_id,
        "schema_checked_on": "2026-08-07",
        "dry_run_estimate": {"amount": 1, "unit": "SYNTHETIC_EXAMPLE_ONLY"},
        "approval": {"status": "approved", "record": "User approved the exact request."},
        "job_id": "job_demo" if acceptance_status != "not_run" else None,
        "output_id": "asset_out" if acceptance_status in {"accepted", "rejected"} else None,
        "known_cost": {"amount": 1, "unit": "SYNTHETIC_EXAMPLE_ONLY"} if terminal else None,
        "acceptance": {
            "status": acceptance_status,
            "reason": "The inspected output reached a terminal review state." if terminal else None,
        },
        "reroll_diagnosis": reroll_diagnosis,
    }


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
        data = valid_manifest(Decimal("60"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        generation["mode"] = "edit"
        generation["parameters"] = {
            "prompt": "@video1 supplies the accepted source. Preserve all content except the bounded repair.",
            "duration": -1,
            "resolution": "720p",
            "outputFormat": "mp4",
            "generateAudio": False,
            "referenceVideos": ["asset_v"],
        }
        reference_pack = data["reference_pack"]
        assert isinstance(reference_pack, dict)
        assets = reference_pack["assets"]
        assert isinstance(assets, list)
        assets.append(
            {
                "id": "accepted-video",
                "path": "clips/accepted-video.mp4",
                "scenario_asset_id": "asset_v",
                "roles": ["bounded edit source"],
            }
        )
        planning = shot["planning"]
        assert isinstance(planning, dict)
        planning["reference_roles"] = [
            {
                "tag": "@video1",
                "scenario_asset_id": "asset_v",
                "role": "bounded edit source",
                "inherits": ["source geometry", "preserved content"],
                "excludes": ["source audio"],
            }
        ]

        self.assertEqual(validate_manifest(data), [])

    def test_accepts_auto_duration_for_non_edit_mode(self) -> None:
        """Break caught: treating the global Seedance Auto sentinel as an edit-only value."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["duration"] = -1

        self.assertEqual(validate_manifest(data), [])

    def test_rejects_master_below_thirty_seconds(self) -> None:
        """Break caught: permitting a master that Task 2 would have rejected."""
        data = valid_manifest(Decimal("30"))
        master = data["master"]
        assert isinstance(master, dict)
        master["decoded_duration_seconds"] = 29.999

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
        parameters["format"] = "mp4"
        parameters["negativePrompt"] = "watermark"

        codes = error_codes(data)
        self.assertIn("generation.model_id", codes)
        self.assertIn("generation.parameters.unknown", codes)

    def test_rejects_generated_audio_and_non_array_scenario_fields(self) -> None:
        """Break caught: allowing audio generation or scalar fields where the MCP contract needs arrays."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["generateAudio"] = 0
        parameters["referenceImages"] = "asset_i"
        parameters["referenceAudio"] = "asset_a"

        codes = error_codes(data)
        self.assertIn("generation.parameters.generate_audio", codes)
        self.assertIn("generation.parameters.reference_images.array", codes)
        self.assertIn("generation.parameters.reference_audio.array", codes)

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

        parameters["duration"] = 31
        self.assertIn("generation.parameters.duration", error_codes(data))

    def test_rejects_generation_too_short_without_accepted_source(self) -> None:
        """Break caught: deferring generation feasibility until after a clip has been accepted."""
        fixed = valid_manifest(Decimal("30"))
        fixed_shot = fixed["shots"][0]
        assert isinstance(fixed_shot, dict)
        del fixed_shot["accepted_source"]
        fixed_generation = fixed_shot["generation"]
        assert isinstance(fixed_generation, dict)
        fixed_parameters = fixed_generation["parameters"]
        assert isinstance(fixed_parameters, dict)
        fixed_parameters["duration"] = 29

        auto = valid_manifest(Decimal("31"))
        auto_shots = auto["shots"]
        assert isinstance(auto_shots, list)
        auto_shot = auto_shots[0]
        assert isinstance(auto_shot, dict)
        auto_shot["timeline"] = {"start_frame": 0, "end_frame": 744}
        del auto_shot["accepted_source"]
        auto_generation = auto_shot["generation"]
        assert isinstance(auto_generation, dict)
        auto_parameters = auto_generation["parameters"]
        assert isinstance(auto_parameters, dict)
        auto_parameters["duration"] = -1
        auto["shots"] = [auto_shot]

        self.assertIn("generation.parameters.duration.coverage", error_codes(fixed))
        self.assertIn("generation.parameters.duration.coverage", error_codes(auto))

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

    def test_rejects_shots_out_of_declared_chronological_order(self) -> None:
        """Break caught: silently sorting an EDL whose array order disagrees with its frame order."""
        data = valid_manifest(Decimal("60"))
        shots = data["shots"]
        assert isinstance(shots, list)
        data["shots"] = list(reversed(shots))

        self.assertIn("timeline.order", error_codes(data))

    def test_rejects_invalid_source_trim_and_unsafe_local_path(self) -> None:
        """Break caught: assembly receiving backward trims, too-short coverage, or a path outside the project."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        source = shot["accepted_source"]
        assert isinstance(source, dict)
        source["path"] = "../outside.mp4"
        source["trim_start_seconds"] = "30.000"
        source["trim_end_seconds"] = "29.000"

        codes = error_codes(data)
        self.assertIn("source.path", codes)
        self.assertIn("source.trim.range", codes)

    def test_rejects_windows_style_path_traversal(self) -> None:
        """Break caught: treating a Windows parent path as a harmless filename on POSIX."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        source = shot["accepted_source"]
        assert isinstance(source, dict)
        for unsafe_path in ("..\\outside.mp4", "C:/outside.mp4"):
            with self.subTest(unsafe_path=unsafe_path):
                source["path"] = unsafe_path
                self.assertIn("source.path", error_codes(data))

    def test_accepts_inspected_output_before_local_source_download(self) -> None:
        """Break caught: requiring a local download at the instant a Scenario output passes review."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        del shot["accepted_source"]

        self.assertEqual(validate_manifest(data), [])

    def test_accepts_complete_planning_with_empty_pre_spend_production(self) -> None:
        """Break caught: making a complete pre-spend shot plan impossible without fake job or output IDs."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        del shot["accepted_source"]
        shot["planning"] = canonical_planning()
        shot["production"] = {"disposition": "planned", "attempts": []}

        self.assertEqual(validate_manifest(data), [])

    def test_rejects_missing_planning_fields_and_unverified_sync_events(self) -> None:
        """Break caught: paying for a shot whose director brief is incomplete or whose sync event is unverified."""
        missing = valid_manifest(Decimal("30"))
        missing_shot = missing["shots"][0]
        assert isinstance(missing_shot, dict)
        missing_shot["planning"] = canonical_planning()
        missing_shot["production"] = {
            "disposition": "accepted",
            "attempts": [canonical_attempt()],
        }
        planning = missing_shot["planning"]
        assert isinstance(planning, dict)
        del planning["closing_state"]

        unverified = copy.deepcopy(missing)
        unverified_shot = unverified["shots"][0]
        assert isinstance(unverified_shot, dict)
        unverified_planning = canonical_planning()
        sync_events = unverified_planning["sync_events"]
        assert isinstance(sync_events, list) and isinstance(sync_events[0], dict)
        sync_events[0]["verified"] = False
        unverified_shot["planning"] = unverified_planning

        self.assertIn("planning.keys", error_codes(missing))
        self.assertIn("planning.sync_events.verified", error_codes(unverified))

    def test_requires_reference_roles_to_match_ordered_generation_inputs(self) -> None:
        """Break caught: accepting a paid prompt whose role map omits or misbinds a Scenario input."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        planning = canonical_planning()
        roles = planning["reference_roles"]
        assert isinstance(roles, list)
        roles.pop()
        shot["planning"] = planning
        shot["production"] = {
            "disposition": "accepted",
            "attempts": [canonical_attempt()],
        }

        self.assertIn("planning.reference_roles.coverage", error_codes(data))

    def test_accepts_completed_production_with_nullable_pre_call_identifiers(self) -> None:
        """Break caught: failing a real accepted run or forcing fake identifiers before a paid call exists."""
        completed = valid_manifest(Decimal("30"))
        completed_shot = completed["shots"][0]
        assert isinstance(completed_shot, dict)
        completed_shot["planning"] = canonical_planning()
        completed_shot["production"] = {
            "disposition": "accepted",
            "attempts": [canonical_attempt()],
        }

        pending = valid_manifest(Decimal("30"))
        pending_shot = pending["shots"][0]
        assert isinstance(pending_shot, dict)
        del pending_shot["accepted_source"]
        pending_attempt = canonical_attempt(acceptance_status="not_run")
        approval = pending_attempt["approval"]
        assert isinstance(approval, dict)
        approval["status"] = "pending"
        approval["record"] = None
        pending_shot["planning"] = canonical_planning()
        pending_shot["production"] = {
            "disposition": "planned",
            "attempts": [pending_attempt],
        }

        self.assertEqual(validate_manifest(completed), [])
        self.assertEqual(validate_manifest(pending), [])

    def test_requires_accepted_attempt_for_accepted_source(self) -> None:
        """Break caught: treating a local clip as accepted without a recorded inspected Scenario result."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        shot["planning"] = canonical_planning()
        shot["production"] = {"disposition": "planned", "attempts": []}

        self.assertIn("production.accepted_source", error_codes(data))

    def test_rejects_null_accepted_source_object(self) -> None:
        """Break caught: treating a present null source as if the optional field were absent."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        shot["accepted_source"] = None
        shot["production"] = {"disposition": "planned", "attempts": []}

        self.assertIn("source.keys", error_codes(data))

    def test_allows_revised_dry_run_after_explicit_pre_call_rejection(self) -> None:
        """Break caught: making an explicitly rejected dry-run request a permanent provenance dead end."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        del shot["accepted_source"]
        rejected = canonical_attempt(acceptance_status="not_run")
        rejected_approval = rejected["approval"]
        assert isinstance(rejected_approval, dict)
        rejected_approval["status"] = "rejected"
        rejected_approval["record"] = "User rejected the exact dry-run request."
        pending = canonical_attempt(attempt_id="attempt-002", acceptance_status="not_run")
        pending_approval = pending["approval"]
        assert isinstance(pending_approval, dict)
        pending_approval["status"] = "pending"
        pending_approval["record"] = None
        shot["production"] = {
            "disposition": "planned",
            "attempts": [rejected, pending],
        }

        self.assertEqual(validate_manifest(data), [])

    def test_rejects_job_without_approval_and_output_without_job(self) -> None:
        """Break caught: recording a paid call before exact approval or an output without its original job."""
        unapproved = valid_manifest(Decimal("30"))
        unapproved_shot = unapproved["shots"][0]
        assert isinstance(unapproved_shot, dict)
        del unapproved_shot["accepted_source"]
        attempt = canonical_attempt(acceptance_status="not_run")
        approval = attempt["approval"]
        assert isinstance(approval, dict)
        approval["status"] = "pending"
        approval["record"] = None
        attempt["job_id"] = "job_demo"
        unapproved_shot["planning"] = canonical_planning()
        unapproved_shot["production"] = {
            "disposition": "planned",
            "attempts": [attempt],
        }

        orphan_output = copy.deepcopy(unapproved)
        orphan_shot = orphan_output["shots"][0]
        assert isinstance(orphan_shot, dict)
        production = orphan_shot["production"]
        assert isinstance(production, dict)
        attempts = production["attempts"]
        assert isinstance(attempts, list) and isinstance(attempts[0], dict)
        orphan_attempt = attempts[0]
        orphan_approval = orphan_attempt["approval"]
        assert isinstance(orphan_approval, dict)
        orphan_approval["status"] = "approved"
        orphan_approval["record"] = "User approved the exact request."
        orphan_attempt["job_id"] = None
        orphan_attempt["output_id"] = "asset_out"

        self.assertIn("production.attempt.job.approval", error_codes(unapproved))
        self.assertIn("production.attempt.output.job", error_codes(orphan_output))

    def test_rejects_retry_after_timeout_and_undiagnosed_reroll(self) -> None:
        """Break caught: creating a replacement job after timeout or rerolling without one testable diagnosis."""
        timeout = valid_manifest(Decimal("30"))
        timeout_shot = timeout["shots"][0]
        assert isinstance(timeout_shot, dict)
        del timeout_shot["accepted_source"]
        timed_out = canonical_attempt(acceptance_status="timed_out")
        timed_out_acceptance = timed_out["acceptance"]
        assert isinstance(timed_out_acceptance, dict)
        timed_out_acceptance["reason"] = "The original job wait timed out."
        timeout_shot["planning"] = canonical_planning()
        timeout_shot["production"] = {
            "disposition": "timed_out",
            "attempts": [timed_out, canonical_attempt(attempt_id="attempt-002")],
        }

        reroll = valid_manifest(Decimal("30"))
        reroll_shot = reroll["shots"][0]
        assert isinstance(reroll_shot, dict)
        del reroll_shot["accepted_source"]
        rejected = canonical_attempt(acceptance_status="rejected")
        reroll_shot["planning"] = canonical_planning()
        reroll_shot["production"] = {
            "disposition": "accepted",
            "attempts": [rejected, canonical_attempt(attempt_id="attempt-002")],
        }

        self.assertIn("production.attempt.timeout.retry", error_codes(timeout))
        self.assertIn("production.attempt.reroll_diagnosis", error_codes(reroll))

    def test_requires_master_rights_and_delivery_audio_policy(self) -> None:
        """Break caught: validating a production manifest without authorization or deterministic mastering policy."""
        missing_rights = valid_manifest(Decimal("30"))
        master = missing_rights["master"]
        assert isinstance(master, dict)
        del master["rights"]

        bad_policy = valid_manifest(Decimal("30"))
        delivery = bad_policy["delivery"]
        assert isinstance(delivery, dict)
        audio_policy = delivery["audio_policy"]
        assert isinstance(audio_policy, dict)
        audio_policy["clip_audio"] = "mix"

        self.assertIn("master.keys", error_codes(missing_rights))
        self.assertIn("delivery.audio_policy.clip_audio", error_codes(bad_policy))

    def test_uses_decimal_master_duration_for_fractional_frame_target(self) -> None:
        """Break caught: truncating or float-rounding the exclusive target frame for fractional frame rates."""
        data = valid_manifest(Decimal("60"))
        master = data["master"]
        delivery = data["delivery"]
        shots = data["shots"]
        assert isinstance(master, dict) and isinstance(delivery, dict) and isinstance(shots, list)
        master["decoded_duration_seconds"] = 30.001
        delivery["frame_rate"] = {"fps_num": 30000, "fps_den": 1001}
        first, second = shots
        assert isinstance(first, dict) and isinstance(second, dict)
        first["timeline"] = {"start_frame": 0, "end_frame": 720}
        second["timeline"] = {"start_frame": 720, "end_frame": 900}
        for shot in (first, second):
            expected_output = shot["expected_output"]
            assert isinstance(expected_output, dict)
            expected_output["frame_rate"] = {"fps_num": 30000, "fps_den": 1001}
        accepted_source = second["accepted_source"]
        generation = second["generation"]
        assert isinstance(accepted_source, dict) and isinstance(generation, dict)
        accepted_source["trim_end_seconds"] = "7.000"
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["duration"] = 7

        self.assertEqual(validate_manifest(data), [])

        timeline = second["timeline"]
        assert isinstance(timeline, dict)
        timeline["end_frame"] = 899
        self.assertIn("timeline.final_coverage", error_codes(data))

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
        counts = {code: sum(item.code == code for item in validate_manifest(data)) for code in codes}
        for code in (
            "expected_output.resolution",
            "expected_output.aspect_ratio",
            "expected_output.frame_rate",
        ):
            self.assertEqual(counts[code], 1)

    def test_requires_supplied_pack_or_approved_generated_pack(self) -> None:
        """Break caught: treating supplied references as approved without an explicit approval record."""
        missing = valid_manifest(Decimal("30"))
        missing["reference_pack"] = {"source": "generated", "approval": "pending", "assets": []}
        supplied_missing = valid_manifest(Decimal("30"))
        supplied_missing["reference_pack"] = {
            "source": "supplied",
            "assets": [
                {"id": "artist", "path": "references/artist.png", "scenario_asset_id": "asset_i", "roles": ["performer"]},
                {"id": "master-guide", "path": "masters/master.wav", "scenario_asset_id": "asset_a", "roles": ["timing"]},
            ],
        }
        supplied_approved = copy.deepcopy(supplied_missing)
        supplied_pack = supplied_approved["reference_pack"]
        assert isinstance(supplied_pack, dict)
        supplied_pack["approval"] = "approved"
        generated = valid_manifest(Decimal("30"))
        generated["reference_pack"] = {
            "source": "generated",
            "approval": "approved",
            "assets": [
                {"id": "world", "path": "references/world.png", "scenario_asset_id": "asset_i", "roles": ["world"]},
                {"id": "master-guide", "path": "masters/master.wav", "scenario_asset_id": "asset_a", "roles": ["timing"]},
            ],
        }

        self.assertIn("reference_pack.approval", error_codes(missing))
        self.assertIn("reference_pack.approval", error_codes(supplied_missing))
        self.assertEqual(validate_manifest(supplied_approved), [])
        self.assertEqual(validate_manifest(generated), [])

    def test_rejects_duplicate_reference_ids_and_unbound_prompt_tags(self) -> None:
        """Break caught: ambiguous pack identities or prompt tags that cannot bind to Scenario arrays."""
        data = valid_manifest(Decimal("30"))
        reference_pack = data["reference_pack"]
        assert isinstance(reference_pack, dict)
        assets = reference_pack["assets"]
        assert isinstance(assets, list)
        assets.append(copy.deepcopy(assets[0]))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["prompt"] = "@image2 is missing and @audio0 is malformed."

        codes = error_codes(data)
        self.assertIn("reference_pack.asset.id.duplicate", codes)
        self.assertIn("generation.parameters.prompt_tag.unbound", codes)
        self.assertIn("generation.parameters.prompt_tag.malformed", codes)

    def test_requires_every_generation_asset_to_resolve_in_approved_pack(self) -> None:
        """Break caught: using unapproved visual or derived audio assets in a paid request."""
        data = valid_manifest(Decimal("30"))
        shot = data["shots"][0]
        assert isinstance(shot, dict)
        generation = shot["generation"]
        assert isinstance(generation, dict)
        parameters = generation["parameters"]
        assert isinstance(parameters, dict)
        parameters["referenceImages"] = ["asset_z"]
        parameters["referenceAudio"] = ["asset_y"]
        parameters["prompt"] = "@image1 defines identity. @audio1 defines timing only."

        codes = error_codes(data)
        self.assertIn("generation.parameters.reference_images.unapproved", codes)
        self.assertIn("generation.parameters.reference_audio.unapproved", codes)

    def test_malformed_enum_values_return_diagnostics_instead_of_type_errors(self) -> None:
        """Break caught: membership tests raising TypeError on valid JSON arrays or objects."""
        cases = (
            ("mode", lambda data: data["shots"][0]["generation"].__setitem__("mode", [])),
            ("aspect_ratio", lambda data: data["delivery"].__setitem__("aspect_ratio", [])),
            ("resolution", lambda data: data["delivery"].__setitem__("resolution", {})),
            ("output_format", lambda data: data["shots"][0]["generation"]["parameters"].__setitem__("outputFormat", [])),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                data = valid_manifest(Decimal("30"))
                mutate(data)
                diagnostics = validate_manifest(data)
                self.assertTrue(diagnostics)

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
        artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-manifest-tests-", dir=preferred_temp_root()))
        duplicate = artifact_dir / "duplicate.json"
        nonfinite = artifact_dir / "nonfinite.json"
        extreme_positive = artifact_dir / "extreme-positive.json"
        extreme_negative = artifact_dir / "extreme-negative.json"
        extreme_integer = artifact_dir / "extreme-integer.json"
        scalar = artifact_dir / "scalar.json"
        duplicate.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
        nonfinite.write_text('{"schema_version": NaN}', encoding="utf-8")
        extreme_positive.write_text('{"decoded_duration_seconds": 1e9999}', encoding="utf-8")
        extreme_negative.write_text('{"decoded_duration_seconds": 1e-9999}', encoding="utf-8")
        extreme_integer.write_text('{"start_frame": 100000000000000000000}', encoding="utf-8")
        scalar.write_text('["not a manifest"]', encoding="utf-8")

        for path in (duplicate, nonfinite, extreme_positive, extreme_negative, extreme_integer, scalar):
            with self.subTest(path=path.name):
                with self.assertRaises(ManifestJsonError):
                    load_manifest(path)

    def test_loads_json_decimals_without_binary_float_rounding(self) -> None:
        """Break caught: losing exact manifest time values before Decimal frame math runs."""
        artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-decimal-tests-", dir=preferred_temp_root()))
        manifest_path = artifact_dir / "precise.json"
        manifest_path.write_text('{"decoded_duration_seconds": 30.0000000000000000001}', encoding="utf-8")

        data = load_manifest(manifest_path)

        self.assertIsInstance(data["decoded_duration_seconds"], Decimal)
        self.assertEqual(data["decoded_duration_seconds"], Decimal("30.0000000000000000001"))

    def test_rejects_boolean_schema_version_and_string_master_duration(self) -> None:
        """Break caught: Python equality or coercion accepting JSON values with the wrong scalar types."""
        data = valid_manifest(Decimal("30"))
        data["schema_version"] = True
        master = data["master"]
        assert isinstance(master, dict)
        master["decoded_duration_seconds"] = "30.000"

        codes = error_codes(data)
        self.assertIn("schema_version", codes)
        self.assertIn("master.duration.type", codes)

    def test_cli_has_contract_and_json_error_exit_codes(self) -> None:
        """Break caught: callers being unable to distinguish a bad manifest from unreadable or invalid JSON."""
        artifact_dir = Path(tempfile.mkdtemp(prefix="scenario-seedance-manifest-cli-tests-", dir=preferred_temp_root()))
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
