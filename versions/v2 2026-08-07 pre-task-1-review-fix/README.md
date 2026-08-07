# Scenario Seedance 2.5 Music Video

An installable Agent Skill for creating a fully assembled music-video MP4 from an authorized master audio track at least 30 seconds long. It preserves the supplied master as the final soundtrack, plans visuals against exact musical timing, requires cost gates for Scenario generation, and verifies final delivery.

## Why this exists

Created from Emmanuel de Maistre's 2026-08-07 request for a reusable Scenario workflow that turns long-form music into coherent multi-shot videos without replacing or altering the master audio.

## Repository map

- `SKILL.md`: concise operating workflow and progressive-disclosure routes.
- `agents/openai.yaml`: agent discovery metadata and starter prompt.
- `references/`, `assets/`, `scripts/`: packaged operational material, implemented in later tasks.
- `tests/`: deterministic contract and script tests.
- `docs/superpowers/`: approved design and implementation plan, excluded from the packaged skill.
- `versions/`: immutable deliverable history. Add a version before overwriting a deliverable.

## Status

Task 1 establishes the core static contract and repository hygiene. Deterministic media tools, production references, templates, forward tests, packaging, installation, and publication remain planned work.

## Verification

Run the static contract test:

```bash
python3 -B -m unittest tests.test_skill_contract -v
```

## Resume

The coordinating session must append its Codex resume identifier when the full skill is complete.
