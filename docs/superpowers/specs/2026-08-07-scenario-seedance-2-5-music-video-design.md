# Scenario Seedance 2.5 Music Video Skill Design

**Date:** 2026-08-07

**Status:** Approved by user direction. Emmanuel selected a fully assembled MP4 with the supplied master audio and delegated the remaining product decisions.

## Goal

Create a separate Agent Skill that turns an authorized music master of at least 30 seconds into a finished music video of any practical length. The skill must analyze the track, lyrics, rhythm, tone, energy, structure, and story, build or use visual references, generate multiple Seedance 2.5 shots through Scenario MCP, edit them on the master timeline, preserve the supplied music, and deliver a quality-checked MP4.

## Selected Approach

Use a hybrid anchor-sequence workflow.

- Treat the original master audio as the immutable timeline and final soundtrack.
- Generate 8 to 24 second anchor sequences for major song sections.
- Generate 4 to 8 second inserts, transitions, or recovery shots only where the edit needs more control.
- Use the smallest high-signal reference set and stable identity anchors across the project.
- Assemble locally with deterministic FFmpeg tooling, then mux the supplied master once.

This is preferred over mostly 30 second chapters because it gives better musical timing and lower reroll risk. It is preferred over generating every micro-shot separately because it reduces cost and identity drift.

## Core Creative Principle

Music-video energy means visible response to the specific music, not constant speed. A fast track may justify dense cuts, acceleration, impact frames, and aggressive camera motion. A slow or ambient track may use long evolving frames, restrained motion, scale changes, and precisely timed visual releases. Every pacing choice must be justified by the supplied music, lyrics, brief, or approved references.

Do not infer ethnicity, location, wardrobe, subculture, era, or genre stereotypes from the audio alone.

## Intake and Reference Policy

Gather all missing information in one round:

- Scenario team and project
- master-audio file or Scenario asset ID, rights status, release title, artist or brand, and intended platforms
- desired output aspect ratio, resolution, frame rate, version count, deadline, and spend ceiling
- lyrics, translation, cue sheet, stems, or known BPM if available
- story, message, required moments, product or brand role, CTA, credits, and exact text for post-production
- reference images, style references, character or performer references, wardrobe, locations, products, logos, and footage
- visual exclusions, sensitive themes, representation constraints, and release-rating requirements

Explicitly ask whether the user has a reference image, visual style, character, performer, product, or world to preserve. If they do, upload and role-map only the strongest references. If they do not, create a treatment and generate reference stills in Scenario before video generation. Require approval of the reference pack before Seedance spending.

## Music and Lyric Analysis

Keep the master read-only and record its SHA-256 hash. Analyze a proxy or Scenario copy.

Produce a private song-analysis record containing:

- exact measured duration, codec, sample rate, channels, loudness, peaks, and silence regions
- BPM candidates with confidence, tempo changes, beat and downbeat markers, and major transient accents
- song sections such as intro, verse, pre-chorus, chorus, bridge, solo, breakdown, drop, and outro
- vocal entries, breaths, instrumental gaps, hooks, repeated phrases, and emotional turns
- energy, density, timbre, texture, dynamics, tension, release, and tonal progression
- lyric themes, point of view, setting, characters, symbols, narrative arc, and visual opportunities

Use supplied lyrics first. Otherwise, use Scenario Speech to Text for a first transcript. Sung transcription can be imperfect, so compare it with the audio and ask for correction only when a lyrical misunderstanding would materially change the concept. If vocals are masked and the user has authorized paid analysis, optionally dry-run Scenario stem extraction, isolate vocals, and transcribe that stem. Never publish or store full copyrighted lyrics in public examples or provenance. Store themes, timestamps, and only the minimum necessary excerpts.

Use local audio analysis for technical facts and beat candidates. Do not present an automatic beat grid as ground truth. Verify the grid against the waveform and audible downbeats.

## Treatment and Visual System

Create three free text treatments before spending, then select one based on the track and brief. Each treatment defines:

- one-line concept and emotional arc
- performer-led, narrative, abstract, product-led, or hybrid format
- identity anchors and silhouette
- world vocabulary and recurring locations
- color law and lighting progression
- two primary lens or optical behaviors plus one exception
- camera movement rules
- five reusable shot families: performance, human-world tableau, kinetic insert, symbolic object, and transition plate
- two or three recurring motifs
- section-specific pacing and one peak-density passage
- ending image and release behavior

The Magnific reference is evidence for structure, not a house style. Its reusable principles are coherent identity, recurring shot families, motif-driven transitions, selective visual rules, phrase-shaped pacing, and a deliberate outro. Do not copy its cast, locations, monochrome treatment, fisheye signature, wardrobe, or color accents unless the new track independently supports them.

## Timeline and Shot Planning

Build an exact-time edit decision list before video spending. Every planned shot records:

- unique shot ID and song section
- master timeline in and out
- musical function, lyrics or theme, and sync events
- requested Seedance duration and visual handles
- shot family, subject, action, camera, lens, lighting, palette, and transition logic
- opening and closing composition
- continuity state and reference roles
- source path or Scenario asset ID after acceptance
- approval, cost, job, and disposition fields

