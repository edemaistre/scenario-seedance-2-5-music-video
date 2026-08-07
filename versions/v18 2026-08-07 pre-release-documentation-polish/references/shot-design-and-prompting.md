# Shot Design and Prompting

## Start from the locked timeline

Design the video against exact master-relative frames. The generation length creates coverage, while the edit decision list defines what reaches the final cut. Cover the full measured master with no gaps or unintended overlaps before video spend.

For every planned shot, record:

- shot ID, song section, master start frame, and master end frame
- musical or lyrical function, verified sync events, and intended information density
- requested Seedance duration plus opening and closing edit handles
- shot family, subject, visible action, shot size, camera move, lens or optics, aspect ratio, lighting, palette, realism, texture, film stock or grain when justified
- opening composition, exact closing state, screen direction, motion vector, and transition logic
- identity, wardrobe, product, prop, world, and continuity invariants
- reference array order, roles, inherited attributes, and exclusions
- prompt, model parameters, dry-run estimate, approval, job ID, output ID, acceptance, source trim, and reroll diagnosis

Use the canonical manifest shape in `assets/music-video-manifest.example.json`. Validate it before assembly.

The required `planning` object stores the complete director brief: section, musical or lyrical function, verified master-frame sync events, density, handles, shot craft, opening and closing states, continuity categories, and an exact role map for every ordered generation input.

The required `production` object has exactly `disposition` and `attempts`. Use these dispositions:

- `planned`: no paid job exists yet
- `in_progress`: the original job is running or its output awaits review
- `needs_reroll`: the latest result failed or was rejected
- `timed_out`: the original job must be inspected again by its persisted ID
- `accepted`: one inspected attempt passed

An empty attempts array is the valid pre-spend state. Each attempt records its schema-check date, dry-run estimate, explicit approval, nullable job and output IDs, known cost when available, acceptance state, and nullable reroll diagnosis. A later paid attempt is valid only after a failed or rejected result has one testable reroll diagnosis. If the user rejects a dry-run request before any job exists, preserve that attempt and append a revised pending request without inventing a reroll diagnosis. Never add another attempt after a timeout. Keep the same job ID and inspect that original job again. Add `accepted_source` only when one attempt is accepted, and omit the key entirely until its exact object exists.

## Use a hybrid coverage plan

- Prefer 8 to 24 second anchor sequences for a complete phrase, performance passage, narrative unit, or evolving visual idea.
- Use 4 to 8 second inserts, symbolic details, transition plates, and recovery shots where the edit needs precise control.
- Extract a sub-four-second final edit from a longer accepted clip. Do not pay for one generation per beat.
- Request handles around intended edit points. The visual action must remain usable before and after the exact cut.
- Reserve some neutral or low-complexity recovery coverage for continuity repairs.
- Build a still animatic or labeled placeholder cut for the entire song before paid Seedance generation.

A chapter is a planning and approval unit, not necessarily one generation. Group related shots around a song section, location, performer setup, product setup, or visual rule.

## Evidence from creator prompts

The user's 1,088-prompt sample showed that creators frequently make craft directions explicit. Treat the following as a practical checklist, not a formula or required density:

1. explicit camera move
2. dialogue or spoken lines when applicable
3. shot size
4. aspect ratio
5. lens or optics
6. realism target
7. film stock or grain when it supports the treatment
8. lighting direction
9. duration
10. multi-shot or sequence structure
11. audio or music brief as conditioning only
12. negative constraints tied to diagnosed risks

Do not stuff every field into every prompt. Include only directions that materially control the intended shot. Identity, product geometry, action, and exact transition states come before decorative style language.

## Build a reference map

Give each input one primary role:

| Tag | Valid primary roles | State explicitly |
|---|---|---|
| `@image1` | performer identity, character identity, wardrobe, product geometry, world, palette | subject controlled, attributes inherited, background or style exclusions |
| `@video1` | body motion, choreography, camera path, physical action, boundary source | motion controlled, source identity and audio exclusions, boundary state |
| `@audio1` | pulse, phrase shape, performance energy, transition cue | timing inherited, melody, lyrics, voice, and recording identity not passed through |

Use the smallest high-signal set. Multiple angles of one subject must agree. Never ask a motion reference to donate its cast, location, captions, audio, or styling unless that role is intentional and authorized.

