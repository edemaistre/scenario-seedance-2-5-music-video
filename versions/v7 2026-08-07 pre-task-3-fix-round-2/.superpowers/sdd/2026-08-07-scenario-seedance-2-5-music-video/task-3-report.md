# Task 3 Report: Long-Form Project Manifest Validator

## Scope

Implemented Task 3 only. The approved design, implementation plan, Task 1 files, and Task 2 files were not modified. No commit was created.

The interrupted Task 3 draft was preserved at `versions/v5 2026-08-07 interrupted-task-3-draft/` before its deliverables were revised. The version entry was added to `versions/README.md`.

## Files created or completed

- `tests/fixtures/valid_30s_project.json`
- `tests/fixtures/valid_157s_project.json`
- `tests/fixtures/invalid_gap_project.json`
- `tests/test_validate_project.py`
- `scripts/validate_project.py`
- `assets/music-video-manifest.example.json`

## Canonical manifest contract

- The master records a safe relative path, SHA-256, numeric decoded duration, sample rate, channels, and confirmed rights basis.
- Delivery records MP4 geometry, aspect ratio, rational frame rate, resolution, and a strict supplied-master audio policy.
- Integer shot ranges use exclusive `start_frame` and `end_frame` values. They cover `[0, target_frames)` exactly, where `target_frames = ceil(Decimal(decoded_duration_seconds) * fps_num / fps_den)`.
- Optional `accepted_source` trims use millisecond-precision Decimal strings. A complete pre-spend plan can validate before clips exist.
- The supplied reference pack or approved generated reference pack records local provenance and Scenario asset IDs. Example IDs are short public placeholders so repository privacy guards remain effective.
- Lyrics support provided and certain, Scenario transcription and uncertain, instrumental, or unresolved states. Scenario transcription cannot be marked certain.
- Each shot carries the exact dated Seedance request shape. The validator accepts only documented parameter names, validates Scenario asset arrays and prompt tags, requires `generateAudio` to be exactly `false`, and uses integer `-1` only for valid edit-mode Auto operations.

## RED evidence

The interrupted draft already had tests timestamped before its production validator. This continuation did not claim an unavailable transcript from that interrupted process.

After adding the missing canonical contract assertions, the command below failed before the validator changes:

```bash
python3 -B -m unittest tests.test_validate_project -v
```

Result: 21 tests ran with 23 failing test or subtest cases. Failures covered the new master, delivery, optional accepted source, Scenario parameter, Auto edit, prompt-tag, and fractional-frame expectations.

Two strict-JSON regression tests were then added before their fixes:

```bash
python3 -B -m unittest tests.test_validate_project.ValidateProjectTests.test_rejects_duplicate_keys_nonfinite_json_and_non_object_roots tests.test_validate_project.ValidateProjectTests.test_rejects_boolean_schema_version_and_string_master_duration -v
```

Result: 2 tests failed as expected. Exponent overflow was accepted, and Python equality allowed boolean schema version 1 while string master duration was coerced.

The portable path regression test was also run before its fix:

```bash
python3 -B -m unittest tests.test_validate_project.ValidateProjectTests.test_rejects_windows_style_path_traversal -v
```

Result: 1 test failed as expected because a Windows parent path was treated as a POSIX filename.

## GREEN evidence

Focused command:

```bash
python3 -B -m unittest tests.test_validate_project -v
```

Result: all 23 validator tests passed with no warnings or tracebacks.

Direct CLI checks:

- `assets/music-video-manifest.example.json` returned exit code 0.
- `tests/fixtures/invalid_gap_project.json` returned exit code 1 with one deterministic `timeline.gap` diagnostic.
- Automated CLI tests cover unreadable or invalid JSON exit code 2.

Full verification:

```bash
python3 -B -m unittest discover -s tests -v
```

Result: all 43 repository tests passed with no warnings or tracebacks.

## Integration fix

The first full-suite run found 5 Task 1 privacy-guard failures because realistic long example asset IDs looked like private Scenario identifiers. The root cause was fixture data, not the guard or validator. The fixtures and example now use short schema-valid public placeholders such as `asset_i` and `asset_a`. The focused privacy test and all validator tests passed before the final full-suite run.

## Concerns

- The validator matches the live Scenario schema snapshot verified on 2026-08-07. The skill must still refresh the live schema before any real generation, and the live schema wins if it changes.
- Public example asset IDs are placeholders. A private production manifest must replace them with actual uploaded Scenario asset IDs without publishing those IDs back into this repository.
- Task 4 must require `accepted_source` for assembly even though Task 3 intentionally permits it to be absent during pre-spend planning.

## Review Fix Round 1

### Scope

Applied all six Important findings and both Minor findings from review. The pre-fix snapshot is at `versions/v6 2026-08-07 pre-task-3-review-fix/`. No commit, deletion, design edit, or plan edit was made.

### RED evidence

Focused command after adding the eight regression cases:

```bash
python3 -B -m unittest tests.test_validate_project -v
```

Result before the fixes: 29 tests ran with 7 failures and 4 errors.

- Reference mode rejected the global `-1` Auto sentinel.
- Generation feasibility was skipped when `accepted_source` was absent.
- Reversed declared shot order was silently sorted.
- Malformed array or object enum values raised four `TypeError` exceptions.
- Generation reference assets were not checked against the approved pack.
- JSON decimals were decoded through binary floats.
- Windows drive-qualified paths were accepted.
- Delivery mismatch diagnostics were emitted twice.

### Fixes

- All valid Seedance modes now accept `-1` Auto. Edit mode still requires `-1`; other modes also accept fixed integers from 4 through 30.
- Fixed and Auto requests are checked against the frame-derived shot duration even before any source is accepted. Auto capacity is conservatively capped at 30 seconds.
- Timeline continuity is evaluated in declared array order. Reversed EDL entries produce `timeline.order` and are never silently sorted.
- Every enum membership check verifies scalar type first, so valid malformed JSON produces diagnostics rather than exceptions.
- Every direct or array-based generation asset ID must resolve to the supplied pack or explicitly approved generated pack. Fixtures and the example now register the derived master-audio guide.
- Strict JSON uses `parse_float=Decimal`, preserving the exact decimal token before target-frame math.
- Relative-path validation rejects both backslash traversal and Windows drive-qualified paths.
- The duplicate delivery-comparison branch was removed, leaving one delivery mismatch diagnostic per field.

### GREEN evidence

Focused verification:

```bash
python3 -B -m unittest tests.test_validate_project -v
```

Result: all 29 validator tests passed with no warnings or tracebacks.

Full verification:

```bash
python3 -B -m unittest discover -s tests -v
```

Result: all 49 repository tests passed with no warnings or tracebacks.

Direct CLI verification retained the contract: the example exits 0, and the gap fixture exits 1 with one deterministic `timeline.gap` diagnostic.
