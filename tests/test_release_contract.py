from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"Missing release file: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_agent_prompt_describes_music_responsive_not_uniform_energy(self) -> None:
        text = self.read("agents/openai.yaml")
        self.assertIn("music-responsive", text)
        self.assertNotIn("high-energy", text)

    def test_skill_and_music_reference_analyze_the_exact_read_only_master(self) -> None:
        skill = self.read("SKILL.md")
        guidance = self.read("references/music-analysis-and-treatment.md")
        self.assertIn("exact release master", skill.lower())
        self.assertIn("read-only", skill.lower())
        for marker in (
            "model_scenario-audio-to-text",
            "large-v3",
            "ISO language",
            "vadFilter",
            "segment-level",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, guidance)

    def test_assembly_documentation_matches_frame_and_transcode_verification(self) -> None:
        text = self.read("references/assembly-and-qa.md")
        for marker in (
            "ceiling frame",
            "one frame longer",
            "retained work directory",
            "master-derived reference AAC",
            "audio duration",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_public_release_documentation_is_complete(self) -> None:
        readme = self.read("README.md")
        claude = self.read("CLAUDE.md")
        changelog = self.read("CHANGELOG.md")
        bugs = self.read("BUGS.md")
        roadmap = self.read("ROADMAP.md")
        versions = self.read("versions/README.md")
        for marker in ("Install", "Scenario smoke", "113", "public GitHub", "v1.0.0"):
            with self.subTest(marker=marker):
                self.assertIn(marker, readme)
        self.assertIn("Current state: complete", claude)
        self.assertIn("audio analysis", changelog.lower())
        self.assertIn("fixed", bugs.lower())
        self.assertNotIn("- [ ]", roadmap)
        for number in range(1, 19):
            self.assertIn(f"## v{number} ", versions)
        for relative_path in (
            "references/assembly-and-qa.md",
            "references/examples.md",
            "references/scenario-production.md",
            "references/shot-design-and-prompting.md",
            "references/source-ledger.md",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertIn("## Contents", self.read(relative_path))

    def test_publication_metadata_exists(self) -> None:
        for relative_path in (
            "LICENSE",
            "llms.txt",
            "llms-full.txt",
            "requirements-dev.txt",
            "scripts/package_skill.py",
        ):
            self.read(relative_path)


if __name__ == "__main__":
    unittest.main()
