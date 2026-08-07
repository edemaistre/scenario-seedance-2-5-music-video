#!/usr/bin/env python3
"""Build the installable skill archive from an exact privacy-audited allowlist."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
import zipfile
from pathlib import Path


PACKAGE_ROOT = "scenario-seedance-2-5-music-video"
PACKAGE_FILES = (
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
ALLOWED_SUFFIXES = {".json", ".md", ".py", ".txt", ".yaml", ".yml"}
ALLOWED_NAMES = {"LICENSE"}
PRIVATE_ID_PATTERN = re.compile(
    r"\b(?:team|project|workspace|organization|asset)_[A-Za-z0-9_-]{8,}\b",
    re.IGNORECASE,
)
SIGNED_URL_PATTERN = re.compile(
    r"(?:X-(?:Amz|Goog)-(?:Algorithm|Credential|Date|Expires|SignedHeaders|Signature)|[?&](?:signature|sig|token|policy|key-pair-id)=)",
    re.IGNORECASE,
)


class PackageError(RuntimeError):
    """Raised when a source file fails the release contract."""


def audit_release_file(relative_path: Path, raw: bytes) -> list[str]:
    """Return deterministic privacy and file-type violations."""
    violations: list[str] = []
    if relative_path.is_absolute() or ".." in relative_path.parts:
        violations.append("path must be relative and remain inside the package")
    if relative_path.name not in ALLOWED_NAMES and relative_path.suffix.lower() not in ALLOWED_SUFFIXES:
        violations.append("disallowed package file type")
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


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def build_skill_archive(source_root: Path, destination: Path) -> dict[str, object]:
    """Create an atomic no-overwrite archive and retain its work directory."""
    source_root = source_root.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if destination.exists():
        raise FileExistsError(f"Archive already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    work_dir = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.work-", dir=destination.parent)
    )
    candidate = work_dir / destination.name
    with zipfile.ZipFile(candidate, mode="x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in PACKAGE_FILES:
            path = source_root / relative
            if not path.is_file():
                raise PackageError(f"Missing package file: {relative}")
            raw = path.read_bytes()
            violations = audit_release_file(Path(relative), raw)
            if violations:
                raise PackageError(f"Unsafe package file {relative}: {'; '.join(violations)}")
            archive.writestr(_zip_info(f"{PACKAGE_ROOT}/{relative}"), raw)
    try:
        os.link(candidate, destination)
    except FileExistsError as error:
        raise FileExistsError(f"Archive already exists: {destination}") from error
    return {
        "archive": str(destination),
        "retained_work_directory": str(work_dir),
        "files": len(PACKAGE_FILES),
    }


def _parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the allowlisted installable skill archive.")
    parser.add_argument("destination", type=Path, help="New .skill archive path")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = _parse_arguments(arguments)
    result = build_skill_archive(args.source_root, args.destination)
    print(f"Created {result['archive']} with {result['files']} allowlisted files.")
    print(f"Retained package work directory: {result['retained_work_directory']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
