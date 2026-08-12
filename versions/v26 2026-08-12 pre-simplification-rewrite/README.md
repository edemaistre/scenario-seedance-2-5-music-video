# Scenario Seedance 2.5 Music Video

An installable Agent Skill that turns an authorized music master of at least 30 seconds into one finished music-video MP4 through Scenario MCP and Seedance 2.5. It analyzes the exact track and lyrics, creates missing visual references, plans the complete song, controls generation spend, assembles silent footage, muxes the supplied master, and verifies delivery.

This public GitHub repository is available at: https://github.com/edemaistre/scenario-seedance-2-5-music-video

## Why this exists

Created from Emmanuel de Maistre's 2026-08-07 request for a reusable workflow that handles any genre, visual style, and practical song length without replacing the master, forcing a house style, or stopping at generated clips.

## What the skill decides

- Analyze the exact master, supplied lyrics, language, tone, rhythm, sections, dynamics, texture, hooks, emotion, and story.
- Ask once for reference images, style, character, performer, product, and world. Create and approve a compact Scenario reference pack when they are missing.
- Develop three treatments, select one with the delegated decision owner, and lock a continuity bible.
- Plan a complete no-gap frame EDL and animatic before paid Seedance video generation.
- Use music-responsive 8 to 24 second anchors plus selective 4 to 8 second inserts, not uniform hypercut pacing.
- Generate every Seedance plate with `generateAudio: false`, then mux the original master exactly once.
- Produce a playable MP4 and a technical verification report.

## Install

### From GitHub

```bash
git clone https://github.com/edemaistre/scenario-seedance-2-5-music-video.git ~/.agents/skills/scenario-seedance-2-5-music-video
```

### From the local `.skill` archive

```bash
unzip scenario-seedance-2-5-music-video.skill -d ~/.agents/skills/
```

The packaged release is also published at [v1.0.0 on GitHub](https://github.com/edemaistre/scenario-seedance-2-5-music-video/releases/download/v1.0.0/scenario-seedance-2-5-music-video.skill).

Runtime requirements: Python 3.11 or newer, FFmpeg and FFprobe, an authenticated Scenario MCP, and authorized source media. Refresh the live Scenario schema before production because the dated local contract is a guardrail, not the source of truth.

The optional official skill validator requires PyYAML. Install its development dependency with `python3 -m pip install -r requirements-dev.txt` when validating source releases.

## Use

Invoke `$scenario-seedance-2-5-music-video` with a master audio file and the desired outcome. The skill gathers missing decisions in one intake, then routes to its references, templates, and deterministic scripts.

Key local commands:

```bash
python3 -B scripts/analyze_audio.py "<master>" --output "<new-analysis.json>"
python3 -B scripts/validate_project.py "<manifest.json>"
python3 -B scripts/assemble_music_video.py "<manifest.json>" "<new-output.mp4>" --project-root "<project-root>"
python3 -B scripts/package_skill.py "<new-archive.skill>"
```

The audio analyzer records the source codec, decoded duration, integrated loudness, true peak, loudness range, energy, silence, onset, and tempo candidates without modifying the master.

Delivery verification is exposed as `verify_delivery(...)` in `scripts/verify_delivery.py` so callers can retain the structured report.

## Scenario smoke test

Verified 2026-08-07 in `# Emmanuel / C - MCP Tests`:

- live Seedance 2.5 discovery succeeded;
- live schema retrieval succeeded;
- a 4-second, 480p, 1:1, silent dry run returned an 84 CU estimate;
- no job was created and nothing was spent.

Live workspace IDs are intentionally excluded from this public repository.

## Verification

Run all tests:

```bash
python3 -B -m unittest discover -s tests -v
```

All 113 automated tests pass. The suite covers source codec and EBU R128 analysis, exact Decimal frame math, strict planning and paid-attempt provenance, explicit reference approval, race-free assembly, MP4 container enforcement, audio provenance, portable FFmpeg behavior, binary privacy checks, deterministic packaging, and release contracts.

Five fresh-agent forward tests also passed: a 30-second brand film without references, a 2:37 lyrical artist video, a 3-minute ambient instrumental, foreign-language uncertainty, and tight-budget timeout recovery.

## Repository map

- `SKILL.md`: concise operating workflow and progressive-disclosure routes.
- `references/`: dated model contract, music analysis, shot design, Scenario production, assembly, examples, and source ledger.
- `assets/`: intake, treatment, continuity, and manifest templates.
- `scripts/`: deterministic analysis, strict validation, assembly, delivery verification, and allowlisted packaging.
- `tests/`: unit, integration, privacy, portability, and release contracts.
- `docs/superpowers/`: approved design and implementation plan, excluded from the packaged skill.
- `versions/`: immutable deliverable history.

No master, complete lyric sheet, private reference, live workspace ID, signed URL, or generated media is included.

## License

MIT. Scenario and Seedance names belong to their respective owners.

## Resume

**Resume this work:** `claude --resume 019fdb6d-cde0-7ee3-858d-8f411dc18f50`
