# Music Analysis and Treatment

## Outcome

Turn the exact authorized master into a time-based creative brief before paying for video. The analysis must explain what the music is doing, what is known versus uncertain, and how each proposed visual choice responds to the track, lyrics, brief, or approved references.

Music-video energy means music-responsive change. It does not mean uniform speed, a fixed cut count, or a hypercut treatment. A quiet drone may need a long evolving frame and one precisely timed release. A dense dance section may support rapid inserts and hard visual accents. Preserve contrast so the peak can feel like a peak.

## Preserve the source

1. Keep the supplied master read-only.
2. Record its SHA-256 hash, measured decoded duration, sample rate, channel count, and source path in the private manifest.
3. Analyze a proxy or decoded stream. Do not normalize, stretch, remix, trim, fade, or replace the master.
4. Use the exact release master that will be muxed into the delivery. Do not plan against a streaming preview or an earlier mix.

Run the local technical pass from the skill root:

```bash
python3 -B scripts/analyze_audio.py "<master-audio-path>" --output "<new-analysis-json-path>"
```

When authorized lyrics are supplied, add `--lyrics "<lyrics-path>"`. The analyzer records the lyrics-file hash but does not emit the lyric body. It returns energy windows, silence regions, onset candidates, tempo candidates, and confidence. These are candidates, not musical ground truth.

## Lyric and language branch

Use this order:

1. Prefer lyrics supplied or approved by the rights holder.
2. Record the language, point of view, speaker, addressee, repeated hooks, narrative turns, named entities, sensitive content, and any supplied translation.
3. If lyrics are absent, upload an analysis copy and use Scenario `model_scenario-audio-to-text`. Refresh its live schema first. The 2026-08-07 snapshot requires a `file`, supports `modelSize` through `large-v3`, accepts a blank autodetect or ISO language code, uses `task: transcribe` or `translate`, and exposes `vadFilter`. Prefer `large-v3`, the known or autodetected ISO language, `task: transcribe`, and `vadFilter: true` unless the refreshed schema or source requires another choice. Preserve its segment-level timing and mark uncertain words, language, and speaker interpretation as uncertain.
4. Do not claim word-level lyric alignment when only segment-level timing is available.
5. Compare the transcript with the audio. Ask for correction only when a disputed phrase would materially change story, representation, safety, or synchronization.
6. Never invent a missing lyric, translation, name, claim, or story detail. Use a thematic or instrumental visual branch for unresolved passages.

Sung vocals, layered harmonies, ad-libs, distortion, and heavy effects can reduce transcription accuracy. If vocals are masked, and only when the user has authorized the source and approved analysis spend, optionally dry-run `model_ace-step-1-5-edit-stem-extract`. If approved, extract a vocal stem and transcribe that stem. Label the result as machine-assisted and uncertain. Do not replace or remix the final master with the stem.

Scenario `asset_analyze` does not analyze audio. It can help with approved images or text, but it cannot substitute for local audio analysis or Scenario transcription.

For an instrumental track, set the lyrics state to instrumental. Do not fabricate a vocalist or narrative. Build from form, rhythm, texture, dynamics, timbre, spatial movement, emotional progression, and the user's brief.

## Complete song-analysis record

### Technical facts

- immutable source hash and exact decoded duration
- codec, sample rate, channels, and known mix version
- energy windows, silence regions, large transients, and clipping observations
- tempo candidates and confidence, including half-time, double-time, swing, rubato, and tempo-change possibilities

### Musical form and sync

- intro, verse, pre-chorus, chorus, refrain, bridge, drop, breakdown, solo, coda, and outro where applicable
- phrase boundaries, downbeat candidates, pickups, rests, fills, impacts, vocal entries, breaths, held notes, and final transient
- hook recurrence and variation
- density, dynamics, tension, release, and negative space
- instrumentation, production texture, timbre, register, stereo movement, and notable sound-design events

### Meaning and feeling

- lyrics, language, translation status, point of view, and certainty
- story, conflict, progression, emotional turns, tone, and intended audience effect
- concrete images, metaphors, symbols, recurring words, and visual opportunities
- sensitive themes, cultural context, representation risks, and phrases that must not be literalized
- brand, product, performer, or release objective supplied by the user

## Verify the music manually

Listen through the complete master while viewing the waveform. Correct obvious grid mistakes. A pulse detector can lock to subdivisions, skip a quiet downbeat, or drift through rubato. Mark each sync event as verified, likely, or speculative.

Build a sync map with exact master-relative timecodes:

| Time | Section | Event | Confidence | Visual function | Density |
|---|---|---|---|---|---|
| `[00:00.000]` | `[section]` | `[entry, phrase, hit, silence, texture change]` | `[verified, likely, speculative]` | `[reveal, hold, cut, transition, performance cue]` | `[low, medium, high]` |

Use the sync map to shape the edit. Do not force a cut on every beat. A held visual can make a later cut stronger.

## Write three free treatments

Before any Seedance video spend, draft three genuinely different text treatments using `assets/treatment-template.md`. Each must be traceable to the same analysis and brief, but should vary the organizing idea, not only color or lens.

Each treatment defines:

- one-line concept and audience promise
- format: performance-led, narrative, abstract, product-led, or a justified hybrid
- emotional arc by song section
- identity, product, and world anchors
- visual law, color progression, lighting, optics, and camera behavior
- five reusable shot families: performance, human-world tableau, kinetic insert, symbolic object, and transition plate, adapted when a family does not fit
- two or three recurring motifs and how they evolve
- section-specific information density, breathing room, one optional peak-density passage, and a deliberate ending image
- reference requirements and which references must be generated
- known rights, feasibility, safety, and budget risks

Score the three treatments against musical fit, lyrical integrity, brief fit, reference feasibility, continuity, production risk, cost, and release safety. Select one with the user before generating the reference pack or paid Seedance video. Preserve the rejected options as alternatives, not hidden defaults.
