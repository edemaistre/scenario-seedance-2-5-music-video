from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "SKILL.md"
RESUME_ENTRY = "**Resume this work:** `claude --resume 019fdb6d-cde0-7ee3-858d-8f411dc18f50`"
PRIVATE_ID_PATTERN = re.compile(
    r"\b(?:team|project|workspace|organization|asset)_[A-Za-z0-9_-]{8,}\b",
    re.IGNORECASE,
)
SIGNED_URL_PATTERN = re.compile(
    r"(?:X-(?:Amz|Goog)-(?:Algorithm|Credential|Date|Expires|SignedHeaders|Signature)|[?&](?:signature|sig|token|policy|key-pair-id)=)",
    re.IGNORECASE,
)
ALLOWED_RELEASE_SUFFIXES = {".json", ".md", ".py", ".txt", ".yaml", ".yml"}
ALLOWED_RELEASE_NAMES = {".gitignore", "LICENSE"}


def release_file_violations(relative_path: Path, raw: bytes) -> list[str]:
    """Return privacy violations for one prospective repository or package file."""
    violations: list[str] = []
    if relative_path.name not in ALLOWED_RELEASE_NAMES and relative_path.suffix.lower() not in ALLOWED_RELEASE_SUFFIXES:
        violations.append("disallowed release file type")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        violations.append("file is not valid UTF-8 text")
        return violations
    if "\x00" in text:
        violations.append("text file contains binary NUL bytes")
    if PRIVATE_ID_PATTERN.search(text):
        violations.append("private Scenario ID found")
    if SIGNED_URL_PATTERN.search(text):
        violations.append("temporary signed URL found")
    return violations


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
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True,
            capture_output=True,
        )
        for encoded_path in result.stdout.split(b"\0"):
            if not encoded_path:
                continue
            relative_path = Path(encoded_path.decode("utf-8"))
            with self.subTest(path=relative_path):
                self.assertEqual(release_file_violations(relative_path, (ROOT / relative_path).read_bytes()), [])

    def test_privacy_audit_rejects_binary_and_disallowed_media(self) -> None:
        png = release_file_violations(Path("private-reference.png"), b"\x89PNG\r\n\x1a\n")
        disguised = release_file_violations(Path("reference.md"), b"\xff\xfeprivate")

        self.assertTrue(any("type" in item for item in png))
        self.assertTrue(any("UTF-8" in item for item in disguised))

    def test_gitignore_covers_common_private_media(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "*.png", "*.jpg", "*.jpeg", "*.webp", "*.m4a", "*.aac", "*.aiff", "*.ogg", "*.opus", "*.webm"
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, text)

    def test_signed_url_pattern_catches_google_cloud_signature(self) -> None:
        marker = "X-Goog-" + "Signature"
        value = f"https://storage.example/video.mp4?{marker}=example"

        self.assertIsNotNone(SIGNED_URL_PATTERN.search(value))

    def test_signed_url_pattern_catches_cloudfront_parameters(self) -> None:
        policy = "Po" + "licy"
        key_pair_id = "Key-Pair-" + "Id"
        value = (
            "https://cdn.example/video.mp4?"
            f"{policy}=example&{key_pair_id}=example"
        )

        self.assertIsNotNone(SIGNED_URL_PATTERN.search(value))

    def test_repository_docs_include_the_current_resume_entry(self) -> None:
        for name in ("README.md", "CLAUDE.md"):
            with self.subTest(name=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn(RESUME_ENTRY, text)

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
