# Scenario Seedance 2.5 Music Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, test, install, package, and publicly publish a separate skill that turns a 30 second or longer authorized music master into a fully assembled Seedance 2.5 music video through Scenario MCP.

**Architecture:** Keep the supplied master audio immutable, analyze it before visual planning, generate coherent silent Seedance plates in cost-gated chapter batches, then assemble the accepted plates against exact master timecodes. Use dependency-free Python wrappers around FFprobe and FFmpeg for deterministic probing, validation, assembly, and delivery verification.

**Tech Stack:** Agent Skills Markdown, Python 3.11 or newer standard library, FFmpeg and FFprobe, Scenario MCP, JSON, unittest, GitHub Actions.

## Global Constraints

- Use the separate skill name `scenario-seedance-2-5-music-video`.
- Accept master audio whose measured duration is at least 30 seconds. Do not impose an artificial maximum.
- Use `model_bytedance-seedance-2-5`, but refresh the live Scenario schema before production.
- Set `generateAudio` to `false` for every Seedance request.
- Treat `referenceAudio` as conditioning only, never passthrough.
- Preserve the supplied master timeline and mix. Never normalize, stretch, remix, trim, fade, or replace it.
- Ask for reference images, visual style, character, performer, product, and world. Create a reference pack in Scenario if none exists.
- Keep examples genre-neutral and structurally illustrative.
- Never store credentials, signed URLs, private IDs, copyrighted masters, full lyrics, or user reference assets in the repository.
- Use one final commit and one push after all tests pass, following the user's standing rule.
- Do not use em dash or en dash characters in repository prose.

---

### Task 1: Define static skill contract and repository hygiene

**Files:**

- Create: `tests/test_skill_contract.py`
- Create: `README.md`
- Create: `CLAUDE.md`
- Create: `CHANGELOG.md`
- Create: `BUGS.md`
- Create: `ROADMAP.md`
- Create: `versions/README.md`
- Create: `.gitignore`
- Create: `.github/workflows/tests.yml`
- Modify: `SKILL.md`
- Verify: `agents/openai.yaml`

**Interfaces:**

- Consumes: approved design specification.
- Produces: a discoverable skill whose required workflow and supporting-file routes can be asserted by static tests.

- [ ] **Step 1: Write failing static tests**

Create tests that parse YAML frontmatter and assert:

```python
assert metadata["name"] == "scenario-seedance-2-5-music-video"
assert metadata["description"].startswith("Use when")
assert "30" in skill_text
assert "generateAudio: false" in skill_text
assert "fully assembled" in skill_text.lower()
assert "reference" in skill_text.lower()
```

Also assert every routed file exists, the repository contains no private Scenario IDs or signed URLs, and text files contain neither `\u2013` nor `\u2014`.

- [ ] **Step 2: Run the static tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_skill_contract -v
```

Expected: failures because the initialized template does not contain the contract and routed files do not exist.

- [ ] **Step 3: Write the core skill and repository docs**

Keep `SKILL.md` below 500 lines. Route detailed knowledge to references. Include one consolidated intake, the immutable-master rule, the music-intelligence phase, missing-reference creation, treatment approval, complete EDL, proof-shot gate, chapter generation, assembly, and QA.

- [ ] **Step 4: Run the static tests and verify GREEN**

Run the same unittest command. Expected: all static contract tests pass.

### Task 2: Build the deterministic audio analyzer

**Files:**

- Create: `tests/test_analyze_audio.py`
- Create: `scripts/__init__.py`
- Create: `scripts/analyze_audio.py`

**Interfaces:**

- Consumes: local master-audio path, optional lyrics path, optional output JSON path.
- Produces: `analyze_audio(path: Path, lyrics_path: Path | None = None) -> dict[str, object]` and a CLI that prints or writes strict JSON.

- [ ] **Step 1: Write failing analyzer tests**

Generate synthetic WAV fixtures during tests with Python's `wave` module. Assert that the analyzer returns:

```python
{
    "schema_version": 1,
    "master": {
        "path": "...",
        "sha256": "...",
        "duration_seconds": 30.0,
        "sample_rate": 44100,
        "channels": 2,
    },
    "analysis": {
        "energy_windows": [...],
        "silence_regions": [...],
        "onset_candidates": [...],
        "tempo_candidates_bpm": [...],
        "tempo_confidence": "low|medium|high",
    },
    "lyrics": {"provided": false}
}
```

Test missing files, files below 30 seconds, non-audio inputs, lyrics hashing without lyric-body leakage, strict JSON, and paths containing spaces.

- [ ] **Step 2: Run analyzer tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_analyze_audio -v
```

Expected: import failure because `scripts.analyze_audio` does not exist.

- [ ] **Step 3: Implement minimal analyzer**

Use `ffprobe -of json` for stream facts. Use `ffmpeg` to decode mono PCM for fixed-window RMS, silence candidates, onset-envelope peaks, and tempo autocorrelation. Label tempo as a candidate and emit confidence. Hash the original master and optional lyrics file with SHA-256. Never emit lyric contents.

