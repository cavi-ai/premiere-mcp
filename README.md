# Premiere MCP

MCP server for Adobe Premiere Pro on macOS. It runs ExtendScript in Premiere through an Adobe Bridge
BridgeTalk relay, exposes the common Premiere operations as typed tools, and cuts a clip list into
a new project with transitions and a ProRes 422 HQ master.

## Install

Requires macOS, Premiere Pro 2026 or later, Adobe Bridge 2026 or later (the script relay), FFmpeg
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
| `premiere_status` | Installed Premiere Pro and Adobe Bridge, versions and pids, relay install state, mailbox path, and the system ProRes 422 HQ export preset.
| `premiere_bridge_install` | Copies the relay startup script into Adobe Bridge's user Startup Scripts folder and reports whether it matches the packaged copy. | |
| `premiere_script` | Runs a `.jsx` file in Premiere with the globals `CAVI_ARGS` and `CAVI_REPORT` and returns its last value as `answer`. When `report` names a `.json` path, the script writes JSON there and the call returns it. |
| `premiere_cut` | Cuts a clip list into a new project and exports a ProRes 422 HQ `.mov` master; returns the master's frame count from `ffprobe`. |
| `premiere_project` | Opens, creates (`new` refuses an existing path unless `replace`), saves or closes a `.prproj`; `close_others` closes every other open project unsaved and `open` reports the count. |
| `premiere_inspect` | Bins, project items (media path, offline, duration, fps, frame size), sequences with every track's clips and transitions, and sequence markers. |
| `premiere_transitions` | Lists every video and audio transition this Premiere offers, read from QE. |
| `premiere_presets` | Lists export presets (`.epr`: Premiere, Media Encoder and user) and sequence presets (`.sqpreset`) by name. |
| `premiere_import` | Imports files into a named bin, created when missing. |
| `premiere_sequence_new` | Creates an empty sequence with the settings of a project item or of a `.sqpreset` (path or listed name). |
| `premiere_clip_place` | Places a project item or file on any video or audio track at a time, with source in/out, overwrite or insert. |
| `premiere_clip_props` | Sets Motion position, scale and rotation, Opacity and audio Volume on a placed clip, static or keyframed. |
| `premiere_transition_add` | Adds a QE transition of a given kind and length at the start or end of any track's clip. |
| `premiere_media_replace` | Points a project item at a new file (or refreshes it) and confirms through `premiere_inspect`. |
| `premiere_markers_add` | Adds sequence markers, including a beat grid from bpm and beats per bar. |
| `premiere_clip_edit` | Trims, moves (in time and to another track), enables or disables, renames, links, unlinks or removes (ripple or lift) a placed clip found by time, index or name. |
| `premiere_razor` | Splits one track or every track of a kind at one or more times with the QE razor. |
| `premiere_clip_speed` | Sets a clip's speed in percent or the duration it fills, with reverse, audio pitch and ripple; returns the resulting duration. |
| `premiere_sequence_set` | Sets frame size, frame rate and audio rate, in/out points; nests clips into a new sequence, duplicates, renames or deletes a sequence. |
| `premiere_tracks` | Adds video and audio tracks, sets mute, lock and target per track, and returns the counts and every track's state. |
| `premiere_frame_export` | Exports PNG stills of a sequence at given times and returns their paths and sizes. |
| `premiere_auto_reframe` | Makes a new sequence at another aspect ratio (9:16, 1:1, 4:5, ...) with Auto Reframe, a motion preset and the nest option. |
| `premiere_encode` | Queues a sequence in Adobe Media Encoder with a preset and a range, starts the batch and judges the file. |
| `premiere_interchange` | Exports a sequence as FCP XML, AAF or OMF, or imports an FCP XML into the project. |
| `premiere_captions` | Imports an `.srt` and creates a caption track on a sequence. |
| `premiere_effects` | Lists the video and audio effects Premiere offers, with a name filter. |
| `premiere_effect_add` | Adds a video or audio effect to a placed clip and returns the clip's components. |
| `premiere_effect_set` | Sets or lists any component parameter by display names, static or keyframed with linear, hold or bezier interpolation, with colors as `#RRGGBB`. |
| `premiere_clip_fit` | Sets a video clip's Motion Scale and centers it so the source fits or fills the sequence frame. |
| `premiere_items` | Renames, moves to a bin, labels, subclips, interprets footage, attaches a proxy to, sets metadata on or deletes (bins) a project item. |
| `premiere_scene_detect` | Finds hard cuts inside a placed clip from its media and reports them as timeline seconds; can split the clip or add markers there. |
| `premiere_markers_edit` | Lists sequence markers, or updates (name, comment, new start, duration) or deletes one by index or time, or all. |
| `premiere_gaps` | Lists empty gaps across the unlocked tracks and closes them, moving later clips left so tracks stay in sync. |
| `premiere_range_remove` | Cuts a time range out of every unlocked track; `extract` closes the hole, `lift` leaves it. |
| `premiere_bins` | Creates, renames and deletes project bins and moves items into them. |
| `premiere_fade` | Fades a clip in and out with opacity (video) or volume (audio) keyframes. |
| `premiere_color` | Basic Lumetri Color correction (exposure, contrast, highlights, shadows, whites, blacks, temperature, tint, saturation, vibrance); adds the effect when missing. |
| `premiere_find` | Finds project items and placed clips by name or path; lists offline or unused items. |
| `premiere_clip_copy` | Places another copy of a clip (same media and source range) at a time or track; effects are not copied. |
| `premiere_mogrt_add` | Imports a `.mogrt` onto a track at a time and sets its text parameters. |
| `premiere_export` | Exports a sequence (whole, in/out range or work area, optional caption burn-in) with an `.epr` preset and confirms the file, the report and the `ffprobe` frame count. |

