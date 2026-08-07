from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_skill import PACKAGE_FILES, PACKAGE_ROOT, audit_release_file, build_skill_archive
from scripts.verify_delivery import preferred_temp_root


ROOT = Path(__file__).resolve().parents[1]


class PackageSkillTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
