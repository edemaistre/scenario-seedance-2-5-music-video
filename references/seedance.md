# Seedance 2.5 in practice

Everything here was measured against the live model on 2026-08-12 during a full 60 second build.
The live schema always wins over this page.

## The contract

`model_bytedance-seedance-2-5`

| Parameter | Notes |
|---|---|
| `prompt` | up to 10000 characters |
| `image` | first frame. Mutually exclusive with `referenceImages`. Aspect ratio is ignored and follows this frame |
| `lastFrameImage` | only valid alongside `image` |
| `referenceImages` | up to 30. Array even for one. Mutually exclusive with `image` |
| `referenceVideos` | up to 10. Drives editing and extension. Affects cost |
| `referenceAudio` | up to 10. Timing and energy conditioning only, never passthrough |
| `duration` | 4 to 30 seconds, or -1 for auto. Affects cost |
| `resolution` | `480p` or `720p`. 720p is the maximum. Affects cost |
| `aspectRatio` | ignored in first/last frame, editing and extension modes |
| `generateAudio` | defaults to **true**. Set it to `false` on every music video call |
| `outputFormat` | `mp4` or `mov` |

Output is exactly `duration * fps + 1` frames at 24 fps. A 19 second request returns 457 frames.

## Cost

720p 16:9 measured at about 46.3 CU per second, linear in duration and unaffected by the number of
reference images or audio tracks.

| Duration | CU |
|---|---|
| 6s | 278 |
| 8s | 370 |
| 9s | 418 |
| 10s | 464 |
| 13s | 602 |
| 19s | 880 |

A minute of finished 720p coverage is roughly 3000 CU before any reroll. Dry run before a batch:
`dry_run: true` returns the estimate and creates no job.

## The one thing that will cost you money if you miss it

**In reference-to-video mode, frame one is anchored to the base state of the reference world, and no
prompt wording overrides it.**

On a build where the sky had to already carry an aurora at the loudest bar, four separate attempts
failed, each an independent paid render:

1. Plain description of the target state. Opened on a clear sky and bloomed over three seconds.
2. An explicit single take and opening state lock at the top of the prompt. No change.
3. Reordering `referenceImages` so the aurora plate was `@image1`. No change.
4. Framing the motion as a decay from full, which is what worked by accident on another shot. No change.

Switching to first frame mode fixed it on the first try. The measured sky signal at frame one went
from +31 to +84 and held for the whole take.

So: **if the opening state matters, pass it as `image`. If only identity and world matter, use
`referenceImages`.** Deciding this per shot before you generate is worth more than any prompt tuning.

The side effect of the reference-mode behaviour is that independently generated shots each restart
their own evolution. Cutting them together resets whatever was building, which reads as a continuity
error at exactly the moments the music is loudest. Plan for it.

## Prompt shape that held up

Order matters less than presence. Every shot that worked had all of these:

1. What each reference is for, by tag: `@image1 defines the world and the slab. @audio1 is timing only.`
2. Section function and visual goal in one line: `the pulse enters. Visual goal: arrival.`
3. One dominant camera move and one dominant action. Two of either produces a mess.
4. The closing state, explicitly.
5. An exclusion list. `No people, no text, no captions, no logos, no watermarks. Silent footage.`

Keep one shot to one idea. Long prompts describing a sequence make the model cut inside the clip.

## Reading results

Do not judge a clip from a sparse contact sheet. Tiling every 40th frame makes a continuous camera
move look like a hard cut, and it cost real money to learn that. Compare neighbouring frames
numerically first. Downscale to about 160x90, take the mean absolute difference between consecutive
frames, and only call it a cut when the value spikes far above the clip's own baseline. In the build
above the largest genuine frame-to-frame difference across nine accepted clips was 7 of 255, meaning
there were no hard cuts anywhere, contrary to what the sheets suggested.

The same trick tracks any colour-carried state. Mean of green minus red over the upper half of frame
gave a usable aurora index and turned an argument about whether shots matched into a number.

## Other models used in this workflow

| Purpose | Model | Notes |
|---|---|---|
| Lyrics | `model_scenario-audio-to-text` | Whisper. `modelSize: large-v3`, `vadFilter: true` |
| Reference stills | `model_openai-gpt-image-2` | 46 CU at 1536x864 high quality |
| Music, when generating a track | `model_elevenlabs-music-v2` | 30 CU for 60s, `forceInstrumental` available |

## Gotchas

- `asset_download` only accepts image target formats. For video and audio, read the signed URL from
  `asset_get` and fetch it with `curl -L`.
- Reference audio must be uploaded with the multipart flow above about 100KB. PUT the part to the
  presigned URL with no extra `x-amz-checksum` headers, then call `upload_asset_complete`.
- The auto caption on a returned asset describes what the model thinks it made. It is often wrong
  about the sky and is not a substitute for looking.
