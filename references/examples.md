# Structural Examples

## Contents

- [Anti-anchoring rules](#anti-anchoring-rules)
- [Performance-led chapter](#1-performance-led-chapter)
- [Lyric-metaphor chapter](#2-lyric-metaphor-chapter)
- [Instrumental abstract chapter](#3-instrumental-abstract-chapter)
- [Brand or product cover chapter](#4-brand-or-product-cover-chapter)

## Anti-anchoring rules

These examples are scaffolds, not defaults. They demonstrate how to connect analysis, references, coverage, prompt structure, and edit states without prescribing a genre or visual identity.

- Replace every bracketed field from the current track, lyrics, brief, or approved references.
- If a choice cannot be traced to current evidence, omit it or ask for it.
- Do not copy any example's shot count, pacing, identity, location, wardrobe, palette, lighting, lens, transition, or narrative.
- Do not assume the presence of a performer, lyrics, product, chorus, conventional beat, or fast cut.
- Do not paste a copyrighted lyric, artist likeness, brand, user prompt, or private asset into a reusable example.
- Keep `generateAudio: false`. The supplied master is the final soundtrack.
- Treat the examples as four ways to organize one chapter. A full video may use one, combine justified parts, or use none.

## 1. Performance-led chapter

Use only when an approved performer or character and the music support visible performance.

**Analysis trace:** `[section]` contains `[vocal, instrumental, rhythmic, or emotional function]`. The visible performance should change at `[verified cue]` because `[track-specific reason]`.

**Reference map:** `@image1` controls `[performer identity and approved wardrobe]`; `@video1` controls `[gesture or choreography only]`; `@audio1` controls `[phrase and energy only]`. Exclude each reference's background, captions, sound, and unassigned style.

**Coverage plan:** one `[8 to 24]` second performance anchor, plus one `[4 to 8]` second environmental or tactile insert only if the EDL needs contrast or recovery. Keep screen direction and performance intensity continuous.

**Prompt scaffold:**

```text
Goal and section function: Hold the approved performer as the identity anchor while the image responds to [musical function].
References: @image1 defines [identity attributes] only. @video1 defines [motion] only. @audio1 defines [relative phrase shape] only.
Invariants: [identity, wardrobe, prop, world, object count, screen direction].
0 to [time]: [one visible performance change], [shot size], [one camera move], ending on [observable state].
[time] to [time]: [second track-supported change], ending on [exact handoff].
Look: [track-supported light, palette, optics, realism, texture].
Closing state: [pose, gaze, motion vector, camera state, clean handles].
Constraints: no captions, logos, watermark, extra performer, identity drift, or generated audio.
```

**Parameters:** `duration: [4 through 30 or justified Auto]`, `resolution: [480p or 720p]`, `aspectRatio: [delivery ratio]`, `generateAudio: false`, `outputFormat: mp4`.

## 2. Lyric-metaphor chapter

Use only when authorized lyrics contain a clear image, conflict, or emotional turn. Translate meaning, not protected wording. If transcription is uncertain, keep the metaphor broad enough to remain valid.

**Analysis trace:** the supplied lyric theme at `[master time]` changes from `[state A]` to `[state B]`. The visual metaphor expresses that turn through `[approved object, space, material, or action]`.

**Reference map:** an approved reference controls `[subject or world]`; optional `@audio1` controls the relative phrase transition only. No performer is implied.

**Coverage plan:** one evolving `[8 to 24]` second anchor with a legible before and after state. Add a `[4 to 8]` second symbolic insert only if it creates a useful rhyme elsewhere in the full video.

**Prompt scaffold:**

```text
Goal and section function: Express the approved theme [theme summary] without on-screen lyrics or literal illustration.
Reference roles: [tag] defines [one role] and excludes [unassigned attributes]. @audio1 defines [relative cue] only.
Invariants: [subject count, material law, world, continuity motif].
0 to [time]: [metaphorical state A], [shot size], [camera behavior], ending on [state].
[time] to [time]: At the relative [phrase event], [one motivated transformation] produces state B; end with [exact closing composition].
Look: [analysis-supported visual law].
Constraints: no lyric text, invented character, unapproved symbol, logo, watermark, or generated audio.
```

**Parameters:** `generateAudio: false`; reference-audio timing is conditioning only; the EDL holds the exact master cue.

## 3. Instrumental abstract chapter

Use when the track is instrumental or when language uncertainty makes nonliteral structure safer. Abstract does not mean arbitrary. Every change still maps to rhythm, texture, dynamics, timbre, spatial movement, or silence.

**Analysis trace:** `[section]` moves from `[density, texture, register, or tension A]` to `[state B]`, with a verified event at `[master time]`.

**Reference map:** an approved style or material reference controls `[specific visual law]`; `@audio1` controls `[pulse, phrase, or energy]` only. Exclude subject identity, existing composition, captions, and recording identity.

**Coverage plan:** one `[12 to 24]` second evolution with few comprehensible states. A slow piece may remain in one shot. A dense passage may earn short kinetic inserts, but do not turn pulse into uniform hypercut speed.

**Prompt scaffold:**

```text
Goal and section function: Make [musical property] visible through [approved visual system].
References: [tag] defines [material or spatial rule] only. @audio1 defines [relative energy contour] only.
Invariants: [element count, geometry law, color law, world rule].
0 to [time]: [state A evolves], [camera behavior], ending on [legible configuration].
[time] to [time]: At [relative musical event], [single transformation] moves toward state B; end on [stable handoff].
Look: [track-supported texture, light, optics, realism].
Constraints: no performer, narrative stereotype, typography, logo, watermark, or generated audio.
```

**Parameters:** `generateAudio: false`; use a longer hold when that is the strongest response to the music.

## 4. Brand or product cover chapter

Use when an authorized product, release object, package, mascot, or distinctive brand asset must participate in the music video. The product should perform a story or rhythm function, not interrupt the video as an unrelated advertisement.

**Analysis trace:** `[hook, refrain, drop, or resolution]` supports a product action because `[brief and track-specific reason]`. Any functional claim comes from approved copy, never from inference.

**Reference map:** `@image1` controls exact product silhouette, material, and approved color; another approved image may control the world. Exclude source labels, background, reflections, text, and lighting unless explicitly assigned. Add exact logo artwork later in post.

**Coverage plan:** one `[8 to 20]` second active product anchor and, if needed, one `[4 to 8]` second tactile detail. End with a stable composition and placement-safe negative space.

**Prompt scaffold:**

```text
Goal and section function: Integrate the approved product into [musical or story function] and finish on an editable release image.
References: @image1 defines one product's [geometry and material] only; exclude its background, text, and lighting. [Other tag] defines [one role].
Invariants: exactly [count], unchanged silhouette, controls, proportions, ownership, and approved behavior.
0 to [time]: [product action tied to section], [shot size], [one camera move], ending on [proof state].
[time] to [time]: [track-supported escalation or settle], ending on [stable closing state and clean copy space].
Look: [treatment-supported light, palette, lens, realism, texture].
Constraints: no invented feature, malformed label, generated logo, price, claim, caption, watermark, or generated audio.
```

**Parameters:** `generateAudio: false`; composite exact logo, title, claim, legal copy, and CTA from approved source artwork after the video plate is accepted.
