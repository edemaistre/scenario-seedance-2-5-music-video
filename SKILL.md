---
name: scenario-seedance-2-5-music-video
description: Use when turning a song into a finished music video with Scenario and Seedance 2.5. Reads the track, pulls the lyrics, builds a story, generates reference frames and then shots, and cuts everything against the untouched master.
---

# Music video with Seedance 2.5

Five steps: song, lyrics, story, frames, video. The supplied master is the soundtrack and is never re-encoded.

## Ask once, then work

In one message: which Scenario team and project, who the track is by and whether it is cleared, aspect ratio and target length, anything that must appear (a performer, a product, a place), anything that must not, and the spend ceiling. Then run without stopping to ask again.

## 1. Read the song

```bash
python3 scripts/song.py master.mp3 -o song.json
```

Returns the SHA-256, duration, loudness, tempo, sections and cut candidates. Sections are your shot boundaries, cut candidates are your cut points. Play the track and check them. A beat grid is a suggestion, not the truth.

Keep the master read only. Every later number is timed against its measured duration.

## 2. Get the lyrics

Supplied lyrics always win. Otherwise transcribe on Scenario:

```
model_scenario-audio-to-text   modelSize: large-v3   vadFilter: true
```

Sung vocals transcribe worse than speech, so treat the output as a draft. Read it against the audio. Only ask the user about a line if getting it wrong would change the story. If the track is instrumental, say so and move on.

## 3. Write the story

One page, no more. What happens, to whom, where, and how it turns across the sections from step 1. Then name the things that must not drift: face, wardrobe, location, object, palette. Name the closing image.

Show it to the user before spending anything. This is the cheapest place to be wrong.

## 4. Generate the frames

Make the reference stills first, one per look you need to hold, with `model_openai-gpt-image-2` at the delivery aspect ratio. Look at them. They set identity, material and palette for everything downstream.

Then choose, per shot, how it is conditioned. This decides more than the prompt does:

- The shot must **open** in a specific state: pass that state as `image`, the first frame.
- The shot must **carry identity and world** but can start anywhere: pass `referenceImages`.

Do not try to set an opening state through prompt wording. It does not work. See `references/seedance.md`.

## 5. Generate and cut

Every shot: `model_bytedance-seedance-2-5`, `generateAudio: false`, always. 4 to 30 seconds, 480p or 720p. Generate one or two seconds longer than the edit needs so you have a handle to trim.

Look at every clip before accepting it. Measure before you judge: a sparse contact sheet makes a continuous camera move look like a hard cut, so compare neighbouring frames numerically before you conclude a shot is broken and pay to reroll it.

Write `edit.json` (see `edit.example.json`):

```json
{
  "master": "master.mp3",
  "fps": 24,
  "width": 1280,
  "height": 720,
  "shots": [
    {"clip": "clips/01.mp4", "at": 0.0},
    {"clip": "clips/02.mp4", "at": 12.5},
    {"clip": "clips/03.mp4", "at": 30.625, "in": 1.0}
  ]
}
```

Each shot runs until the next one starts, and the last runs to the end of the master, so gaps are impossible. `in` is an optional head trim inside that clip.

```bash
python3 scripts/build.py edit.json out.mp4
```

One ffmpeg pass: conform, concatenate, mux the master, verify. It fails loudly if a clip is too short for its slot or the delivered audio is not the master.

## Non-negotiables

- `generateAudio: false` on every Seedance call. The master is muxed once, at the end.
- Never trim, normalise, fade or re-encode the master. `build.py` copies it when MP4 can carry the codec and proves it with a hash of the audio frames.
- Visuals cover the whole track. Enforced.
- Refresh the live model schema before a session. The IDs here were correct on 2026-08-12; the live schema wins.
- Watch the finished video with sound and again muted before calling it done.
