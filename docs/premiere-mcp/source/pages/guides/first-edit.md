# Make a first edit

This guide builds a short edit clip by clip: a new project, two clips, a dissolve, a Motion change
and an export. It uses the two clips from the [quickstart](../introduction/quickstart.md). The results
below are from a real run; folder paths are shortened to `/work`, and `warnings` and `errors` lists
that were empty are left out.

## 1. Create the project

`premiere_project` with `action` `new`. `close_others` closes every other open project without saving,
so the new one is the only one Premiere Pro has open.

```json
{"action": "new", "path": "/work/edit/edit.prproj", "close_others": true}
```

The result has `"open": 1` and `"sequences": 0`. `new` refuses an existing path unless `replace` is
true.

## 2. Import the media

```json
{"files": ["/work/pattern.mp4", "/work/bars.mp4"], "bin": "Source"}
```

`premiere_import` creates the `Source` bin and returns each file's `name` and `media_path`.

## 3. Create a sequence

`premiere_sequence_new` takes its settings from a project item:

```json
{"name": "Edit", "clip": "/work/pattern.mp4"}
```

The result: `fps` 25, `width` 1280, `height` 720, with 3 video and 3 audio tracks.

## 4. Place the clips

`premiere_clip_place` takes a project item as a media path or a name, and a time:

```json
{"item": "/work/pattern.mp4", "at": 0}
{"item": "bars.mp4", "at": 3, "in_point": 0, "out_point": 2}
```

Each call returns the placed `clip` with its track `position`, `start`, `end`, source `in_point` and
`out_point` and `media_path`. The first clip fills 0 to 3 seconds; the second, with source 0 to 2
seconds, fills 3 to 5.

## 5. Add a dissolve

```json
{"at": 3, "transition": "cross_dissolve", "frames": 12}
```

`premiere_transition_add` puts the transition at the start of the clip at 3 seconds. With the default
`alignment` of 0.5 it is centered on the cut, and the result reported `start` 2.76 and `end` 3.24.

## 6. Change the first clip

```json
{"at": 0.5, "scale": 120, "opacity": 90}
```

`premiere_clip_props` reports `applied`: `{"scale": 120, "opacity": 90}`. Position is in pixels from the
top left, rotation in degrees and `volume_db` for audio; `keyframes` animate any of them.

## 7. Export

```json
{"master": "/work/edit/edit.mov"}
```

`premiere_export` uses ProRes 422 HQ unless `preset` names another. The result had `frames` 125 and
`expected_frames` 125 with `complete` true: the frame count `ffprobe` read from the file equals the
sequence length (5 seconds at 25 fps).

## 8. Save

`premiere_project` with `action` `save`, then `action` `close` when you are done.

Next: [Cut from a clip list](cut-from-clip-list.md) does the work of steps 1 to 5 and 7 for a whole clip list in one call,
and [Export and encode](exports.md) covers presets and ranges.