- [ ] **Step 4: Run analyzer tests and verify GREEN**

Run the analyzer tests, then run the full suite. Expected: all pass with no warnings or tracebacks.

### Task 3: Validate the long-form project manifest

**Files:**

- Create: `tests/fixtures/valid_30s_project.json`
- Create: `tests/fixtures/valid_157s_project.json`
- Create: `tests/fixtures/invalid_gap_project.json`
- Create: `tests/test_validate_project.py`
- Create: `scripts/validate_project.py`
- Create: `assets/music-video-manifest.example.json`

**Interfaces:**

- Consumes: strict JSON manifest.
- Produces: `validate_manifest(data: dict[str, object]) -> list[Diagnostic]` and CLI exit codes `0` valid or warnings only, `1` contract errors, `2` unreadable or invalid JSON.

- [ ] **Step 1: Write failing validator tests**

Assert acceptance of 30, 60, 157, and 360 second manifests. Assert rejection of:

- measured master duration below 30 seconds
- wrong model ID
- any shot with `generateAudio` not exactly `false`
- Seedance duration outside 4 to 30 seconds, except documented Auto operations
- duplicate shot IDs
- timeline gaps or unintended overlaps
- invalid source trim ranges
- incomplete final coverage
- inconsistent aspect ratio, frame rate, resolution, or geometry
- missing supplied or approved generated reference pack
- invented lyrics marked as certain
- duplicate JSON keys, nonfinite numbers, control-character diagnostic injection, and non-object JSON

- [ ] **Step 2: Run validator tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_validate_project -v
```

Expected: import failure because the validator does not exist.

- [ ] **Step 3: Implement strict validator**

Use a duplicate-key rejecting JSON loader. Represent diagnostics with a frozen dataclass. Sort diagnostics deterministically. Compare time coverage with `Decimal` at millisecond precision. Validate all Scenario arrays, tags, modes, and exact parameter names against the dated Seedance contract.

- [ ] **Step 4: Run validator tests and verify GREEN**

Run validator tests and then the full suite. Expected: all pass.

### Task 4: Assemble visuals and mux the supplied master

**Files:**

- Create: `tests/test_assemble_music_video.py`
- Create: `scripts/assemble_music_video.py`

**Interfaces:**

- Consumes: validated manifest, accepted local clips, local master audio, output MP4 path.
- Produces: `build_ffmpeg_command(manifest: dict[str, object], output_path: Path) -> list[str]`, `assemble(...) -> dict[str, object]`, and a CLI.

- [ ] **Step 1: Write failing assembly tests**

Use FFmpeg lavfi to create synthetic colored clips with distinct generated audio and a separate master tone. Assert:

- source clips appear in declared order and use declared trims
- output is constant geometry and frame rate
- generated clip audio is absent
- master audio begins at zero and covers the final MP4
- output duration differs from the master by no more than one frame plus 20 ms
- AAC, MP3, or ALAC input uses stream copy when supported by MP4
- WAV or FLAC uses one explicit AAC 320 kbps delivery encode
- missing clips, invalid coverage, absent FFmpeg, and paths with spaces fail cleanly

- [ ] **Step 2: Run assembly tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_assemble_music_video -v
```

Expected: import failure because the assembler does not exist.

- [ ] **Step 3: Implement assembly**

Construct an argument list, never a shell string. For each shot, trim video, reset timestamps, scale and pad, set frame rate, and concatenate video only. Pad the last frame only when needed, then trim to the measured master duration. Map `0:v:0` from the conformed visual intermediate and `master:a:0` explicitly. Never use `-shortest` before validating visual duration.

- [ ] **Step 4: Run assembly tests and verify GREEN**

Run assembly tests and then the full suite. Expected: all pass.

### Task 5: Verify final delivery

**Files:**

- Create: `tests/test_verify_delivery.py`
- Create: `scripts/verify_delivery.py`

**Interfaces:**

- Consumes: final MP4, original master, manifest.
- Produces: `verify_delivery(final_path: Path, master_path: Path, manifest: dict[str, object]) -> dict[str, object]` with `passed`, checks, warnings, and technical metadata.

- [ ] **Step 1: Write failing delivery tests**

Assert detection of wrong duration, missing video, missing audio, multiple audio tracks, channel mismatch, wrong frame rate or geometry, and an accidental generated-audio track. Assert compressed-packet hash equality for copied audio and a clearly labeled non-bit-exact result for AAC transcode.

