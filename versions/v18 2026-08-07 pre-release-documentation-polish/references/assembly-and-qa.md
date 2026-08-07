# Assembly and Delivery QA

## Delivery contract

The final MP4 uses the supplied authorized master as its only audio track. Accepted Seedance clips contribute video only. The master starts at timeline zero and remains unchanged in duration, speed, gain, channel layout, and mix, except for one required delivery-codec conversion when its codec cannot be stored in MP4.

Keep the source master immutable. Verify its SHA-256 against the manifest immediately before assembly and again during delivery verification.

## Prepare the local project

Keep every manifest media path relative to one private project root:

```text
<project-root>/
  masters/<authorized-master>
  analysis/<analysis-record>
  references/<approved-reference-files>
  clips/<accepted-downloaded-clips>
  manifests/<project-manifest.json>
  output/<new-delivery.mp4>
```

Do not place private media, full lyrics, workspace IDs, or signed URLs in the skill repository.

For each accepted shot, populate `accepted_source.path`, `trim_start_seconds`, and `trim_end_seconds` in the canonical manifest. Use the exact local file that passed review. Confirm the source trim is long enough for its declared frame interval and that shots cover the full master in chronological order.

## Lock the exact EDL

The manifest is the edit decision list:

- master path, SHA-256, decoded duration, sample rate, channels, and rights basis
- delivery geometry, aspect ratio, rational frame rate, and audio policy
- approved reference pack and lyrics state
- every shot's exact start and end frame
- accepted source path and source trim
- exact generation prompt, model, mode, parameters, and `generateAudio: false`

Represent edit boundaries as frames, not floating-point master time. The target is the ceiling frame count: `ceil(decoded master duration * fps_num / fps_den)`. The picture can therefore be less than one frame longer than the audio. Never shorten the master to remove that legal frame boundary. Use decimal seconds only for source trims. Resolve creative cut choices before deterministic assembly.

Validate from the skill root:

```bash
python3 -B scripts/validate_project.py "<project-manifest.json>"
```

Do not assemble while the validator reports an error. Recheck the refreshed live schema separately because the validator is a dated guardrail.

## Assemble silent visuals, then mux once

Run:

```bash
python3 -B scripts/assemble_music_video.py "<project-manifest.json>" "<new-output.mp4>" --project-root "<project-root>"
```

The assembler:

1. validates the manifest and safe project-relative paths
2. verifies the master hash and measured facts
3. trims accepted sources in declared order
4. discards all source clip audio
5. conforms video to the declared constant geometry and rational frame rate
6. produces the exact target visual frame count
7. explicitly maps the conformed video and original master audio
8. writes candidates inside a unique retained work directory, verifies them, and publishes the final path with an atomic no-replace hard link

Do not use generated clip audio, a reference-audio stream, or `-shortest` to hide incomplete visual coverage. If visuals are short, repair the EDL or accepted coverage first.

## Master-audio policy

- For MP4-compatible AAC, MP3, or ALAC masters, stream-copy the supplied compressed audio stream when the actual container combination is supported.
- For WAV, FLAC, or another incompatible master, encode audio once to AAC at 320 kbps for the MP4.
- Do not apply normalization, gain, compression, limiting, equalization, resampling for creative effect, time stretch, remix, trim, fade, or added silence.
- Do not move the master start. Timeline zero is audio zero.
- Record whether the output used `stream_copy` or `aac_320k`.
- If lossless or sample-preserving audio is a release requirement, create a separately approved archival MOV or MKV after checking its container contract. Do not mislabel an AAC MP4 as lossless.

## Verify programmatically

`scripts/verify_delivery.py` exposes a Python function rather than a command-line interface:

```python
from pathlib import Path

from scripts.validate_project import load_manifest
from scripts.verify_delivery import verify_delivery

manifest = load_manifest(Path("<project-manifest.json>"))
report = verify_delivery(
    Path("<final-mp4>"),
    Path("<authorized-master>"),
    manifest,
)
if not report["passed"]:
    raise RuntimeError(report)
```

Archive the structured report in the private run folder. Verification must establish:

- one video stream and exactly one audio stream
- declared geometry and rational frame rate
- video and audio duration within one frame plus 20 milliseconds of the master
- audio start at zero, matching channels, and no cumulative drift
- no generated audio or extra source audio track
- unchanged original-master SHA-256
- compressed elementary-stream hash equality for stream-copy delivery
- an explicit non-bit-exact source status plus packet equality with a deterministic master-derived reference AAC for the single AAC transcode path

## Creative review

Watch the full music video with sound, then again muted. Do not approve from a thumbnail or successful job state.

Inspect:

- whether pacing follows section, rhythm, lyrics, tone, dynamics, timbre, and story
- whether slow passages have breathing room and dense passages remain comprehensible
- hook, motif recurrence, chapter contrast, peak-density passage, emotional release, and ending image
- performer or character identity, anatomy, hands, expression, wardrobe, choreography, and lip movement
- product geometry, object count, props, labels, screens, reflections, and ownership
- world continuity, geography, screen direction, camera direction, lens law, lighting direction, palette, and grain
- transition motivation, cut readability, repeated coverage, malformed morphs, accidental text, logos, and watermarks
- exact titles, captions, credits, product UI, legal copy, and CTA composited in post

Inspect every cut frame by frame and create a dense contact sheet across the full duration. Check the beginning, midpoint, each hook or chorus, every major transition, the final peak, and the last transient at normal speed.

## Audio and sync review

- Compare the final file with the original master at the beginning, midpoint, final hook or peak, and final transient.
- Confirm music begins at zero and ends intact.
- Confirm there is no normalization, stretch, remix, trim, fade, added silence, clipping, dropout, or channel change.
- Confirm no Seedance-generated audio remains, even quietly under the master.
- Verify visual sync against manually confirmed phrase boundaries and accents, not only the automatic onset list.
- Listen on studio monitoring and ordinary phone speakers when the release context warrants it.

## Rights, safety, and release review

Confirm release rights for the master, composition, lyrics, samples, performers, voices, choreography, brands, product designs, source media, and visual references. Require human approval for likenesses, claims, gameplay truth, legal copy, cultural context, and final release.

Review minors, unsafe acts, sexualization, weapons, explicit themes, stereotype risk, flashing images, strobing, rapid high-contrast cuts, and photosensitivity. Modify or warn when necessary. Check current platform aspect-ratio, safe-zone, caption, accessibility, age-rating, and ad-policy requirements at export time.

## Deliverables

Deliver at minimum:

- playable final MP4
- immutable source hash and final verification report
- canonical manifest with accepted source paths and provenance
- release notes stating audio mode, dimensions, frame rate, duration, and any separate finishing step
- optional placement-specific exports or archival audio-preserving container only when requested and verified

Never call a project complete if the output stops at prompts, generated clips, an animatic, or an unmuxed visual sequence. The required outcome is the fully assembled MP4 with the supplied master audio.