Paths are absolute. Adobe Bridge and Premiere Pro are opened in the background (`open -g -a`) when
they are not running. Times are seconds; tracks are 0-based (`track` 0 is V1 or A1); `sequence`
defaults to the active sequence. Every tool is a script in `src/cavi_premiere_mcp/jsx` run through
the relay with `CAVI_ARGS`, and answers the JSON report the script writes.

## Tool notes

- A project item is addressed by its absolute media path or its name. `premiere_clip_place` imports
  a file that is not in the project and puts the item's source in/out back after placing.
- `premiere_clip_props`: `position` is pixels from the top left; `scale` and `opacity` are percent;
  `rotation` is degrees; `volume_db` is dB (0 is unity). `keyframes[].time` is seconds from the
  clip's start, and a property with keyframes ignores its static value.
- `premiere_transition_add` and the clips of `premiere_cut` take any name `premiere_transitions`
  lists (`Cross Zoom`, `Constant Power`, ...) and the aliases `cross_dissolve`, `film_dissolve`,
  `dip_to_white`, `dip_to_black`.
  `alignment` 0 starts the transition at the cut, 0.5 centers it, 1 ends it there. A transition
  needs source handles on both sides to reach its full length.
- `premiere_markers_add` with `beat_grid` writes one marker per beat from `start` to `end`, named
  `bar.beat`; the first beat of a bar is commented `downbeat`.
- `premiere_mogrt_add` sets text through the template's exposed parameters, so it works with
  templates built in After Effects. The native Essential Graphics titles that ship with Premiere
  (`Basic Title`, `Basic Lower Third`) expose none; a request for text on one is refused.
  `video_track` must be an existing track. The text is confirmed by reading the parameter back.
- `premiere_clip_edit` `remove` takes the clip's linked clips with it unless `keep_linked`, and
  `ripple` shifts the later clips of every unlocked track left by the clip's length.
  `premiere_clip_edit` addresses a clip by `at`, `position_index` or `name`. `trim_start` and `trim_end`
  are timeline times and the source in/out follow them; a trim cannot reach past the source.
  `move_to` shifts only the addressed clip, never its audio or video partner. A move to another
  track places the clip again with its source range and its other stream, so it loses its effects and
  its name. `remove` `ripple` removes the clip and moves the later clips of the same track left;
  other tracks stay as they are. `unlink` takes the whole link group apart and `link_with` links
  two clips; `linked` in the answer counts the clips in the clip's link group (0 when unlinked).
- `premiere_razor` cuts at times on the frame grid; the answer counts the clips before and after.
- `premiere_clip_speed` keeps the source range: 200% halves the duration, 50% doubles it, and a
  clip that would run into its neighbour stops at it unless `ripple` is set. A clip's linked audio is
  a separate clip: call it again with `kind` audio.
- `premiere_sequence_set` nests the listed clips with `createSubsequence`; it copies the clips
  inside the in/out range into a new sequence and leaves the source clips on their track. The work
  area bounds cannot be set from a script; in/out points can.
