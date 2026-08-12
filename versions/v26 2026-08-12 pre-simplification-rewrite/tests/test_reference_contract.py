from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_project import validate_manifest


ROOT = Path(__file__).resolve().parents[1]

REFERENCE_FILES = (
    "references/model-contract.md",
    "references/music-analysis-and-treatment.md",
    "references/shot-design-and-prompting.md",
    "references/scenario-production.md",
    "references/assembly-and-qa.md",
    "references/examples.md",
    "references/source-ledger.md",
)

TEMPLATE_FILES = (
    "assets/intake-template.md",
    "assets/treatment-template.md",
    "assets/continuity-bible-template.md",
)


class ReferenceContractTests(unittest.TestCase):
    def text(self, relative_path: str) -> str:
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"Missing routed file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_every_skill_route_exists(self) -> None:
        skill = self.text("SKILL.md")
        for relative_path in REFERENCE_FILES + TEMPLATE_FILES:
            with self.subTest(relative_path=relative_path):
                self.assertIn(relative_path, skill)
                self.assertTrue((ROOT / relative_path).is_file())

    def test_model_contract_records_live_scenario_boundary(self) -> None:
        text = self.text("references/model-contract.md")
        for marker in (
            "model_bytedance-seedance-2-5",
            "2026-08-07",
            "model_schema_get",
            "generateAudio",
            "referenceImages",
            "referenceVideos",
            "referenceAudio",
            "480p",
            "720p",
            "21:9",
            "9:16",
            "live schema wins",
            "conditioning",
            "passthrough",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_music_guidance_covers_analysis_uncertainty_and_adaptive_energy(self) -> None:
        text = self.text("references/music-analysis-and-treatment.md")
        for marker in (
            "model_scenario-audio-to-text",
            "segment-level",
            "instrumental",
            "lyrics",
            "uncertain",
            "stem",
            "asset_analyze",
            "rhythm",
            "story",
            "energy",
            "hypercut",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text.lower())

    def test_shot_guidance_encodes_music_video_craft_without_style_anchoring(self) -> None:
        text = self.text("references/shot-design-and-prompting.md")
        for marker in (
            "8 to 24",
            "4 to 8",
            "camera",
            "shot size",
            "lens",
            "lighting",
            "dialogue",
            "aspect ratio",
            "negative",
            "closing",
            "do not copy",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text.lower())

    def test_canonical_manifest_records_planning_and_paid_attempt_provenance(self) -> None:
        """Break caught: guidance requiring production records that the canonical manifest cannot store."""
        manifest = json.loads(self.text("assets/music-video-manifest.example.json"))
        self.assertEqual(validate_manifest(manifest), [])
        shots = manifest["shots"]
        self.assertIsInstance(shots, list)
        shot = shots[0]
        self.assertIn("planning", shot)
        self.assertIn("production", shot)
        self.assertEqual(set(shot["production"]), {"disposition", "attempts"})

        shot_guidance = self.text("references/shot-design-and-prompting.md").lower()
        production_guidance = self.text("references/scenario-production.md").lower()
        skill = self.text("SKILL.md").lower()
        for marker in ("planning", "production", "disposition", "attempts"):
            with self.subTest(document="shot guidance", marker=marker):
                self.assertIn(marker, shot_guidance)
        for marker in ("disposition", "attempt record", "reroll diagnosis"):
            with self.subTest(document="production guidance", marker=marker):
                self.assertIn(marker, production_guidance)
        self.assertIn("supplied and generated reference packs", skill)

    def test_public_manifest_costs_are_unmistakably_synthetic(self) -> None:
        """Break caught: presenting one unrelated live smoke estimate as a quote for example shots."""
        paths = (
            "assets/music-video-manifest.example.json",
            "tests/fixtures/valid_30s_project.json",
            "tests/fixtures/valid_157s_project.json",
            "tests/fixtures/invalid_gap_project.json",
        )
        for relative_path in paths:
            manifest = json.loads(self.text(relative_path))
            for shot in manifest["shots"]:
                for attempt in shot["production"]["attempts"]:
                    with self.subTest(relative_path=relative_path, shot=shot["id"]):
                        self.assertEqual(
                            attempt["dry_run_estimate"]["unit"],
                            "SYNTHETIC_EXAMPLE_ONLY",
                        )
                        known_cost = attempt["known_cost"]
                        if known_cost is not None:
                            self.assertEqual(known_cost["unit"], "SYNTHETIC_EXAMPLE_ONLY")

    def test_production_guidance_requires_reference_creation_and_spend_gates(self) -> None:
        text = self.text("references/scenario-production.md")
        for marker in (
            "teams_list",
            "projects_list",
            "model_schema_get",
            "dry_run",
            "model_run",
            "jobs_wait",
            "reference pack",
            "explicit approval",
            "job id",
            "timed out",
            "generateAudio: false",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_spend_gates_are_tiered_and_non_circular(self) -> None:
        skill = self.text("SKILL.md")
        production = self.text("references/scenario-production.md")

        self.assertNotIn("Do not make paid calls before", skill)
        self.assertIn("No paid Seedance video generation", skill)

        analysis_heading = "## Analysis spend gate"
        reference_heading = "## Reference spend gate"
        video_heading = "## Seedance video spend gate"
        for heading in (analysis_heading, reference_heading, video_heading):
            with self.subTest(heading=heading):
                self.assertIn(heading, production)

        analysis_start = production.index(analysis_heading)
        reference_start = production.index(reference_heading)
        video_start = production.index(video_heading)
        self.assertLess(analysis_start, reference_start)
        self.assertLess(reference_start, video_start)

        analysis = production[analysis_start:reference_start]
        for marker in (
            "only when needed",
            "model_scenario-audio-to-text",
            "model_ace-step-1-5-edit-stem-extract",
            "model_schema_get",
            "dry_run",
            "estimate",
            "explicit approval",
            "one asynchronous call",
            "job ID",
        ):
            with self.subTest(tier="analysis", marker=marker):
                self.assertIn(marker, analysis)

        reference = production[reference_start:video_start]
        for marker in (
            "free technical and music analysis",
            "three free treatments",
            "selected treatment",
            "dry_run",
            "estimate",
            "explicit approval",
            "one bounded reference run",
            "continuity bible",
            "animatic",
        ):
            with self.subTest(tier="reference", marker=marker):
                self.assertIn(marker, reference)

        video = production[video_start:]
        for marker in (
            "approved reference pack",
            "continuity bible",
            "complete no-gap EDL",
            "animatic",
            "chapter budget",
            "live schema",
            "proof-shot dry run",
            "explicit approval",
        ):
            with self.subTest(tier="video", marker=marker):
                self.assertIn(marker, video)

    def test_assembly_guidance_preserves_master_and_requires_verification(self) -> None:
        text = self.text("references/assembly-and-qa.md")
        for marker in (
            "assemble_music_video.py",
            "verify_delivery.py",
            "stream-copy",
            "AAC",
            "320",
            "normalization",
            "stretch",
            "generated audio",
            "photosensitivity",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), text.lower())

    def test_examples_are_structural_varied_and_explicitly_non_prescriptive(self) -> None:
        text = self.text("references/examples.md")
        for marker in (
            "anti-anchoring",
            "performance-led",
            "lyric-metaphor",
            "instrumental abstract",
            "brand or product cover",
            "do not copy",
            "generateAudio: false",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), text.lower())

    def test_templates_capture_required_decisions(self) -> None:
        intake = self.text("assets/intake-template.md")
        treatment = self.text("assets/treatment-template.md")
        continuity = self.text("assets/continuity-bible-template.md")
        for marker in ("rights", "master", "lyrics", "reference", "spending ceiling"):
            self.assertIn(marker, intake.lower())
        for marker in ("emotional arc", "music", "visual", "ending image"):
            self.assertIn(marker, treatment.lower())
        for marker in ("identity", "world", "color", "camera", "continuity"):
            self.assertIn(marker, continuity.lower())


if __name__ == "__main__":
    unittest.main()
