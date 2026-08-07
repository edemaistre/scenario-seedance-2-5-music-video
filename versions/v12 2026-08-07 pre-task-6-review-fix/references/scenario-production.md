# Scenario Production Workflow

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

## 4. Analyze music and create three treatments

Run local analysis on the exact master. Use supplied lyrics first. If needed, resolve and use Scenario `model_scenario-audio-to-text`, preserving segment-level timing and uncertainty. Before a paid transcription or stem call, refresh that model's schema, dry-run the exact request, show the estimate, obtain explicit approval, run it once asynchronously, and recover it through the same job ID. If vocals are masked, stem extraction is optional, paid, and allowed only for an authorized source after that gate.

Create three free text treatments from the analysis and brief. Select one before reference-image spend. `asset_analyze` can inspect supplied images or text, but it does not analyze audio. Feed creative reasoning the local analysis JSON, transcript summary, brief, and approved visual references.

## 5. Build or create the reference pack

### When references are supplied

Select the smallest set that establishes required identity, product geometry, wardrobe, world, motion, or visual law. Map each asset to one primary role and explicit exclusions. Reject contradictory, low-quality, unauthorized, watermarked, or irrelevant inputs.

### When references are absent or incomplete

Create them in Scenario before Seedance video generation:

1. Derive a reference brief from the selected treatment and continuity bible.
2. List only the stills needed to lock the system, such as performer or character turnaround, wardrobe, product form, key location, palette and lighting board, or ending composition.
3. Use `recommend` or `search` to choose a Scenario image model appropriate to those assets.
4. Call `model_schema_get` for the exact image model.
5. Prepare the smallest bounded reference-generation request, run `model_run` with `dry_run: true`, show the estimate, and obtain explicit approval for that paid reference run.
6. Run it once asynchronously, persist its job ID, wait on the same ID, then display and inspect every result.
7. Regenerate only a diagnosed missing reference, with another dry run if a paid parameter changes.
8. Assemble the approved stills into a role-mapped reference pack and obtain user approval before any Seedance video spend.

Reference approval checks identity, representation, product accuracy, wardrobe, world, visual law, rights, safety, and suitability across the full song. A beautiful still that cannot sustain continuity is not an approved anchor.

## 6. Complete the planning gate

Before Seedance video spend, require all of the following:

- immutable-master hash and technical analysis
- lyric or instrumental state with uncertainties
- selected treatment
- approved reference pack
- continuity bible
- complete frame-based EDL with no gaps
- still animatic or labeled placeholder cut
- chapter plan, recovery reserve, and spend ceiling
- exact model schema retrieved for this session

## 7. Dry-run one proof shot

Select the most informative difficult hero, hook, chorus, drop, or identity-critical shot. The proof should test the riskiest combination of identity, motion, camera, world, reference conditioning, and editability.

1. Build the exact intended parameters with `generateAudio: false`.
2. Call `model_run` with `dry_run: true`.
3. Confirm that the response is a dry run and creates no paid job.
4. Show the estimate, what the proof tests, and the remaining reserve.
5. Obtain explicit approval for this exact bounded paid request.
6. Send the same request once with asynchronous waiting, using `wait: false` when the live tool exposes that field.
7. Persist the returned job id immediately.
8. Call `jobs_wait` on that same job ID.
9. Display the output with `asset_display`, inspect full playback and dense frames, and download only when local QA or assembly requires it.

If `jobs_wait` reports pending work or a timed out wait, call `jobs_wait` again only on the pending original IDs. Never create a replacement `model_run` because a wait budget expired.

## 8. Produce by chapter

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