- `premiere_export` and `premiere_encode` take `range` entire, in_out or work_area and compare the
  `ffprobe` frame count with the range's length. The work area cannot be changed from a script, so
  `work_area` is the whole sequence unless it was set in the UI.
- `premiere_encode` starts Media Encoder when it is not running and waits for it before queueing; the
  call returns when the output file exists, is closed and has the expected frames.
- `premiere_auto_reframe` keeps the source height and narrows the width (9:16 from 640x360 gives
  202x360); the new sequence is named by `name`.
- `premiere_interchange` `import_xml` adds the XML's sequence to the project; an imported sequence
  keeps its name, so it can share one with the original.
- `premiere_captions` counts cues in the `.srt`. The caption track shows in `premiere_frame_export`
  stills. `premiere_export` `burn_captions` exports from a copy of the preset (written to a temporary folder)
  with `DoCaptions` set: an H.264 preset burns the caption into the picture
  (white text at the bottom in the frame; false removes it), a ProRes preset has no effect.
- `premiere_mogrt_add` renders the template as placed (Bold Coming Up shows its default text in a
  frame). The built-in templates expose no text parameters, and the `Source Text` property of their
  `Text` component takes an encoded value: a plain string replaces the text with a broken render.
  Setting text is verified only through the template's exposed parameters. The value of `Source Text`
  is not JSON (no `textEditValue`) and `getMGTComponent` is null on these templates, so the
  JSON path does not apply.
