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
   closes a project open at its path unsaved (`closeDocument(0, 0)`) before creating its project.
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
    it; right after Media Encoder launches the job is not accepted, so the tool waits until the `ame`
    target answers a script. A 4 s ProRes in/out job finished in about 25 s; on 27.0.0 a 3 s ProRes job from
    Media Encoder stopped took 10 s. `app.encoder.bind("onEncoderJobError", f)` and
    `"onEncoderJobComplete"` run after the script that queued the job has returned; a master in a read-only
    folder gives `Encoding error (9007)`. Media Encoder's `getBatchEncoderStatus()` read `stopped` 2 s after
    both a failed and a finished job. An empty sequence queues a job that writes no file.
21. `overwriteClip` and `insertClip` at a time off the frame grid start the clip on the nearest frame (20 s
    in a 23.976 fps sequence starts at 20.02). Source in and out points land on frames of the media (0.5 and
    2.5 on 25 fps media read back 0.48 and 2.48).
22. `Marker.setColorByIndex(index)` colours the marker it is called on (a second argument is ignored) and
    `getColorByIndex()` reads it back. `setTypeAsChapter`, `setTypeAsSegmentation`, `setTypeAsComment` and
    `setTypeAsWebLink(url, frameTarget)` return true and set `type` to Chapter, Segmentation, Comment and
    WebLink; `getWebLinkURL` and `getWebLinkFrameTarget` read the link back.
23. QE `removeEffects()` on a video clip removes its effects and keeps Motion and Opacity; on an audio clip it
    returns true and the effects stay. QE `getComponentAt(n).remove()` removes that one effect from a video
    or an audio clip. `remove(false, false)` on an item of `Track.transitions` removes the transition and
    leaves the clips.
24. QE `getClipPanComponent()` on an audio clip returns the `Panner` component, whose one parameter is `Pan`
    on a mono clip and `Balance` on a stereo clip. A QE audio track has two components: `Track` with
    `Volume` and `Mute`, and an unnamed one with no parameters; the DOM audio track has no volume. QE
    `setParamValue` takes the value as a string (`"30"`, `"0.5"`, `"true"`) and refuses a number with
    `Illegal Parameter type`; Pan `"30"` reads back `30.00` and Volume `"0.5"` reads back `0.50`. Track
    `Volume` is linear gain: exports of a track at 1, 2 and 0.5 measured 0, +6 and -6 dB against the source,
    and 0 is silent.
25. Media Encoder answers BridgeTalk as target `ame`. `app.getEncoderHost()` has `getBatchEncoderStatus`
    (`stopped`, `running`), `isBatchRunning`, `runBatch`, `pauseBatch` and `stopBatch`. `stopBatch()`
    returned true and stopped an 11-minute 23.976 fps encode; the partial movie stayed on disk and no process
    held it open.
26. `Project.saveAs(path)` returns true, writes the project at `path`, opens it and closes the project at the
    old path. The old file stays on disk and other open projects stay open.
27. A retimed clip's `inPoint` and `outPoint` read source time divided by the speed: source 1 to 5 s at
    200% reads 0.5 and 2.5. `getSpeed()` returns the ratio (2), also on a reversed clip, and
    `isSpeedReversed()` the direction. Keyframe times (`addKey`, `getValueAtTime`) are source times: opacity
    keys at 0 and 2 on a 200% white clip rendered alpha 133 at 0.5 s and 255 at 1 s; keys at
    (`inPoint` + offset) × speed render 66, 128 and 255 at 0.5, 1 and 2 s, as on a 100% clip. QE `setSpeed(ratio, duration,
    reverse, pitch, ripple)` with `duration` equal to the clip's span keeps the span and plays further into
    the source (source 0 to 3 s at 2 became source 0 to 6 s in the same 3 s).
28. A 480 × 270 movie with sample aspect 2 reads `VideoInfo` `480 x 270 (2.0)` and
    `getFootageInterpretation().pixelAspectRatio` 2; a square-pixel sequence reads `videoPixelAspectRatio`
    `1:1`. QE `exportFramePNG` writes RGBA, so a clip's opacity is read from the alpha channel.
