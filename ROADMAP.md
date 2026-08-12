# Roadmap

## Next

- **Lyric timings into the edit.** `model_scenario-audio-to-text` returns segments. Feeding those
  into `song.py` output would put vocal entries next to the cut candidates, which is what you
  actually cut a sung track on. The current release has the lyrics step but does not yet align it to
  the timeline.
- **State matching across cuts.** A small check that compares the closing frames of one shot with the
  opening frames of the next and warns when they diverge, so the reset described in `BUGS.md` is
  caught before the build rather than after watching it.
- **A worked end to end example.** The reference build used an instrumental. A sung track with real
  lyrics, start to finish, would exercise steps 2 and 3 properly.

## Considered and rejected

- **A manifest schema.** v1 had one. It cost more than it caught. `build.py` validates the only
  things that can actually be wrong: coverage, frame maths, clip length, and audio integrity.
- **Spend gates with per stage approval.** Ceremony when the operator has already approved the run.
  `dry_run: true` on the model call is the real control and it is one flag.
- **Packaging into a `.skill` archive.** Cloning the repository is enough.

## Not planned

- Adding titles, credits or subtitles. Do that in post with the tool of your choice.
- Colour grading inside `build.py`. It conforms geometry and frame rate and nothing else, on purpose.
