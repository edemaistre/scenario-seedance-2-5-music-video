# Scenario Seedance 2.5 Music Video

An Agent Skill that turns a song into a finished music video using Scenario and Seedance 2.5.

Song, lyrics, story, frames, video. Two scripts and one page of instructions. The master audio you
supply is the soundtrack of the delivered file, copied rather than re-encoded, and proved so with a
hash of the audio frames.

Public repository: https://github.com/edemaistre/scenario-seedance-2-5-music-video

## Install

```bash
git clone https://github.com/edemaistre/scenario-seedance-2-5-music-video.git ~/.agents/skills/scenario-seedance-2-5-music-video
```

Requirements: Python 3.11 or newer, FFmpeg and FFprobe on PATH, numpy, and an authenticated Scenario
MCP.

```bash
python3 -m pip install -r requirements.txt
```

## Use

Invoke `$scenario-seedance-2-5-music-video` with a track and what you want. The skill asks for what
it is missing in one round, then runs. `SKILL.md` is the whole workflow.

### Read the song

```bash
python3 scripts/song.py master.mp3 -o song.json
```

SHA-256, duration, loudness, tempo, sections and cut candidates. The sections are shot boundaries and
the cut candidates are cut points. On a real 60 second track the cut candidates landed within a
quarter of a second of boundaries that had been chosen by hand.

### Cut the video

```bash
python3 scripts/build.py edit.json out.mp4
```

`edit.json` lists the master and, for each shot, a clip and the time it starts. Each shot runs until
the next begins and the last runs to the end of the master, so the timeline cannot have gaps. See
`edit.example.json`.

One ffmpeg pass conforms every clip, concatenates, muxes the master and verifies:

- exactly one video and one audio stream
- exact frame count, geometry and frame rate
- the delivered audio frames hash identically to the master's
- the master file itself is unchanged
- visuals cover the whole track, never less

It exits non-zero and names the failing check if any of that is untrue.

## What is in here

- `SKILL.md`, the five step workflow.
- `references/seedance.md`, the measured model contract, costs, and the conditioning rule that
  decides whether a shot can open in the state you want.
- `scripts/song.py`, read the master.
- `scripts/build.py`, cut and verify.
- `edit.example.json`, the edit format.
- `versions/`, previous releases kept intact.

No master, lyric sheet, workspace ID, signed URL or generated media is committed.

## Verification

```bash
python3 -B -m unittest discover -s tests -v
```

26 tests covering timeline coverage and frame maths, head trims, undersized clips, geometry
conforming, the stream copy path, the single encode fallback, and that the master is never modified.
They caught a real truncation bug during development: `-frames:v` ends the whole output when the
video limit is reached, silently shortening the master whenever the audio runs past the last video
frame.

Last full run: 26 passed, 2026-08-12.

## License

MIT. Scenario and Seedance names belong to their respective owners.

## Resume

**Resume this work:** `claude --resume 019fdb6d-cde0-7ee3-858d-8f411dc18f50`

**Resume this work:** `claude --resume df795281-d63f-47f4-846e-e09ff5cd9556`