29. QE project `newBlackVideo(width, height, fps, parNum, parDen)` and `newTransparentVideo` (same
    arguments) return true and add "Black Video" or "Transparent Video" at the project root, readable
    through the DOM in the next call: `newTransparentVideo(1280, 720, 25, 1, 1)` read `1280 x 720 (1.0),
    Straight Alpha`, and every new still item has a 5 s out point. `newBarsAndTone(w, h, fps, parNum,
    parDen, rate)` ignores its size and rate: 1280x720 at 25, 640x360 at 29.97 and 640x360 at 25 all gave
    "HD Bars and Tone", `1920 x 1080 (1.2121)`, 4.97 s. The reflected argument names are `p0` to `p4` for
    the black, color matte and transparent calls and `p0` to `p5` for bars and tone and the universal
    counting leader.
30. After a project is closed and another is created at the same path in the same Premiere Pro session, QE
    project calls such as `newBlackVideo` still return true but add the item to the earlier project: `qe.project.numItems`
    starts at the earlier count and the DOM shows no new item. A project at a new path behaves correctly.
31. QE sequence `getYellowBarTimes()` on a sequence of one unrendered H.264 clip (0 to 3 s) returned an
    array of two `QETime` objects (`secs`, `ticks`, `timecode`, `frames`) for 0 and 3.00000023841858 s, so
    ranges are flat start, end pairs; `getRedBarTimes()` and `getGreenBarTimes()` returned empty arrays.
    `renderAll`, `renderPreview` and `getRedBarTimes` reflect no arguments.
32. Not measured on 27.0.0: `renderAll` and `renderPreview` on a sequence, `newColorMatte` (how a color is
    given) and `newUniversalCountingLeader`. Premiere Pro stopped answering the relay after a
    `newUniversalCountingLeader(640, 360, 25, 1, 1, 48000)` call and had not answered 30 minutes later, so
    `premiere_item_new` offers bars and tone, black video and transparent video only and no render tool is
    registered.

## Tool behavior

- A project item is addressed by its id (`nodeId`), its absolute media path or its name, and a sequence by
  its id (`sequenceID`) or its name; a reference that several answer to is refused with their ids.
  `premiere_clip_place` imports a file that is not in the project, puts the item's source in and out back
  after placing and reports each clip where it landed. `premiere_clip_copy` places the clip's own project
  item, so a file imported twice is copied from the item the clip uses.
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
  the clip and moves the later clips of every unlocked track left by its length; when a clip that stays on a
  track would be overlapped by the moved ones, the remove is refused before anything changes. `trim_start` and
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
- `premiere_scene_detect` `engine` `ffmpeg` reads the clip's source with ffmpeg. A clip of three 1 s colors
  placed at 8 s reported cuts at 9.0 and 10.0, and `cuts` split it there.
- `engine` `premiere` runs `sequence.performSceneEditDetectionOnSelection(action)`, whose only argument is
  `clipOperation` (`ApplyCuts` or `CreateMarkers`). It acts on the selected clips, returns true whatever it
  did, and detects nothing on a clip of three flat 1 s colors; on a 3 s H.264 clip of three 1 s test
  patterns it found the cuts at 1 s and 2 s. `ApplyCuts` splits the clip and its linked audio at once
  (3 video and 3 audio clips). `CreateMarkers` adds Segmentation markers with an empty name to the clip's
  project item (`getMarkers()`) at 1 s and 2 s, not to the sequence, and only after the call returns, so
  the selection must stay until they exist.
- `app.project.getAllLumetriPresetsList()` returns the 325 look names as an array of strings, with
  duplicates across camera families; `applyLumetriPreset(name)` takes one string, acts on the selected
  clips, returns true and appends a new Lumetri Color component to each, so a second look stacks a second
  component. `getLumetriPresetsForFolderList` takes one argument.
- `app.project.importAllAEComps(aepPath, bin)` and `importAEComps(aepPath, compNames, bin)` import each
  composition as a project item named `<comp>/<project>.aep` whose media path is the `.aep`. Importing
  all of one project gave 8 items (`Main B` twice); an unknown composition name imports nothing and
  raises no error. An import starts an `aerendercore` process under Dynamic Link.
- `premiere_tracks` adds stereo audio tracks and appends them after the last track.
- `premiere_frame_export` writes `<folder>/<prefix>_<n>_<time>s.png` and checks each file and its PNG
  header on disk; a time at or past the sequence end is refused.
