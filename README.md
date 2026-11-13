# Premiere MCP

MCP server for Adobe Premiere Pro on macOS. It runs ExtendScript in Premiere through a Photoshop
BridgeTalk relay, exposes the common Premiere operations as typed tools, and cuts a clip list into
a new project with transitions and a ProRes 422 HQ master.

## Install

Requires macOS, Premiere Pro 2026 or later, Photoshop 2026 or later (the script relay), FFmpeg
(`ffprobe`) and Python 3.15.

```sh
uv sync
uv run cavi-premiere-mcp
```

The server speaks MCP over stdio. Client configuration:

```json
{"mcpServers": {"premiere": {"command": "uv", "args": ["--directory", "/path/to/premiere-mcp", "run", "cavi-premiere-mcp"]}}}
```

## Tools

| Tool | What it does |
|---|---|
| `premiere_status` | Installed Premiere Pro and Photoshop, their versions and pids, and the system ProRes 422 HQ export preset. |
| `premiere_script` | Runs a `.jsx` file in Premiere with the globals `CAVI_ARGS` and `CAVI_REPORT` and returns its last value as `answer`. When `report` names a `.json` path, the script writes JSON there and the call returns it. |
| `premiere_cut` | Cuts a clip list into a new project and exports a ProRes 422 HQ `.mov` master; returns the master's frame count from `ffprobe`. |
| `premiere_project` | Opens, creates (`new` refuses an existing path unless `replace`), saves or closes a `.prproj`. |
| `premiere_inspect` | Bins, project items (media path, offline, duration, fps, frame size), sequences with every track's clips and transitions, and sequence markers. |
| `premiere_import` | Imports files into a named bin, created when missing. |
| `premiere_sequence_new` | Creates an empty sequence with the settings of a project item or of a `.sqpreset` (path or preset name). |
| `premiere_clip_place` | Places a project item or file on any video or audio track at a time, with source in/out, overwrite or insert. |
| `premiere_clip_props` | Sets Motion position, scale and rotation, Opacity and audio Volume on a placed clip, static or keyframed. |
| `premiere_transition_add` | Adds a QE transition of a given kind and length at the start or end of any track's clip. |
| `premiere_media_replace` | Points a project item at a new file (or refreshes it) and confirms through `premiere_inspect`. |
| `premiere_markers_add` | Adds sequence markers, including a beat grid from bpm and beats per bar. |
| `premiere_mogrt_add` | Imports a `.mogrt` onto a track at a time and sets its text parameters. |
| `premiere_export` | Exports a sequence with an `.epr` preset and confirms the file, the report and the `ffprobe` frame count. |

Paths are absolute. Photoshop and Premiere Pro are opened in the background (`open -g -a`) when
they are not running. Times are seconds; tracks are 0-based (`track` 0 is V1 or A1); `sequence`
defaults to the active sequence. Every tool is a script in `src/cavi_premiere_mcp/jsx` run through
the relay with `CAVI_ARGS`, and answers the JSON report the script writes.

## Tool notes

- A project item is addressed by its absolute media path or its name. `premiere_clip_place` imports
  a file that is not in the project and puts the item's source in/out back after placing.
- `premiere_clip_props`: `position` is pixels from the top left; `scale` and `opacity` are percent;
  `rotation` is degrees; `volume_db` is dB (0 is unity). `keyframes[].time` is seconds from the
  clip's start, and a property with keyframes ignores its static value.
- `premiere_transition_add`: `transition` is Premiere's name (`Cross Dissolve`, `Film Dissolve`,
  `Dip to Black`, `Dip to White`; audio `Constant Power`, `Constant Gain`, `Exponential Fade`).
  `alignment` 0 starts the transition at the cut, 0.5 centers it, 1 ends it there. A transition
  needs source handles on both sides to reach its full length.
- `premiere_markers_add` with `beat_grid` writes one marker per beat from `start` to `end`, named
  `bar.beat`; the first beat of a bar is commented `downbeat`.
- `premiere_mogrt_add` sets text through the template's exposed parameters, so it works with
  templates built in After Effects. The native Essential Graphics titles that ship with Premiere
  (`Basic Title`, `Basic Lower Third`) expose none; a request for text on one is refused.
  `video_track` must be an existing track.
