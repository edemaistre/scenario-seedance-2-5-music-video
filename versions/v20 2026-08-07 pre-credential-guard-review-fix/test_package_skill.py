from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.package_skill import PACKAGE_FILES, PACKAGE_ROOT, audit_release_file, build_skill_archive
from scripts.verify_delivery import preferred_temp_root


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PACKAGE_FILES = (
    "SKILL.md",
    "LICENSE",
    "agents/openai.yaml",
    "assets/continuity-bible-template.md",
    "assets/intake-template.md",
    "assets/music-video-manifest.example.json",
    "assets/treatment-template.md",
    "references/assembly-and-qa.md",
    "references/examples.md",
    "references/model-contract.md",
    "references/music-analysis-and-treatment.md",
    "references/scenario-production.md",
    "references/shot-design-and-prompting.md",
    "references/source-ledger.md",
    "scripts/__init__.py",
    "scripts/analyze_audio.py",
    "scripts/assemble_music_video.py",
    "scripts/validate_project.py",
    "scripts/verify_delivery.py",
)


class PackageSkillTests(unittest.TestCase):
    def test_package_membership_matches_independent_operational_contract(self) -> None:
        self.assertEqual(PACKAGE_FILES, REQUIRED_PACKAGE_FILES)

    def test_every_packaged_file_is_allowlisted_text_and_privacy_clean(self) -> None:
        for relative in PACKAGE_FILES:
            with self.subTest(relative=relative):
                path = ROOT / relative
                self.assertTrue(path.is_file())
                self.assertEqual(audit_release_file(Path(relative), path.read_bytes()), [])

    def test_builds_only_the_allowlist_and_never_overwrites(self) -> None:
        retained = Path(tempfile.mkdtemp(prefix="scenario-seedance-package-tests-", dir=preferred_temp_root()))
        output = retained / "scenario-seedance-2-5-music-video.skill"

        result = build_skill_archive(ROOT, output)

        self.assertEqual(result["archive"], str(output))
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(
                archive.namelist(),
                [f"{PACKAGE_ROOT}/{relative}" for relative in PACKAGE_FILES],
            )
            for name in archive.namelist():
                self.assertEqual(audit_release_file(Path(name).relative_to(PACKAGE_ROOT), archive.read(name)), [])
        with self.assertRaises(FileExistsError):
            build_skill_archive(ROOT, output)

    def test_archive_bytes_are_identical_across_host_zip_metadata_defaults(self) -> None:
        retained = Path(tempfile.mkdtemp(prefix="scenario-seedance-package-determinism-", dir=preferred_temp_root()))
        unix_output = retained / "unix.skill"
        windows_output = retained / "windows.skill"

        build_skill_archive(ROOT, unix_output)
        with patch("zipfile.sys.platform", "win32"):
            build_skill_archive(ROOT, windows_output)

        self.assertEqual(
            hashlib.sha256(unix_output.read_bytes()).hexdigest(),
            hashlib.sha256(windows_output.read_bytes()).hexdigest(),
        )

    def test_package_audit_rejects_utf8_decodable_binary_signature(self) -> None:
        violations = audit_release_file(Path("disguised.md"), b"%PDF-1.7\nprivate reference")
        credential = audit_release_file(Path("notes.md"), ("github_pat_" + "a" * 32).encode())
        private_job = audit_release_file(Path("notes.md"), ("job_" + "b" * 12).encode())

        self.assertTrue(any("binary signature" in item for item in violations))
        self.assertTrue(any("credential" in item for item in credential))
        self.assertTrue(any("private job" in item for item in private_job))


if __name__ == "__main__":
    unittest.main()
