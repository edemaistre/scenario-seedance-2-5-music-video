from __future__ import annotations

import unittest
from pathlib import Path


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
