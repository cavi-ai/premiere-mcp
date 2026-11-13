# Premiere Pro behavior

Behavior that the tools depend on and that Adobe does not document, measured with Premiere Pro 2026 and
Adobe Bridge 2026 on macOS. Each item says what was observed.

## Scripting interface

1. Bridge has no AppleScript dictionary, so a startup script, `cavi-bridge-relay.jsx`, relays jobs. The
   client writes `<id>.job` (BridgeTalk target on the first line, script after it) into the mailbox
   folder; the relay polls every 200 ms, sends the body over BridgeTalk and writes `<id>.reply` (`ok` or
   `error`, then the result). Headless After Effects (`-noui`) has no BridgeTalk and cannot serve as the
   relay.
2. A Premiere Pro that is still starting refuses BridgeTalk messages with `TARGET COULD NOT BE
   LAUNCHED`. The relay sends a ping every 5 seconds, for up to 300 seconds, until Premiere Pro answers. A
   freshly launched Premiere Pro needs about 90 seconds before the relay answers.
3. A script body sent through BridgeTalk reaches Premiere Pro with every backslash doubled, so the client
   writes the script to a temporary file and Premiere Pro evaluates that file.
4. The relay can answer `timed out` while Premiere Pro keeps exporting. Exports and cuts are judged by the
   report file, the output file with no process holding it open (`lsof`) and its `ffprobe` frame count,
   not by the relay's answer.

## Projects and media

5. Premiere Pro stalls in `app.newProject()` when an earlier project is still open at the same path. The cut
   closes every open project unsaved (`closeDocument(0, 0)`) before creating its project.
6. Premiere Pro keeps showing the old frames of a source movie that is overwritten on disk while its
   project is open. Measured with a red 3 s ProRes clip on V1: the export read (255, 25, 0) at frame 25;
   after the file was overwritten with blue the next export still read (255, 25, 0), and `refreshMedia`
   alone changed nothing. After `premiere_media_replace` (the item taken offline, relinked to the same
   path and refreshed) the export read (0, 16, 255).
7. `exportAsMediaDirect` with the system preset `Apple ProRes 422 HQ.epr` writes the master synchronously.
   A ProRes movie with a timecode track lists `nb_frames` twice in `ffprobe`; the first value is the
   video stream's.
8. `importMGT` puts a template on the last track when the offset is past it. Its text parameters are JSON
   strings with a `textEditValue` field, exposed only by templates with an `MGT` component.
9. `premiere_items`: `interpret` frame_rate 30 on a 25 fps 6 s clip changed its `duration` to 5; field
   order, pixel aspect and alpha usage read back as set. `proxy` needs a file that matches the clip (a
   320x180 ProRes copy with the same audio was accepted; one without audio was refused). `xmp` writes
   xmpDM text properties (logComment, shotName, ...) and reads them back. Bins can be deleted with their
   contents; clip items cannot be deleted from a script (`deleteBin` returns true and the item stays).
   `subclip` times are source seconds and the subclip lands in the project root; `premiere_inspect` shows
   it with `clip_duration` (the subclip's length) next to `duration` (the media's), and `label` per item.

## Timeline

10. Keyframe times in `addKey` and `getValueAtTime` are source times: the clip's in point plus the time
    from the clip's start. Motion position is normalized (0 to 1). Volume `Level` is linear gain where
    0.17782794 is 0 dB. `Sequence.end` is a string of ticks (254016000000 per second).
11. A QE track lists empty gaps as items; the nth item of type `Clip` is the nth clip of the track.
    Transitions are not listed there.
12. A `TrackItem` write of `start` or `end` moves one edge and leaves `inPoint` and `outPoint`; a trim sets
    all four. A start past the current end needs the end set first. `TrackItem.move` takes a time offset
    and moves only that clip. `TrackItem.remove(ripple)` and QE `remove` delete the clip and leave the gap
    open.
13. `Sequence.unlinkSelection` returns false unless the selection holds the whole link group (a linked
    clip selected through a script does not select its partner); `linkSelection` needs both clips
    selected. Both need the sequence open (`openSequence`). `getLinkedItems` is null for an unlinked clip.
14. QE `setSpeed(speed, duration, reverse, maintainPitch, ripple)`: `speed` is a ratio (2 is 200%) and
    `duration` is the timecode the clip fills; a zero duration keeps the length and is clamped by the
    source. The clip's `inPoint` and `outPoint` read as timeline times after a speed change.
15. QE `addTracks(videoCount, afterVideo, audioCount, afterAudio, audioType)` takes 0-based positions of an
    existing track; a position past the last audio track adds nothing.
16. `Sequence.setSettings` accepts `videoFrameWidth`, `videoFrameHeight`, `previewFrameWidth`,
    `previewFrameHeight`, `videoFrameRate` and `audioSampleRate` as `Time` objects in ticks
    (`254016000000` per second divided by the rate) and applies them to a sequence that has clips.
17. `setWorkAreaInPoint`, `setWorkAreaOutPoint` and QE `setWorkInPoint` return without changing the work
    area, so `work_area` is the whole sequence unless it was set in the Premiere Pro window. In and out
    points can be set.
18. QE `exportFramePNG(timecode, path)` writes `path.png`, returns true, and the file exists when the call
    returns.
19. `Sequence.exportAsFinalCutProXML(path, 1)`, `Project.exportAAF` and `Project.exportOMF` write their
    files synchronously; OMF also writes `<name>omfLog.txt` beside it. `importFiles` on an FCP XML adds its
    sequence. `autoReframeSequence(num, den, preset, name, nest)` returns the new sequence.
