# Cut from a clip list

`premiere_cut` turns a clip list into a finished master in one call: it creates a new project and
sequence, places the clips on V1, adds the transitions, places an optional audio file on A1 and exports
a ProRes 422 HQ `.mov`.

## The request

```json
{
  "project": "/work/cut.prproj",
  "master": "/work/master.mov",
  "audio": "/work/score.wav",
  "clips": [
    {"file": "/work/aisle.mp4", "start": 0, "in_point": 0, "out_point": 3},
    {"file": "/work/circuit.mp4", "start": 3, "in_point": 0.5, "out_point": 3.5,
     "transition": {"kind": "cross_dissolve", "frames": 12}},
    {"file": "/work/cubes.mp4", "start": 6, "in_point": 0.5, "out_point": 3.5,
     "transition": {"kind": "cross_dissolve", "frames": 12}}
  ]
}
```

- `start` is the clip's timeline position; `in_point` and `out_point` are source times. All are
  seconds, snapped to the first clip's frame grid.
- Clips are ordered by `start` and must not overlap; gaps stay empty. Clip files must have distinct
  file names, each file must exist, and `out_point` must be at least one frame after `in_point`.
- The sequence takes its settings from the first clip.
- Clip audio is not used. The optional `audio` file starts at 0 on A1 and plays in full, and the export
  covers the whole sequence, so a score longer than the clips makes a longer master.
- `transition.kind` is `cross_dissolve`, `film_dissolve`, `dip_to_white`, `dip_to_black`, or any name
  that `premiere_transitions` lists. A transition sits at the start of its clip: single-sided on the
  first clip, centered on the cut otherwise. A transition Premiere Pro cannot add is returned in
  `warnings`. A transition needs source handles on both sides to reach its full length.
- An existing project, master or report (`<project>.report.json`) is refused unless `replace` is true,
  which deletes them first.

## The result

```json
{"fps": "24", "frames": 216, "cut_frames": 216,
 "transitions": ["clip 2: Cross Dissolve 12f", "clip 3: Cross Dissolve 12f"], "warnings": []}
```

This is the result of the request above, the same one the [quickstart](../introduction/quickstart.md)
runs. `cut_frames` is the end of the last clip in frames; `frames` is the exported master's, counted by
`ffprobe`. They differ when the audio runs past the last clip; here the score and the clips both end at
9 seconds. `project` and `master` echo the paths.

## After the cut

The project stays on disk and can be opened with `premiere_project`. The edit is then ordinary Premiere
Pro work: [`premiere_inspect`](../reference/tools.md#premiere_inspect) shows the tracks, and any other tool
can change the sequence. Source movies that are rewritten on disk while a project is open keep showing
their old frames until you call `premiere_media_replace` for them.

## Constraints

- `ffprobe` must be installed (it is found on `PATH` or in the usual Homebrew folders): the cut reads the
  first clip's frame rate with it and counts the master's frames.
- Premiere Pro stalls when a project is created at a path where another project is still open, so the
  cut closes every open project without saving before it creates its own.