Cover the full measured master duration without gaps. Use section boundaries and musical phrases, not arbitrary 30 second blocks. Request visual handles because edit points are often fractional while Seedance durations are whole seconds. Extract sub-four-second moments from longer accepted coverage rather than paying for one generation per beat.

Complete a still animatic or labeled placeholder timeline before video generation. This proves full-song coverage and pacing before costs scale.

## Seedance Production

Refresh the live model schema before every production session. The dated target is `model_bytedance-seedance-2-5`, currently 4 to 30 seconds or Auto, 480p or 720p, and MP4 or MOV. The live schema always wins.

Use `referenceAudio` only as rhythm, pacing, or energy guidance. It is not audio passthrough. Set `generateAudio: false` for every music-video shot. If the live schema stops allowing silent output with audio conditioning, stop and report the drift.

For each shot prompt:

1. State the visual goal and section function.
2. Bind every reference by role and exclusion.
3. State identity, product, wardrobe, and world invariants.
4. Map visible changes to segment-relative musical timestamps.
5. Use one dominant subject action and one dominant camera behavior per beat.
6. Define the exact closing state for the next cut.
7. Add only diagnosed failure-prevention constraints.
8. Request no generated audio, captions, logos, watermarks, or legal text.

Use first-frame or first-and-last-frame mode for critical transitions. Use reference mode for most coverage. Use edit mode for one bounded repair. Use extension only for literal boundary continuity and only according to the live schema.

## Cost and Approval Gates

No paid generation occurs before the song analysis, selected treatment, continuity bible, complete shot manifest, and animatic exist.

1. Dry-run one difficult hero or chorus proof shot.
2. Obtain explicit approval for that bounded paid run.
3. Generate asynchronously, persist the job ID, wait on the same job, and inspect the full result.
4. If it passes, dry-run one complete song section and show the combined estimate.
5. Generate sequentially within the approved section and inspect each result.
6. Continue section by section while accepted coverage and remaining budget stay on plan.

Reserve 20 to 30 percent of the ceiling for targeted recovery. Change one diagnosed variable per reroll. A wait timeout never authorizes another paid call.

## Assembly and Master Audio

Download accepted clips and assemble them mute on the locked master timeline.

- Trim, slip, scale, crop, conform frame rate, and color-match video only.
- Cut on verified beats, phrases, transients, vocal entries, and energy changes.
- Use generated transition plates or exact hard cuts. Avoid generic effects that are not part of the treatment.
- Add exact logos, titles, credits, subtitles, legal copy, and product UI in deterministic post-production.
- Ensure the visual track is at least as long as the measured master, then trim it to the exact delivery duration.
- Explicitly map only the assembled video and supplied master audio into the final file.

If the supplied audio codec is MP4-compatible, stream-copy it. If it is WAV, FLAC, or another incompatible codec, create the requested MP4 with one documented high-quality AAC encode that does not normalize, time-stretch, remix, trim, fade, or add silence. Optionally retain an archival MOV or MKV with exact audio stream preservation.

## Quality Gates

Creative QA:

- watch the complete video with sound and again muted
- inspect every cut and a dense frame grid
- verify identity, anatomy, wardrobe, product geometry, props, screen direction, geography, color law, motif recurrence, and transition readability
- confirm visual pacing follows the track and includes intentional contrast, breathing room, peak density, and resolution
- reject accidental text, watermarks, lip-sync failures, repeated coverage, malformed morphs, and visual plateaus

Audio and sync QA:

- confirm the master starts at timeline zero and ends intact
- confirm no generated or reference audio remains
- compare master and delivery durations, channels, codec path, and audio disposition
- check sync at the beginning, midpoint, final chorus or peak, and final transient
- confirm no cumulative drift, normalization, time stretch, trim, fade, or added silence

Release QA:

- confirm rights for master, lyrics, performers, likenesses, choreography, brands, products, and references
- check weapons, unsafe acts, minors, sexualization, cultural stereotyping, explicit themes, strobing, and photosensitivity
- do not split audio or alter workflow to evade moderation
- use silent Seedance generation for fidelity and deterministic mastering, not censorship evasion

## Packaged Skill Structure

The installable archive contains only operational files:

- `SKILL.md`
- `agents/openai.yaml`
- `references/model-contract.md`
- `references/music-analysis-and-treatment.md`
- `references/shot-design-and-prompting.md`
- `references/scenario-production.md`
- `references/assembly-and-qa.md`
- `references/examples.md`
- `references/source-ledger.md`
- `assets/intake-template.md`
- `assets/treatment-template.md`
- `assets/continuity-bible-template.md`
- `assets/music-video-manifest.example.json`
- `scripts/analyze_audio.py`
- `scripts/validate_project.py`
- `scripts/assemble_music_video.py`
- `scripts/verify_delivery.py`

Repository-only files include tests, design documents, plans, README, CLAUDE, CHANGELOG, BUGS, ROADMAP, CI, and version history.

## Completion Contract

The skill is complete when a fresh agent can take an authorized master of at least 30 seconds, ask once for references and constraints, create missing visual references through Scenario, analyze the song and lyrics, plan and cost-gate a coherent multi-shot production, generate silent Seedance footage, assemble a full music video, mux the supplied master, and verify a playable MP4 without claiming unsupported model behavior.