- [ ] **Step 2: Run delivery tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_verify_delivery -v
```

Expected: import failure because the verifier does not exist.

- [ ] **Step 3: Implement delivery verification**

Probe both files with FFprobe. Compare duration within one frame plus 20 ms. Require one video stream and one audio stream. Compare channels and timeline start. For stream-copy mode, compare FFmpeg elementary-stream SHA-256 hashes. For transcode mode, report that the master content and timing are preserved but compressed bytes are not bit-identical.

- [ ] **Step 4: Run delivery tests and verify GREEN**

Run verifier tests and then the full suite. Expected: all pass.

### Task 6: Author production references, templates, and examples

**Files:**

- Create: `references/model-contract.md`
- Create: `references/music-analysis-and-treatment.md`
- Create: `references/shot-design-and-prompting.md`
- Create: `references/scenario-production.md`
- Create: `references/assembly-and-qa.md`
- Create: `references/examples.md`
- Create: `references/source-ledger.md`
- Create: `assets/intake-template.md`
- Create: `assets/treatment-template.md`
- Create: `assets/continuity-bible-template.md`
- Extend: `tests/test_skill_contract.py`

**Interfaces:**

- Consumes: official research, live Scenario model contract, Magnific frame analysis, and generalized prompt-library findings.
- Produces: progressive-disclosure guidance that another agent can execute without copying a fixed genre or treatment.

- [ ] **Step 1: Add failing content-contract tests**

Assert that the references cover lyrics, rhythm, structure, timbre, energy, tone, story, uncertainty, instrumental tracks, user references, reference creation, rights, moderation, strobing, one proof shot, chapter batching, exact master muxing, and no example-style leakage.

- [ ] **Step 2: Run static tests and verify RED**

Expected: missing-reference failures.

- [ ] **Step 3: Write references and templates**

Include four compact structural examples only:

1. performance-led chapter
2. lyric-metaphor chapter
3. instrumental abstract chapter
4. brand or product cover chapter

Place anti-anchoring rules before the examples. Use bracketed placeholders and require every creative choice to trace back to the track, lyrics, brief, or approved references.

- [ ] **Step 4: Run static tests and verify GREEN**

Run the full unittest suite. Expected: all pass.

### Task 7: Forward-test and close skill loopholes

**Files:**

- Modify only files whose behavior fails a forward test.
- Record findings in `BUGS.md`, `CHANGELOG.md`, and `ROADMAP.md`.

**Interfaces:**

- Consumes: complete candidate skill.
- Produces: behavior evidence from fresh agents using only the installed skill artifact and realistic briefs.

- [ ] **Step 1: Run five forward tests**

Test:

- 30 second energetic brand cover with no visual references
- 2 minute 37 second lyrical artist video with character references
- 3 minute instrumental ambient track with only a style reference
- foreign-language vocal track with uncertain transcription
- timed-out Scenario job under cost pressure

- [ ] **Step 2: Review full outputs**

Confirm agents do not invent lyrics, inherit the Magnific treatment, force fast cuts onto slow music, generate audio, skip reference creation, batch unapproved spend, duplicate timed-out jobs, or stop before final assembly.

- [ ] **Step 3: Add one failing regression test per real defect**

Run each new test and verify it fails for the observed reason before changing production files.

- [ ] **Step 4: Apply minimal fixes and verify GREEN**

Run the affected test, then the complete suite.

### Task 8: Validate, smoke-test, package, install, and publish

**Files:**

- Create: sibling archive `/Users/emmanuel/Developer/skills/scenario-seedance-2-5-music-video.skill`
- Install: `/Users/emmanuel/.agents/skills/scenario-seedance-2-5-music-video/`
- Create: public GitHub repository `edemaistre/scenario-seedance-2-5-music-video`

**Interfaces:**

- Consumes: fully tested repository.
- Produces: local source, installed skill, installable archive, one public GitHub commit, and a no-spend Scenario smoke-test record.

- [ ] **Step 1: Run every local validation**

```bash
python3 -B -m unittest discover -s tests -v
python3 /Users/emmanuel/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

Expected: all tests and skill validation pass.

- [ ] **Step 2: Run no-spend Scenario MCP smoke test**

Use team `# Emmanuel`, project `C - MCP Tests`. Confirm the exact Seedance 2.5 model and live schema. Exercise only workspace resolution, public-model search, schema retrieval, and a dry run if it is guaranteed not to charge. Do not run a paid generation.

- [ ] **Step 3: Build and inspect the archive**

Package only `SKILL.md`, `agents`, `assets`, `references`, and `scripts`. Inspect the archive for private IDs, signed URLs, caches, test outputs, source masters, and full lyrics.

- [ ] **Step 4: Install and validate from the installed copy**

Copy the packaged operational files into the auto-discovery path without overwriting an unversioned existing skill. Run quick validation against the installed copy.

- [ ] **Step 5: Initialize Git and run tests immediately before push**

```bash
git init
git add .
git commit -m "feat: add Seedance 2.5 music video skill"
```

Create the public repository and push once only after the complete test suite passes.

- [ ] **Step 6: Verify public repository and handoff**

Confirm repository visibility is public, default branch is `main`, remote HEAD matches the local commit, archive exists, installed copy validates, and the smoke test made no paid call.
