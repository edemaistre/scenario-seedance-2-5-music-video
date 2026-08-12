# Bugs

## Open

### Independently generated shots restart their own evolution

Not a bug in this repo, a property of Seedance 2.5 worth planning around. Each shot begins from the
base state of its reference world, so anything that builds across a shot resets at every cut. On a
build where the sky brightened through each take, the cuts landed as visible resets at the two
loudest bars of the track.

Mitigation today: use first frame mode for any shot whose opening state matters, and order takes so
the closing state of one matches the opening state of the next. See `references/seedance.md`.

### `song.py` section detection is level based only

Sections come from shifts in smoothed RMS. A track that changes arrangement without changing level,
for example a verse into a chorus at the same loudness, will not split there. Onsets and cut
candidates still work. Treat sections as a starting point and listen.

## Fixed in v2.0.0

### The master could be silently truncated

`-frames:v` ends the whole output once the video stream reaches its limit, so any master whose audio
ran past the last video frame lost its tail. A 4.000 second master came back as 3.997 seconds. It did
not show on the 60.029 second reference track because there the video ran 12 ms longer than the
audio, which is why it survived v1. Caught by the new tests. The trim filter in the graph already
fixes the frame count exactly, so the frame limit was removed.

### Bit exactness reported false negatives

Comparing the audio elementary stream of the master against the delivery failed even on a true stream
copy. The mp3 muxer writes an ID3v2 header carrying whatever container metadata it finds, so the same
frames hashed differently from a bare `.mp3` than from inside an `.mp4`. Extraction now passes
`-map_metadata -1 -id3v2_version 0 -write_xing 0`.

### Tempo reported sub-harmonics

Plain autocorrelation of the onset envelope scored half time and third time as highly as the real
pulse. A roughly 112 BPM track reported 55 BPM. The candidates are now weighted by a log normal prior
centred on 120 BPM.

### A master MP4 cannot carry failed the whole build

WAV and other non-copyable codecs failed the bit exactness check and therefore the build. They now
take one documented AAC 320k encode and report `audio_encoded_once`.
