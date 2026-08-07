# Bugs

## Fixed in 1.0.0

- Fixed stale or substituted master media being accepted during assembly by checking source SHA-256, stream facts, physical duration, and target frame ceiling.
- Fixed partial or invalid outputs blocking recovery by building in retained unique work directories and publishing only a verified candidate with an atomic no-replace hard link.
- Fixed rational frame-rate regressions and partial-final-frame loss with exact Fraction and Decimal checks.
- Fixed delivery verification that could accept truncated or unrelated transcoded audio by checking audio duration and a deterministic master-derived AAC packet hash.
- Fixed unauthorized codec changes and raced or unreadable master hashing returning misleading success.
- Fixed a circular spend rule by separating optional analysis spend, reference creation spend, and Seedance video spend gates.
- Fixed macOS-only temporary paths and a CI command that discovered zero tests. CI now installs and checks FFmpeg, then discovers `tests/` explicitly.

## Open

No known reproducible code defects. Live model-schema drift and creative model variability remain operational risks, so every production refreshes the schema, dry-runs paid requests, and requires human visual and release review.
