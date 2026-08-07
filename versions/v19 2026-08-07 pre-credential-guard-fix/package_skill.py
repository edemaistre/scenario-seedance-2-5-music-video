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
ALLOWED_NAMES = {".gitignore", "LICENSE"}
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


def _binary_signature(raw: bytes) -> str | None:
    stripped = raw.lstrip(b"\xef\xbb\xbf\t\r\n ")
    prefixes = (
        (b"%PDF-", "PDF"),
        (b"\x89PNG\r\n\x1a\n", "PNG"),
        (b"\xff\xd8\xff", "JPEG"),
        (b"GIF87a", "GIF"),
        (b"GIF89a", "GIF"),
        (b"PK\x03\x04", "ZIP"),
        (b"7z\xbc\xaf\x27\x1c", "7-Zip"),
        (b"Rar!\x1a\x07", "RAR"),
        (b"OggS", "Ogg"),
        (b"fLaC", "FLAC"),
        (b"ID3", "MP3"),
        (b"8BPS", "Photoshop"),
        (b"\x1aE\xdf\xa3", "Matroska or WebM"),
        (b"\x7fELF", "ELF executable"),
    )
    for prefix, label in prefixes:
        if stripped.startswith(prefix):
            return label
    if len(stripped) >= 12 and stripped[4:8] == b"ftyp":
        return "ISO base media"
    if stripped.startswith(b"RIFF") and len(stripped) >= 12:
        return "RIFF media"
    if stripped.startswith(b"FORM") and len(stripped) >= 12:
        return "IFF media"
    lowered = stripped[:1024].lower()
    if lowered.startswith(b"<svg") or lowered.startswith(b"<?xml") and b"<svg" in lowered:
        return "SVG"
    return None


def audit_release_file(relative_path: Path, raw: bytes) -> list[str]:
    """Return deterministic privacy and file-type violations."""
    violations: list[str] = []
    if relative_path.is_absolute() or ".." in relative_path.parts:
        violations.append("path must be relative and remain inside the package")
    if relative_path.name not in ALLOWED_NAMES and relative_path.suffix.lower() not in ALLOWED_SUFFIXES:
        violations.append("disallowed package file type")
    signature = _binary_signature(raw)
    if signature is not None:
        violations.append(f"binary signature found: {signature}")
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
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.extra = b""
    info.comment = b""
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
    with zipfile.ZipFile(candidate, mode="x", compression=zipfile.ZIP_STORED) as archive:
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
