# Scenario Production Workflow

## Contents

- [Principle](#principle)
- [One-round intake](#1-one-round-intake)
- [Resolve the workspace and live tools](#2-resolve-the-workspace-and-live-tools)
- [Upload supplied media](#3-upload-supplied-media)
- [Analysis spend gate](#analysis-spend-gate)
- [Reference spend gate](#reference-spend-gate)
- [Seedance video spend gate](#seedance-video-spend-gate)
- [Audio and moderation boundary](#audio-and-moderation-boundary)
- [Rights and release safety](#rights-and-release-safety)
- [Private run record](#private-run-record)

## Principle

Scenario is the production workspace for assets, reference creation, transcription, model discovery, Seedance generation, job recovery, and review. Keep deterministic audio analysis, timeline validation, assembly, and delivery verification local.

Use one consolidated intake, one approved visual system, one complete timeline, and bounded spend gates. Do not begin video generation while fundamental creative choices are still moving.

## 1. One-round intake

Copy `assets/intake-template.md` into the private project record and gather all missing decisions in one message. In particular, ask:

> Do you have a reference image, visual style, character, performer, product, logo, wardrobe, location, or world that the video must preserve?

Also gather the Scenario team and project names, exact authorized master, rights status, lyrics and language, optional translation or stems, release objective, artist or brand, story, required moments, platforms, canvas, frame rate, version count, deadline, spending ceiling, exclusions, safety constraints, exact post-produced text, and human approver.

If the user delegates creative choices, make them from the music analysis and explain the selected treatment. Do not infer demographic identity, geography, era, subculture, wardrobe, or genre stereotypes from audio alone.

## 2. Resolve the workspace and live tools

Use the tools in this order:

1. `teams_list`: show accessible names and confirm the intended team.
2. `projects_list`: use the confirmed `team_id`, show project names, and confirm the exact project.
3. `search`: search public models for Seedance 2.5 in that workspace.
4. `model_schema_get`: fetch `model_bytedance-seedance-2-5` and compare it with `references/model-contract.md`.
5. Resolve any other model, including transcription, stem extraction, or image generation, through `search` or `recommend`, then call `model_schema_get` for that exact model before use.

Store workspace IDs only in the private run record. Never put them in the portable skill, prompt example, source ledger, or public repository.

## 3. Upload supplied media

Reuse existing Scenario asset IDs when the user confirms they are the right source. Otherwise upload each local master, image, video, or authorized text asset with `upload_asset` and, for multipart uploads, `upload_asset_complete`.

- Use inline base64 only when the current `upload_asset` schema permits it and the file is below its documented limit. Persist the returned asset ID and do not complete an inline upload again.
- Use multipart upload for larger files. Start with `upload_asset`, follow each returned part instruction exactly, then call `upload_asset_complete` on that same upload.
- Persist only the resulting asset ID in the private manifest.
- Do not log or preserve temporary upload or download URLs.
- Keep reference arrays ordered and role-map every resulting asset.

The master upload is an analysis and conditioning copy. It does not replace the immutable local master that will be muxed into the final MP4.

## Analysis spend gate

Run free local technical and music analysis on the exact master first. Use supplied lyrics before transcription. `asset_analyze` can inspect supplied images or text, but it does not analyze audio.

A paid Scenario analysis call is allowed only when needed for missing lyric transcription or an authorized masked-vocal stem:

- Use `model_scenario-audio-to-text` for a first transcript with segment-level timing and explicit uncertainty.
- Use `model_ace-step-1-5-edit-stem-extract` only when authorized vocals are masked enough to block material understanding. The extracted stem is for analysis, never the final mix.

For either paid analysis operation:

1. Resolve the exact model and refresh its schema with `model_schema_get`.
2. Prepare the exact request and call `model_run` with `dry_run: true`.
3. Show the estimate, scope, uncertainty, and reason the paid analysis is needed.
4. Obtain explicit approval for that bounded analysis request.
5. Submit one asynchronous call with the approved parameters.
6. Persist its job ID immediately, then use `jobs_wait` on that same ID until completion.
7. Display or inspect the result, retain uncertainty, and never launch a replacement because a wait timed out.

After the free analysis and any approved analysis call, create three free treatments from the analysis and brief. Select one treatment before any paid reference creation. Feed creative reasoning the local analysis JSON, transcript summary, brief, and supplied visual references.

## Reference spend gate

Paid reference creation can begin only after the free technical and music analysis, three free treatments, and selected treatment exist. It does not require a locked continuity bible, complete EDL, or animatic, because the approved reference pack is what makes those artifacts lockable.

### When references are supplied

Select the smallest set that establishes required identity, product geometry, wardrobe, world, motion, or visual law. Map each asset to one primary role and explicit exclusions. Reject contradictory, low-quality, unauthorized, watermarked, or irrelevant inputs. Assemble the viable assets into a proposed pack and obtain explicit approval for that pack. No paid reference run is needed.

The canonical manifest requires `approval: approved` for this supplied pack. Supplied assets are not implicitly approved merely because the user uploaded them.

### When references are absent or incomplete

Create them in Scenario before Seedance video generation:

1. Derive a reference brief from the selected treatment and its draft identity, world, product, wardrobe, lighting, and ending-image requirements.
2. List only the stills needed to lock the system, such as performer or character turnaround, wardrobe, product form, key location, palette and lighting board, or ending composition.
3. Use `recommend` or `search` to choose a Scenario image model appropriate to those assets.
4. Call `model_schema_get` for the exact image model.
5. Prepare the smallest bounded request and call `model_run` with `dry_run: true`.
6. Show the estimate and obtain explicit approval for this exact paid reference scope.
7. Submit one bounded reference run asynchronously, persist its job ID, wait on the same ID, then display and inspect every result.
8. Regenerate only a diagnosed missing reference. Any paid request change requires another dry run, estimate, and explicit approval.
9. Assemble the accepted stills into a role-mapped reference pack and obtain explicit approval before Seedance video spend.

Reference approval checks identity, representation, product accuracy, wardrobe, world, visual law, rights, safety, and suitability across the full song. A beautiful still that cannot sustain continuity is not an approved anchor.

The approved pack then locks the continuity bible and animatic. Apply its identity, world, camera, color, product, and motif decisions to the continuity bible. Complete the frame-based EDL with no gaps, then replace animatic placeholders with the approved reference states across the full timeline.

## Seedance video spend gate

This planning gate applies only to paid Seedance video generation. It does not block the separately gated analysis or reference prerequisites above.

No paid Seedance video generation may begin until all of the following are ready:

- immutable-master hash and technical analysis
- lyric or instrumental state with uncertainties
- selected treatment
- approved reference pack
- locked continuity bible
- complete no-gap EDL
- still animatic or labeled placeholder cut covering the full master
- chapter budget, recovery reserve, and spend ceiling
- exact Seedance live schema retrieved for this session

### One proof shot

Select the most informative difficult hero, hook, chorus, drop, or identity-critical shot. The proof should test the riskiest combination of identity, motion, camera, world, reference conditioning, and editability. Run a proof-shot dry run before its paid call:

1. Build the exact intended parameters with `generateAudio: false`.
2. Call `model_run` with `dry_run: true`.
3. Confirm that the response is a dry run and creates no paid job.
4. Show the estimate, what the proof tests, and the remaining reserve.
5. Obtain explicit approval for this exact bounded paid request.
6. Send the same request once asynchronously, using `wait: false` when the live tool exposes that field.
7. Persist the returned job ID immediately.
8. Call `jobs_wait` on that same job ID.
9. Display the output with `asset_display`, inspect full playback and dense frames, and download only when local QA or assembly requires it.

If `jobs_wait` reports pending work or a timed out wait, call `jobs_wait` again only on the pending original IDs. Never create a replacement `model_run` because a wait budget expired.
The persisted job id is the recovery key for every subsequent wait and inspection.

### Produce by chapter

After the proof is accepted:

1. Dry-run the exact requests for one complete song chapter and show their combined estimate.
2. Obtain explicit approval for that bounded chapter.
3. Submit one asynchronous run per approved candidate, once each, and persist every job ID before waiting.
4. Inspect each result before starting a dependent shot or continuity handoff.
5. Record accepted coverage, rejected coverage, source trims, and the one-variable hypothesis for any recovery.
6. Update the animatic with accepted footage and confirm timeline coverage.
7. Continue chapter by chapter within the approved ceiling.

Reserve 20 to 30 percent of the approved budget for recovery. Do not consume the reserve on cosmetic variants while timeline coverage or identity continuity remains incomplete.

## Audio and moderation boundary

The supplied music is analyzed before visual generation because it defines timing, story, tone, and energy. Seedance shots remain silent with `generateAudio: false` so the model footage can be evaluated cleanly and the final master can be muxed deterministically.

This silent-generation workflow is for fidelity and deterministic mastering, never moderation evasion. Do not split, disguise, replace, pre-generate, or separately route audio to avoid a safety system. If a legitimate source or prompt is rejected, identify the applicable policy, revise the creative treatment within it, or stop and request human review.

## Rights and release safety

Before generation and again before release, confirm rights and intended usage for the master, composition, lyrics, samples, stems, choreography, performers, faces, voices, characters, brands, products, logos, footage, locations, and references.

Review:

- real-person consent and likeness use
- minors and age ambiguity
- sexualization, explicit themes, weapons, unsafe acts, and illegal behavior
- cultural stereotyping, protected traits, and contextual misrepresentation
- unsupported product or marketing claims
- accidental logos, captions, watermarks, and copyrighted elements
- rapid flashes, high-contrast flicker, strobing, and photosensitivity risk
- truthful gameplay, product behavior, and platform policy

Require a human release approval. Add warnings or revise flashing sequences when photosensitivity risk exists. Exact titles, lyrics on screen, logos, legal copy, credits, subtitles, and claims must be supplied and composited in post-production.

## Private run record

Persist model and schema date, ordered references and roles, prompts, parameters, dry-run estimates, approvals, job IDs, output IDs, known cost, acceptance, reroll diagnosis, local accepted-source path, master hash, QA, and human release approval. Do not persist credentials or temporary signed URLs.

For every shot, update the canonical `production` record. Its disposition summarizes the latest attempt. Each attempt record preserves the exact dry-run estimate and approval before a call, then the returned job ID, output ID, known cost, acceptance, and reroll diagnosis as they become available. Leave job and output IDs null before Scenario returns them. Leave attempts empty before the first dry run. If the user rejects a proposed request before any job exists, preserve it and append a revised pending request without a reroll diagnosis. A timed-out attempt stays current until its original job is inspected again, and an accepted local source requires one accepted attempt. Omit `accepted_source` until its complete object exists.
