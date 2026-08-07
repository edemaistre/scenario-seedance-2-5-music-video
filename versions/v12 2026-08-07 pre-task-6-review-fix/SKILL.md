---
name: scenario-seedance-2-5-music-video
description: Use when turning an authorized music master of at least 30 seconds into a finished music video with Scenario Seedance 2.5, including music analysis, visual planning, production, assembly, and delivery QA.
---

# Scenario Seedance 2.5 Music Video

Create a fully assembled MP4 whose supplied master audio remains the final soundtrack. The music drives the visual pacing. Do not infer identity, location, era, wardrobe, or genre stereotypes from audio alone.

## Non-negotiable rules

- Accept only an authorized master with a measured duration of 30 seconds or longer.
- Gather every missing input in one consolidated intake before starting production.
- Keep the original master read-only. Record its SHA-256 hash and analyze only a proxy or Scenario copy.
- Refresh the live Scenario model schema before each production session. The dated target is `model_bytedance-seedance-2-5`, but the live schema wins.
- Every Seedance music-video request must set `generateAudio: false`. `referenceAudio` is timing and energy conditioning only, never passthrough.
- Do not make paid calls before the analysis, treatment, continuity bible, complete EDL, and animatic are ready. Obtain explicit approval for the proof-shot spend.
- Never retry a timed-out paid job as a new job. Persist and inspect its original job ID first.
- Do not publish credentials, signed URLs, private IDs, copyrighted masters, complete lyrics, or user references.

## Workflow

### 1. One consolidated intake

Ask once for the Scenario team and project, master source and rights, artist or brand, release title, platforms, aspect ratio, resolution, frame rate, delivery deadline, version count, and spending ceiling. Also ask for lyrics, translation, cue sheet, stems, BPM, story, product or brand role, exact post-production text, references, visual exclusions, representation constraints, and release-rating requirements.

Explicitly ask whether a reference image, visual style, character, performer, product, or world must be preserved. If no viable visual reference exists, create a treatment and reference still pack in Scenario before video generation, then obtain approval for it.

### 2. Preserve and understand the music

Hash the immutable master. Build a private song analysis with measured duration, codec, sample rate, channels, loudness, peaks, silence regions, BPM candidates, downbeats, transients, sections, vocal entries, hooks, emotional turns, energy, texture, dynamics, and tonal progression.

Use supplied lyrics first. Otherwise, obtain a first transcript through Scenario Speech to Text, mark uncertainty, and ask for correction only when it would materially change the concept. Do not treat an automatic beat grid or sung transcription as ground truth. Verify them against the waveform and audible music.

### 3. Establish the visual system

Draft three text treatments before spending. Select one based on the track, brief, and approved references. The approved treatment defines the emotional arc, identity anchors, world, color law, optical behavior, camera rules, reusable shot families, recurring motifs, pacing, peak-density passage, and ending image.

Capture continuity decisions in a bible. Use the smallest high-signal role-mapped reference set. The Magnific reference is evidence for coherent structure only. Do not copy its cast, setting, wardrobe, palette, or signature treatment unless independently supported by the intake.

### 4. Plan the complete edit before generation

Create an exact-time EDL and still animatic that cover the complete measured master with no gaps. Plan by sections and musical phrases, not arbitrary 30-second blocks. Every shot needs an ID, timeline in and out, musical function, sync events, Seedance duration and handles, subject, action, camera, lens, lighting, palette, opening and closing composition, continuity state, reference roles, and acceptance fields.

Prefer 8 to 24 second anchor sequences for major sections. Use 4 to 8 second inserts, transitions, or recovery coverage only where the edit needs control. Extract very short moments from accepted longer coverage rather than generating one clip per beat.

### 5. Cost-gate production

First dry-run a difficult hero or chorus proof shot and state its estimate. After explicit approval, submit it asynchronously, persist the job ID, wait on that same job, and inspect the full result. If accepted, dry-run one full song section, show the combined estimate, then generate sequentially and inspect every result. Continue chapter by chapter within the approved budget.

Reserve 20 to 30 percent of the ceiling for targeted recovery. Diagnose a failed shot and change one variable per reroll. Use first-frame or first-and-last-frame mode for critical transitions, reference mode for most coverage, edit mode for one bounded repair, and extension only for literal boundary continuity allowed by the live schema.

### 6. Prompt silent, cuttable footage

For each shot, state its section function and visual goal, bind references by role and exclusion, preserve all identity and world invariants, map visible changes to relative musical timestamps, use one dominant action and camera behavior per beat, and specify the exact closing state. Request no generated audio, captions, logos, watermarks, or legal text.

### 7. Assemble against the master

Download accepted clips, then trim, slip, scale, crop, conform frame rate, and color-match video only. Cut on verified beats, phrases, transients, vocal entries, and energy changes. Build generated transition plates or use exact hard cuts. Add exact titles, logos, credits, subtitles, legal copy, and product UI deterministically in post-production.

Ensure visuals cover at least the master duration, then trim visuals to its exact measured duration. Explicitly map only the assembled video and supplied master audio into the final file. Stream-copy compatible audio. Otherwise perform one documented high-quality AAC encode without normalization, stretching, remixing, trimming, fading, or added silence.

### 8. QA before delivery

Watch the complete video with sound and muted. Inspect every cut and a dense frame grid for identity, anatomy, wardrobe, product geometry, screen direction, geography, color law, recurring motifs, transitions, accidental text, watermarks, malformed morphs, repeated coverage, and pacing plateaus.

Verify that the master starts at zero and ends intact, generated audio is absent, the delivery has the expected duration and channels, and sync remains correct at the start, midpoint, final peak, and last transient. Review rights and release risks including likenesses, brands, minors, unsafe acts, sexualization, stereotyping, strobing, and photosensitivity. Deliver only a playable MP4 with the supplied master as its soundtrack.

## Load detailed guidance when needed

- `references/model-contract.md`: live schema verification and Seedance request constraints.
- `references/music-analysis-and-treatment.md`: analysis record, lyric uncertainty, and treatment approval.
- `references/shot-design-and-prompting.md`: EDL, continuity, and prompt construction.
- `references/scenario-production.md`: proof-shot, budget, asynchronous job, and chapter controls.
- `references/assembly-and-qa.md`: deterministic FFmpeg assembly and delivery checks.
- `references/examples.md`: genre-neutral structural examples.
- `references/source-ledger.md`: evidence and provenance handling.
- `assets/intake-template.md`: consolidated intake and reference question.
- `assets/treatment-template.md`: three-treatment comparison and selection gate.
- `assets/continuity-bible-template.md`: identity, world, camera, motif, and handoff locks.
- `assets/music-video-manifest.example.json`: canonical frame-based project and EDL shape.
- `scripts/`: local audio analysis, manifest validation, assembly, and delivery verification.
