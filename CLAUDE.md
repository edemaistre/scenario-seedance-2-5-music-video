# Project Instructions

Read `README.md` first, then `SKILL.md`.

This repository builds an installable skill, not a music video. Keep it small. The v1 skill failed
because it grew a manifest contract larger than the work it described, and the whole point of v2 is
that it stays out of the way.

## Rules

- Never use em dash or en dash characters in repository prose.
- The supplied master is the soundtrack. Never trim, normalise, fade or re-encode it. If you touch
  the audio path in `build.py`, the bit exactness test must still pass.
- Run `python3 -B -m unittest discover -s tests -v` before every push. Never push red.
- Version before overwrite. Copy the current state into `versions/vN YYYY-MM-DD label/` first.
- No master, lyric sheet, workspace ID, signed URL or generated media in the repository.
- The live Scenario schema always wins over `references/seedance.md`. That page is dated evidence,
  not a contract.

## Before adding anything

Ask what defect it catches that the current tests do not. v1 had 113 tests and 2900 lines of Python
and none of it caught the one thing that was actually wrong with the picture. If the answer is
"nothing yet", leave it out.

Current state: v2.0.0 released. Two scripts, 26 tests, one reference page.

## Resume

**Resume this work:** `claude --resume 019fdb6d-cde0-7ee3-858d-8f411dc18f50`

**Resume this work:** `claude --resume df795281-d63f-47f4-846e-e09ff5cd9556`
