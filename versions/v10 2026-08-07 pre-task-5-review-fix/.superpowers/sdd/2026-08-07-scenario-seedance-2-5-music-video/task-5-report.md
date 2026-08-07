# Task 5 Delivery Verifier Report

## Scope

Created only:

- `scripts/verify_delivery.py`
- `tests/test_verify_delivery.py`
- this report

The verifier probes the final MP4 and original master with argv-array FFprobe and FFmpeg commands. It verifies the manifest master SHA-256, exactly one video and audio stream, geometry, rational frame rate, target frame count, duration tolerance, channels, and zero audio start. It retains uniquely named `/private/tmp/scenario-seedance-delivery-*` elementary-stream artifacts for copied AAC, MP3, and ALAC comparison.

For compatible copied codecs, compressed packet data is extracted deterministically and SHA-256 compared. A mismatch is reported as altered or generated audio. For a transcode, the report explicitly marks audio as not bit-exact while retaining timing and stream-fact checks.

## TDD Evidence

RED command, run before implementation:

```text
python3 -B -m unittest tests.test_verify_delivery -v
```

Result: 1 test module error, expected `ModuleNotFoundError: No module named 'scripts.verify_delivery'`.

Focused GREEN command:

```text
python3 -B -m unittest tests.test_verify_delivery -v
```

Result: 7 tests passed.

Covered cases: copied stream equality, wrong duration, no video, no audio, multiple audio, channel mismatch, wrong geometry, wrong frame rate, generated-audio replacement, and transcode status.

## Full Suite

Command:

```text
python3 -B -m unittest discover -s tests -v
```

Result: 71 tests run, 17 failures, 0 errors.

All 17 failures belong to the intentionally concurrent Task 6 RED contract. They require reference and template files that Task 6 is creating, including `references/*.md` and the three template files. No Task 5 verifier test failed. Re-run the full suite after Task 6 lands its files.