- `premiere_effect_set` finds a component by display name (`component_index` for repeats) and a
  parameter by display name (`index` when several share one, as Lumetri Color's Saturation does).
  Key times are seconds from the clip's start. Measured: Lumetri Color Saturation 0 turned red
  (255,0,0) into gray (135,135,135) and Temperature 60 moved (255,255,0) to (255,247,0); Crop Left and
  Right 25 turned a green pixel black; Gaussian Blur Amount keyed 0 to 80 lowered the edge energy of
  frames from 11.0 to 5.6 to 3.6; Transform Scale Height and Width 40 blacked a corner pixel; Ultra Key
  with `#c60000` changed the keyed red area; audio Amplify Gain 0.9 raised the exported mean volume
  from -24.1 dB to -0.5 dB. Lumetri's Input LUT and Look take no file: a path is refused and a list
  index is accepted without changing the picture. The Gaussian Blur effect (not the legacy one) has
  Amount where the legacy one has Blurriness; Transform has Scale Width and Scale Height with Uniform
  Scale off.
- `premiere_clip_fit` computes the scale from the source frame size (a 1280x720 clip in a 640x360
  sequence gets Scale 50 for fit, 50 for fill) because the QE `scaleToFrameSize` flag cannot be set.
- `premiere_items` takes a media path or a name (bins by name). `subclip` times are source seconds and
  the subclip lands in the project root; `premiere_inspect` shows it with `clip_duration` (the
  subclip's length) next to `duration` (the media's), and `label` per item. `interpret` frame_rate 30 on
  a 25 fps 6 s clip changed its `duration` to 5; field order, pixel aspect and alpha usage read back as
  set. `proxy` needs a file that matches the clip (a 320x180 ProRes copy with the same audio was
  accepted; one without audio was refused). `xmp` writes xmpDM text properties (logComment, shotName,
  ...) and reads them back. Bins can be deleted with their contents; clip items cannot be deleted
  from a script (`deleteBin` returns true and the item stays).
- `premiere_scene_detect` reads the clip's source with ffmpeg because `performSceneEditDetectionOnSelection`
  returned true and changed nothing (ApplyCuts and CreateMarkers, ProRes and H.264 clips, after 20 s). A
  clip of three 1 s colors placed at 8 s reported cuts at 9.0 and 10.0, and `cuts` split it there.
- `premiere_export` `burn_captions` and `premiere_encode` check every input before Premiere or Media
  Encoder is started; preset copies live in a temporary folder for the call.
- `premiere_tracks` adds stereo audio tracks and appends them after the last track.
- `premiere_frame_export` writes `<folder>/<prefix>_<n>_<time>s.png` and checks each file and its
  PNG header on disk; a time at or past the sequence end is refused.
- `premiere_export` and `premiere_sequence_new` take an absolute path or a name from
  `premiere_presets`. A name used by several formats is written `format/name`, for example
  `H264/00 - Match Source - High bitrate`; user presets win over system ones. Export defaults to
  Apple ProRes 422 HQ.
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

Measured with Premiere Pro 2026 and Adobe Bridge 2026 on macOS.

1. Bridge has no AppleScript dictionary, so a startup script, `cavi-bridge-relay.jsx`, relays jobs.
   The client writes `<id>.job` (BridgeTalk target on the first line, script after it) into
   `~/Library/Application Support/cavi-bridge-relay/`; the relay polls every 200 ms, sends the body
   over BridgeTalk and writes `<id>.reply` (`ok` or `error`, then the result). The relay is
   app-agnostic: the target is a parameter. Run `premiere_bridge_install`, restart Bridge and approve
   the script once in Bridge Settings > Startup Scripts; until then the ping fails with an approval message.
   Headless After Effects (`-noui`) has no BridgeTalk and cannot serve as the relay.
2. A Premiere that is still starting refuses BridgeTalk messages with
   `TARGET COULD NOT BE LAUNCHED`. The relay sends a ping every 5 seconds, for up to 300 seconds,
   until Premiere answers.
3. Premiere stalls in `app.newProject()` when an earlier project is still open at the same path.
   The cut closes every open project unsaved (`closeDocument(0, 0)`) before creating its project.
4. `exportAsMediaDirect` with the system preset `Apple ProRes 422 HQ.epr` writes the master
   synchronously. A ProRes movie with a timecode track lists `nb_frames` twice in `ffprobe`; the
   first value is the video stream's.
5. A script body sent through BridgeTalk reaches Premiere with every backslash doubled, so the client
   writes the script to a temporary file and Premiere evaluates that file.
6. Premiere keeps showing the old frames of a source movie that is overwritten on disk while its
   project is open. Measured with a red 3 s ProRes clip on V1: the export read (255, 25, 0) at
   frame 25; after the file was overwritten with blue the next export still read (255, 25, 0),
   and `refreshMedia` alone changed nothing. After `premiere_media_replace` (the item taken
   offline, relinked to the same path and refreshed) the export read (0, 16, 255).
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
12. A `TrackItem` write of `start` or `end` moves one edge and leaves `inPoint` and `outPoint`; a trim
    sets all four. A start past the current end needs the end set first. `TrackItem.move` takes a
    time offset and moves only that clip. `TrackItem.remove(ripple)` and QE `remove` delete the
    clip and leave the gap open.
13. `Sequence.unlinkSelection` returns false unless the selection holds the whole link group (a
    linked clip selected through a script does not select its partner); `linkSelection` needs
    both clips selected. Both need the sequence open (`openSequence`). `getLinkedItems` is null for
    an unlinked clip.
14. QE `setSpeed(speed, duration, reverse, maintainPitch, ripple)`: `speed` is a ratio (2 is 200%)
    and `duration` is the timecode the clip fills; a zero duration keeps the length and is clamped
    by the source. The clip's `inPoint` and `outPoint` read as timeline times after a speed change.
15. QE `addTracks(videoCount, afterVideo, audioCount, afterAudio, audioType)` takes 0-based
    positions of an existing track; a position past the last audio track adds nothing.
16. QE `exportFramePNG(timecode, path)` writes `path.png` and returns true and the file
    exists when the call returns. `setWorkAreaInPoint`,
    `setWorkAreaOutPoint` and QE `setWorkInPoint` return without changing the work area.
17. `Sequence.setSettings` accepts `videoFrameWidth`, `videoFrameHeight`, `previewFrameWidth`,
    `previewFrameHeight`, `videoFrameRate` and `audioSampleRate` as `Time` objects in ticks
    (`254016000000` per second divided by the rate) and applies them to a sequence that has clips.
18. `Sequence.exportAsFinalCutProXML(path, 1)`, `Project.exportAAF` and `Project.exportOMF` write their
    files synchronously; OMF also writes `<name>omfLog.txt` beside it. `importFiles` on an FCP XML adds
    its sequence. `autoReframeSequence(num, den, preset, name, nest)` returns the new sequence.
19. `app.encoder.encodeSequence(sequence, path, preset, range, 1)` returns a job id and
    `startBatch()` runs it; right after Media Encoder launches the job is not accepted, so the tool
    waits for the launch. A 4 s ProRes in/out job finished in about 25 s.

## Development

```sh
uv sync --dev
uv run ruff check .
uv run pytest
```
