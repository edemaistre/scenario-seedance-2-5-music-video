from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.verify_delivery as verify_delivery


ROOT = Path(__file__).resolve().parents[1]
PORTABILITY_TARGETS = (
    ROOT / "scripts" / "verify_delivery.py",
    ROOT / "tests" / "test_analyze_audio.py",
    ROOT / "tests" / "test_assemble_music_video.py",
    ROOT / "tests" / "test_validate_project.py",
    ROOT / "tests" / "test_verify_delivery.py",
)


class PortabilityContractTests(unittest.TestCase):
    def test_rejects_direct_macos_temp_paths_for_temp_directories_and_cli_cwds(self) -> None:
        """Break caught: Ubuntu jobs trying to use macOS-only /private/tmp paths."""
        violations: list[str] = []
        for path in PORTABILITY_TARGETS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if (
                        keyword.arg in {"dir", "cwd"}
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value == "/private/tmp"
                    ):
                        violations.append(f"{path.relative_to(ROOT)}:{keyword.lineno}")

        self.assertEqual(violations, [])

    def test_prefers_macos_temp_root_when_available_and_falls_back_elsewhere(self) -> None:
        """Break caught: artifact retention relying on a macOS-only temporary root."""
        temp_root = getattr(verify_delivery, "preferred_temp_root", None)
        self.assertTrue(callable(temp_root))
        assert callable(temp_root)

        with patch("scripts.verify_delivery.Path.is_dir", return_value=True):
            self.assertEqual(temp_root(), Path("/private/tmp"))
        with (
            patch("scripts.verify_delivery.Path.is_dir", return_value=False),
            patch("scripts.verify_delivery.tempfile.gettempdir", return_value="/tmp/portable"),
        ):
            self.assertEqual(temp_root(), Path("/tmp/portable"))

    def test_workflow_installs_and_checks_ffmpeg_before_integration_tests(self) -> None:
        """Break caught: CI silently skipping media integration tests because FFmpeg is unavailable."""
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

        self.assertIn("apt-get install -y ffmpeg", workflow)
        self.assertIn("ffmpeg -version", workflow)
        self.assertIn("ffprobe -version", workflow)
        self.assertIn("python3 -B -m unittest discover -s tests -v", workflow)


if __name__ == "__main__":
    unittest.main()
