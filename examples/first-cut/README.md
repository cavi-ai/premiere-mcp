# First cut

Three generated shots and a score, cut into a new Premiere Pro project with 12-frame cross dissolves and
exported as a ProRes 422 HQ master. The stills were exported by Premiere Pro from that project at 1.5, 3,
4.5 and 7.5 seconds: the server aisle, the aisle dissolving into the circuit board, the circuit board,
and the glass cubes.

![Four stills from the cut: a server aisle, the aisle dissolving into a circuit board, the circuit board, and a row of lit glass cubes](cut-frames.png)

## The inputs

[media](media) holds the three shots and the score, ready to cut:

| File | What it is |
|---|---|
| `aisle.mp4` | A forward dolly down a server aisle, 3.75 s, 1280 by 720 at 24 fps |
| `circuit.mp4` | A pull back over a lit circuit board, 3.75 s, 1280 by 720 at 24 fps |
| `cubes.mp4` | A lateral track past a row of lit glass cubes, 3.75 s, 1280 by 720 at 24 fps |
| `score.wav` | 9 seconds of score at 120 BPM, 48 kHz, ending in a one-second fade |

The shots were generated with Wan 2.1 text-to-video and the score was composed in Ableton Live. They are
part of this repository and covered by its [MIT license](../../LICENSE).

## Reproduce it

You need the server [installed and registered](../../docs/premiere-mcp/source/pages/introduction/installation.md)
and the [Bridge relay approved](../../docs/premiere-mcp/source/pages/guides/bridge-setup.md). From a
checkout, run the example against Premiere Pro, with a folder for the project, master and stills:

```sh
uv run --locked python examples/first-cut/run.py ~/Desktop/first-cut
```

[run.py](run.py) starts the server over stdio and calls `premiere_cut` with [cut.json](cut.json), then
`premiere_project` to open the project, `premiere_inspect`, `premiere_frame_export` and
`premiere_project` to close it. To do the same from your agent, ask it to make those calls with the media
paths made absolute.

## What it returned

[results.json](results.json) holds the measured results: the `premiere_cut` answer, the master as
`ffprobe` reads it (ProRes `apch`, 1280 by 720, 24 fps, 216 frames), the sequence as `premiere_inspect`
reports it, and the still sizes. Paths in the file are shortened to `/work`.

- The sequence takes 24 fps and 1280 by 720 from the first clip.
- The master has 216 frames: 9 seconds of clips and 9 seconds of score.
- Each dissolve is centered on its cut: 2.75 to 3.25 seconds and 5.75 to 6.25 seconds. The 0.5 second
  in points of the second and third clips leave the source handles the dissolves need.