20. `app.encoder.encodeSequence(sequence, path, preset, range, 1)` returns a job id and `startBatch()` runs
    it; right after Media Encoder launches the job is not accepted, so the tool waits for the launch. A 4 s
    ProRes in/out job finished in about 25 s.

## Tool behavior

- A project item is addressed by its absolute media path or its name. `premiere_clip_place` imports a file
  that is not in the project and puts the item's source in and out back after placing.
- `premiere_clip_props`: `position` is pixels from the top left; `scale` and `opacity` are percent;
  `rotation` is degrees; `volume_db` is dB (0 is unity). `keyframes[].time` is seconds from the clip's
  start, and a property with keyframes ignores its static value.
- `premiere_transition_add` and the clips of `premiere_cut` take any name `premiere_transitions` lists
  (`Cross Zoom`, `Constant Power`, ...) and the aliases `cross_dissolve`, `film_dissolve`,
  `dip_to_white`, `dip_to_black`. `alignment` 0 starts the transition at the cut, 0.5 centers it, 1 ends it
  there. A transition needs source handles on both sides to reach its full length.
- `premiere_markers_add` with `beat_grid` writes one marker per beat from `start` to `end`, named
  `bar.beat`; the first beat of a bar is commented `downbeat`.
- `premiere_mogrt_add` sets text through the template's exposed parameters, so it works with templates
  built in After Effects. The native Essential Graphics titles that ship with Premiere Pro (`Basic Title`,
  `Basic Lower Third`) expose none, and a request for text on one is refused. The built-in templates render
  as placed (Bold Coming Up shows its default text); the `Source Text` property of their `Text` component
  takes an encoded value, and a plain string replaces the text with a broken render. `video_track` must be
  an existing track. The text is confirmed by reading the parameter back.
- `premiere_clip_edit` `remove` takes the clip's linked clips with it unless `keep_linked`. `ripple` removes
  the clip and moves the later clips of the same track left; other tracks stay as they are. `trim_start` and
  `trim_end` are timeline times and the source in and out follow them; a trim cannot reach past the source.
  `move_to` shifts only the addressed clip, never its audio or video partner. A move to another track places
  the clip again with its source range and its other stream, so it loses its effects and its name. `unlink`
  takes the whole link group apart and `link_with` links two clips; `linked` in the answer counts the clips
  in the clip's link group (0 when unlinked).
- `premiere_razor` cuts at times on the frame grid; the answer counts the clips before and after.
- `premiere_clip_speed` keeps the source range: 200% halves the duration, 50% doubles it, and a clip that
  would run into its neighbour stops at it unless `ripple` is set. A clip's linked audio is a separate
  clip: call it again with `kind` audio.
- `premiere_sequence_set` nests the listed clips with `createSubsequence`; it copies the clips inside the
  in/out range into a new sequence and leaves the source clips on their track.
- `premiere_export` and `premiere_encode` take `range` entire, in_out or work_area and compare the
  `ffprobe` frame count with the range's length.
- `premiere_encode` starts Media Encoder when it is not running and waits for it before queueing; the call
  returns when the output file exists, is closed and has the expected frames.
- `premiere_auto_reframe` keeps the source height and narrows the width (9:16 from 640x360 gives 202x360);
  the new sequence is named by `name`.
- `premiere_interchange` `import_xml` adds the XML's sequence to the project; an imported sequence keeps its
  name, so it can share one with the original.
- `premiere_captions` counts cues in the `.srt`. The caption track shows in `premiere_frame_export` stills.
  `premiere_export` `burn_captions` exports from a copy of the preset (written to a temporary folder) with
  `DoCaptions` set: an H.264 preset burns the caption into the picture (white text at the bottom of the
  frame; false removes it), a ProRes preset has no effect.
- `premiere_effect_set` finds a component by display name (`component_index` for repeats) and a parameter
  by display name (`index` when several share one, as Lumetri Color's Saturation does). Key times are
  seconds from the clip's start. Measured: Lumetri Color Saturation 0 turned red (255,0,0) into gray
  (135,135,135) and Temperature 60 moved (255,255,0) to (255,247,0); Crop Left and Right 25 turned a green
  pixel black; Gaussian Blur Amount keyed 0 to 80 lowered the edge energy of frames from 11.0 to 5.6 to
  3.6; Transform Scale Height and Width 40 blacked a corner pixel; Ultra Key with `#c60000` changed the
  keyed red area; audio Amplify Gain 0.9 raised the exported mean volume from -24.1 dB to -0.5 dB.
  Lumetri's Input LUT and Look take no file: a path is refused and a list index is accepted without
  changing the picture. The Gaussian Blur effect (not the legacy one) has Amount where the legacy one has
  Blurriness; Transform has Scale Width and Scale Height with Uniform Scale off.
- `premiere_clip_fit` computes the scale from the source frame size (a 1280x720 clip in a 640x360 sequence
  gets Scale 50 for fit, 50 for fill) because the QE `scaleToFrameSize` flag cannot be set.
- `premiere_scene_detect` reads the clip's source with ffmpeg because `performSceneEditDetectionOnSelection`
  returned true and changed nothing (ApplyCuts and CreateMarkers, ProRes and H.264 clips, after 20 s). A
  clip of three 1 s colors placed at 8 s reported cuts at 9.0 and 10.0, and `cuts` split it there.
- `premiere_tracks` adds stereo audio tracks and appends them after the last track.
- `premiere_frame_export` writes `<folder>/<prefix>_<n>_<time>s.png` and checks each file and its PNG
  header on disk; a time at or past the sequence end is refused.