- `premiere_export` returns `frames` from `ffprobe` and `expected_frames` from the sequence length;
  `complete` is true when they match. `premiere_cut` is judged the same way.
- To change a source movie that is written again on disk while its project stays open, call
  `premiere_media_replace` for it (a new file name, or the same path to refresh); Premiere keeps
  showing the old frames otherwise.

## Cut

```json
{
  "project": "/work/cut/cut.prproj",
  "master": "/work/cut/master.mov",
  "audio": "/work/score.wav",
  "clips": [
    {"file": "/work/a.mov", "start": 0, "in_point": 0.5, "out_point": 1.5},
    {"file": "/work/b.mov", "start": 1, "in_point": 0.5, "out_point": 2,
     "transition": {"kind": "cross_dissolve", "frames": 8}}
  ]
}
```

- `start` is the clip's timeline position; `in_point` and `out_point` are source times. All are
  seconds and are snapped to the first clip's frame grid.
- Clips are ordered by `start` and must not overlap; gaps stay empty. Clip files must have
  distinct file names.
- The sequence takes its settings from the first clip. Clip audio is not used; the optional
  `audio` file starts at 0 on A1 and plays in full, and the export covers the whole sequence.
- `transition.kind` is `cross_dissolve`, `film_dissolve`, `dip_to_white` or `dip_to_black`. A
  transition sits at the start of its clip: single-sided on the first clip, centered on the cut
  otherwise. A transition Premiere cannot add is returned in `warnings`.
- An existing project, master or report (`<project>.report.json`) is refused unless
  `replace` is true, which deletes them first.
- `cut_frames` is the end of the last clip in frames; `frames` is the exported master's.

## Behavior notes

Measured with Premiere Pro 2026 and Photoshop 2026 on macOS.

1. Premiere receives ExtendScript from Photoshop `do javascript` through BridgeTalk.
   `BridgeTalk.send(timeout)` in Photoshop is synchronous, so the relay returns Premiere's answer.
   Headless After Effects (`-noui`) has no BridgeTalk and cannot serve as the relay.
2. A Premiere that is still starting refuses BridgeTalk messages with
   `TARGET COULD NOT BE LAUNCHED`. The relay sends a ping every 5 seconds, for up to 300 seconds,
   until Premiere answers.
3. Premiere stalls in `app.newProject()` when an earlier project is still open at the same path.
   The cut closes every open project unsaved (`closeDocument(0, 0)`) before creating its project.
4. `exportAsMediaDirect` with the system preset `Apple ProRes 422 HQ.epr` writes the master
   synchronously. A ProRes movie with a timecode track lists `nb_frames` twice in `ffprobe`; the
   first value is the video stream's.
5. A script body sent through BridgeTalk reaches Premiere with every backslash doubled, so the relay
   writes the script to a temporary file and Premiere evaluates that file.
6. Premiere keeps showing the old frames of a source movie that is overwritten on disk while its
   project is open; `changeMediaPath` and `refreshMedia` (`premiere_media_replace`) make it read
   the file again.
7. The relay can answer `timed out` while Premiere keeps exporting. Exports and cuts are judged by
   the report file, the output file with no process holding it open (`lsof`) and its `ffprobe`
   frame count, not by the relay's answer.
8. A freshly launched Premiere needs about 90 seconds before the relay answers; the 300 second
   ping loop covers it.
9. Keyframe times in `addKey` and `getValueAtTime` are source times: the clip's in point plus the
   time from the clip's start. Motion position is normalized (0 to 1). Volume `Level` is linear
   gain where 0.17782794 is 0 dB. `Sequence.end` is a string of ticks (254016000000 per second).
10. A QE track lists empty gaps as items; the nth item of type `Clip` is the nth clip of the track.
    Transitions are not listed there.
11. `importMGT` puts a template on the last track when the offset is past it. Its text parameters
    are JSON strings with a `textEditValue` field, exposed only by templates with an `MGT`
    component.

## Development

```sh
uv sync --dev
uv run ruff check .
uv run pytest
```