## Match modes to edit needs

- Use reference mode for most identity, product, world, motion, or rhythm-led coverage.
- Use first-frame mode when the opening composition is critical.
- Use first-and-last-frame mode when both endpoints are approved, physically compatible, and needed for an exact transition.
- Use edit mode with `duration: -1` for one bounded repair to a source-master clip, with a complete preservation list.
- Use extension only for literal before-boundary or after-boundary continuity allowed by the refreshed live schema.
- Use text mode only when no identity-critical media is needed.

## Write each prompt as a compact director brief

Use this order:

```text
Goal and section function: [what this coverage contributes to the song and final edit]

Reference roles: [bind each used tag to one role, inherited attributes, and exclusions]

Identity and invariants: [subject mapping, product form, wardrobe, object count, ownership, world, screen direction]

Timed visible beats: [consecutive generation-relative ranges, one main state change and one end state per beat]

Camera and optics: [shot size, one dominant camera behavior per beat, lens or optical behavior]

Look: [aspect ratio intent, environment, lighting direction, palette, realism, texture, stock or grain only if supported]

Music conditioning: [which relative pulse, phrase, accent, silence, or energy change from @audio1 guides visible action]

Dialogue or performance: [exact authorized short line only if visibly spoken, speaker, language, delivery, or state none]

Closing state and handles: [stable composition, pose, object state, camera state, motion vector, clean edit space]

Negative constraints: [only likely failures, including no captions, accidental text, logos, watermarks, extra subjects, or generated audio]
```

Always set `generateAudio: false` in parameters. An audio or music brief tells Seedance how the image should respond. It does not request a soundtrack. Exact lyrics, titles, logos, legal copy, packaging typography, captions, UI, and credits belong in deterministic post-production.

## Time correctly

Master time and generation-relative time are different:

- The EDL might place a clip at master `[01:12.500]`.
- A 12 second generated clip still uses internal prompt ranges from 0 through 12 seconds.
- The accepted source trim maps the useful generated interval back onto the master frames.

Each timed beat needs one visible state change, one dominant camera behavior, and an observable end state. Define the exact closing state for the next cut: pose, gaze, object state, screen direction, velocity, camera position and velocity, lighting, background, and negative space. Vague instructions such as "continue cinematically" are not edit decisions.

## Create music-video energy without a house style

Use section contrast:

- performance versus observation
- wide world versus tactile detail
- motion versus suspension
- literal event versus symbolic echo
- stable identity anchor versus one controlled optical exception
- sparse information versus one justified high-density passage

Transitions should emerge from action, composition, light, material, occlusion, camera motion, or an approved motif. Use a hard cut when it better serves the phrase. A transition is not valuable merely because it morphs.

A frame study of the user-supplied 30.2 second Magnific example found roughly 29 substantive shots within one recurring performer and world. Its reusable structure includes performance, human-world tableau, kinetic insert, symbolic object, and transition-plate families; motivated transitions; phrase-aware cuts; and one selective high-density section. This is structural evidence only.

Do not copy its cast, city, wardrobe, palette, fisheye treatment, monochrome treatment, color accents, or genre. Do not copy any supplied prompt-library example as a treatment. Derive every creative choice from the current track, lyrics, brief, or approved references.

## Diagnose before rerolling

Record one testable failure and change one variable:

| Failure | One-variable correction |
|---|---|
| Identity drift | Remove competing identity references or strengthen one invariant profile. |
| Product shape drift | Move exact geometry and object count before look language. |
| Reference background leaks | Add a background exclusion to the responsible reference. |
| Camera jitters | Replace stacked moves with one dominant move. |
| Beat feels static | Add one visible before-and-after state change. |
| Cut has no usable seam | Rewrite the closing state and add edit handles. |
| Transition feels generic | Tie it to one approved material, action, motif, or phrase event. |
| Edit changes too much | Strengthen one preservation category in the edit prompt. |
| Lip movement fails | Remove visible dialogue, shorten the authorized line, or use non-lip-synced performance coverage. |
| Text is malformed | Remove generated typography and composite approved text in post. |

Validate and dry-run the revised request. A rejected output or wait timeout never authorizes an unpriced replacement call.
