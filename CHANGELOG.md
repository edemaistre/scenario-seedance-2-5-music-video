# Changelog

## v2.0.0, 2026-08-12

Complete rewrite for simplicity and speed. The v1 skill was correct and unusable: it spent the
session producing documentation about the video instead of the video.

### The shape now

Five steps, matching how the work actually goes: song, lyrics, story, frames, video.

- Added the lyrics step, which v1 buried and which a real run skipped entirely. `song.py` reads the
  track and `model_scenario-audio-to-text` transcribes it.
- One edit format. A master, a frame rate, a size, and a list of shots with the time each starts.
  Shots run until the next one begins, so gaps are impossible by construction rather than by
  validation.

### Removed

- `validate_project.py`, 1186 lines enforcing a manifest with 23 mandatory planning keys per shot,
  exact key matching, decimal millisecond strings and a linear attempt lifecycle. Producing a valid
  document required writing a 400 line generator first. It never caught a defect in the picture.
- `assemble_music_video.py` and `verify_delivery.py`, replaced by `build.py`, which does both in one
  ffmpeg pass. The 60 second reference build went from 42 seconds to 4.7.
- `analyze_audio.py`, replaced by `song.py`. Same loudness figures, plus sections, a corrected tempo
  estimate and ready to use cut points.
- `package_skill.py`, the treatment and continuity templates, six of the seven reference documents,
  the OpenAI agent manifest, and `llms-full.txt`.

Net: about 2900 lines of Python down to about 500, 113 tests down to 26 that exercise the delivery
contract rather than the schema.

All of it is preserved in `versions/v26 2026-08-12 pre-simplification-rewrite/`.

### Fixed

- **The master could be silently truncated.** `-frames:v` ends the whole output once the video
  reaches the limit, so any master running past the last video frame lost its tail. Caught by the new
  tests. The trim filter already fixes the frame count, so the limit is gone.
- **Bit exactness reported false negatives.** The mp3 muxer writes an ID3v2 header carrying container
  metadata, so identical audio frames hashed differently coming from a bare `.mp3` than from inside an
  `.mp4`. Extraction now strips metadata.
- Tempo estimation reported half time and third time as confidently as the real pulse. It is now
  weighted toward what people hear: a track that read as 55 BPM now reads as 112.
- A master in a codec MP4 cannot carry used to fail the build outright. It now takes one documented
  AAC encode and says so.

### Learned, and written down

`references/seedance.md` records the finding that cost the most: in reference-to-video mode Seedance
2.5 anchors frame one to the base state of the reference world, and no prompt wording overrides it.
Four paid attempts failed to change it. First frame mode fixed it immediately. It also records
measured costs, and why a sparse contact sheet will make you pay to reroll a shot that was never
broken.

## v1.0.0, 2026-08-07

First release. Skill, deterministic media tools, production references, 113 tests, packaging and a
Scenario dry run smoke test.
