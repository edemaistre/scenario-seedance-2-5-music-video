# SDD ledger, plan: docs/superpowers/plans/2026-08-07-scenario-seedance-2-5-music-video.md

Constraint ruling: the user's one-commit rule overrides per-task commits. Each task uses a saved pre-task snapshot and a diff package for review. One final commit will be created only after all tests pass.

Plan dependency ruling: Task 1 cannot both require every future routed file and leave Task 6 to create those files. Task 1 tests the current core contract. Task 6 adds routed-file existence assertions when the referenced files exist.

Task 1: fix round 1/5, 2 findings addressed, 0 open.
Task 1: complete, review clean, 6 static tests passing, no intermediate commit by user rule.

Task 2: fix round 1/5, 4 findings addressed, 1 new boundary-onset finding open.
Task 2: fix round 2/5, boundary-onset finding addressed, 0 open.
Task 2: complete, review clean, 20 full-suite tests passing, no intermediate commit by user rule.

Task 3 interface decision: use integer target and edit frame indexes for exact final coverage, with Decimal strings only for source trim seconds. This avoids floating-point timeline accumulation and becomes the assembler contract for Tasks 4 and 5.

Task 3: initial implementer was interrupted after no visible progress; its late draft was preserved before continuation.
Task 3: fix round 1/5, 8 findings addressed, 1 exponent-overflow regression open.
Task 3: fix round 2/5, exponent-overflow and stale documentation addressed, 0 open.
Task 3: complete, review clean, 49 full-suite tests passing, no intermediate commit by user rule.
