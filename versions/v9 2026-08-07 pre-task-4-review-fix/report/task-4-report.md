# Status

Task 4 is implemented. The assembler requires a validation-clean manifest and one accepted source per shot, resolves all media beneath the supplied project root, conforms shots in declared frame order, creates the exact target frame count, and explicitly muxes only the conformed H.264 video with the supplied master audio. Compatible AAC, MP3, and ALAC streams are copied. Other codecs receive one AAC 320 kbps encode with no audio processing.

# Test summary

- Required RED recorded: `python3 -B -m unittest tests.test_assemble_music_video -v` failed with `ModuleNotFoundError` before the assembler existed.
- CLI regression RED recorded: direct execution outside the repository failed on the sibling validator import before the focused fix.
- Master coverage RED recorded: a five-second real master paired with a stale thirty-second manifest was initially accepted before the coverage check.
- Assembly suite: all 7 tests passed.
- Full suite: all 56 tests passed.
- Synthetic FFmpeg artifacts remain under `/private/tmp/scenario-seedance-assembly tests-*` as required.

# Concerns

- The conformed `.visual.mp4` intermediate is intentionally retained beside each delivery because cleanup would violate the no-delete rule.
- No earlier deliverables were edited. No commit or deletion was performed.
