from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "SKILL.md"
PRIVATE_ID_PATTERN = re.compile(
    r"\b(?:team|project|workspace|organization|asset)_[A-Za-z0-9_-]{8,}\b",
    re.IGNORECASE,
)
SIGNED_URL_PATTERN = re.compile(
    r"(?:X-Amz-(?:Algorithm|Credential|Signature)|[?&](?:signature|sig|token)=)",
    re.IGNORECASE,
)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise AssertionError("SKILL.md must begin with YAML frontmatter")
    metadata: dict[str, str] = {}
    for line in match.group("body").splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


class SkillContractTests(unittest.TestCase):
    def test_skill_frontmatter_and_core_contract(self) -> None:
        skill_text = SKILL_PATH.read_text(encoding="utf-8")
        metadata = parse_frontmatter(skill_text)

        self.assertEqual(metadata["name"], "scenario-seedance-2-5-music-video")
        self.assertTrue(metadata["description"].startswith("Use when"))
        self.assertIn("30", skill_text)
        self.assertIn("generateAudio: false", skill_text)
        self.assertIn("fully assembled", skill_text.lower())
        self.assertIn("reference", skill_text.lower())

    def test_repository_has_no_private_ids_or_signed_urls(self) -> None:
        excluded_parts = {".git"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or excluded_parts.intersection(path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(PRIVATE_ID_PATTERN.search(text))
                self.assertIsNone(SIGNED_URL_PATTERN.search(text))

    def test_text_files_use_ascii_hyphens(self) -> None:
        excluded_parts = {".git"}
        for path in ROOT.rglob("*"):
            if not path.is_file() or excluded_parts.intersection(path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("\u2013", text)
                self.assertNotIn("\u2014", text)
