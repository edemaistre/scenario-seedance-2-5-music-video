# Seedance 2.5 Model Contract for Music Videos

## Authority and date

This Scenario contract was verified on 2026-08-07. Refresh it with `model_schema_get` before every production session. The live schema wins over this document, a third-party guide, an example manifest, or a remembered parameter.

Model: `model_bytedance-seedance-2-5`

## Dated Scenario boundary

| Field | Dated contract |
|---|---|
| `prompt` | Optional string, maximum 6,000 characters. Use `@image1`, `@video1`, and `@audio1` to bind ordered references. |
| `image` | First-frame image. It cannot be combined with `referenceImages` or `referenceVideos`. |
| `lastFrameImage` | Last-frame image. It requires `image`. |
| `referenceImages` | Array of Scenario image asset IDs, maximum 30. |
| `referenceVideos` | Array of Scenario video asset IDs, maximum 10. |
| `referenceAudio` | Array of Scenario audio asset IDs, maximum 10. |
| `duration` | Integer 4 through 30, or `-1` for Auto. Default `-1`. |
| `resolution` | `480p` or `720p`. Default `720p`. |
| `aspectRatio` | `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, or `adaptive`. Default `adaptive`. |
| `generateAudio` | Boolean. Set it to `false` for every music-video shot. |
| `outputFormat` | `mp4` or `mov`. Default `mp4`. |

The current wrapper exposes text-to-video, image-to-video, and video-to-video capabilities. It does not expose a deterministic seed, mask, region, 3D reference, or dedicated camera-control field. Describe camera behavior in the prompt.

## Music-video audio rule

The supplied master is the final soundtrack and immutable timeline. `referenceAudio` is model conditioning for rhythm, pacing, performance energy, or section shape. It is not soundtrack passthrough and must never be treated as a bit-preserving audio input.

Keep `generateAudio: false` even when `referenceAudio` is present. Discard every source clip audio stream during assembly, then mux the supplied master once. If a refreshed live schema no longer permits silent output with the required conditioning, stop before spending and report the drift.

## Mode boundaries

| Intent | Inputs | Duration and geometry |
|---|---|---|
| Text | `prompt` | 4 through 30 or Auto. Requested `aspectRatio` controls the canvas. |
| First frame | `image`, usually `prompt` | Inherits source geometry. Do not add reference image or video arrays. |
| First and last frame | `image`, `lastFrameImage`, usually `prompt` | Inherits source geometry. Use only compatible endpoints. |
| Reference | One or more reference arrays, usually `prompt` | 4 through 30 or Auto. Requested ratio applies unless a source-bound operation is inferred. |
| Edit | `referenceVideos`, a bounded preservation prompt, `duration: -1` | Follows input duration and geometry. Make one diagnosed repair. |
| Extend | `referenceVideos`, explicit boundary and continuation prompt | Inherits the source boundary and geometry. Use only for literal continuity. |

Mode is inferred from the request shape and prompt. A local `mode` field can document intent in the project manifest, but it is not a model parameter.

## Reference rules

- Arrays remain arrays with one item.
- Pass Scenario asset IDs, never local paths, public URLs, or temporary signed URLs.
- Array order defines tag order. The first image is `@image1`, the first video is `@video1`, and the first audio file is `@audio1`.
- Give every reference one primary role, the exact attributes to inherit, and explicit exclusions.
- Use the smallest reference set that proves identity, product, world, motion, or rhythm. More references can introduce conflicts.
- A reference audio file can guide timing and energy, but the exact master timeline stays in the edit decision list.

## Required live-schema check

1. Resolve the confirmed Scenario team and project.
2. Use `search` to locate the exact public model.
3. Call `model_schema_get` for `model_bytedance-seedance-2-5` in that workspace.
4. Compare model ID, field names, types, limits, modes, duration, resolution, aspect ratio, output, and silent-audio behavior with the manifest.
5. Update the private run record with the retrieval date and any drift.
6. Stop before a paid call if the intended request is no longer valid. Do not guess a renamed field or silently fall back to another model.

Scenario currently outputs at 480p or 720p. A 1080p or 4K delivery requires a separate finishing or upscale stage with its own live schema check, cost gate, and approval.
