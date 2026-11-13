# Export and encode

Four tools write files from a sequence: `premiere_export` (through Premiere Pro),
`premiere_encode` (through Adobe Media Encoder), `premiere_frame_export` (PNG stills) and
`premiere_interchange` (FCP XML, AAF, OMF). All of them take an absolute output path and refuse an existing
file unless `replace` is true.

## Choose a preset

`premiere_presets` lists export presets (`.epr`, from Premiere Pro, Media Encoder and your user
folders) and sequence presets (`.sqpreset`) as `name`, `format`, `source` and `path`. A preset is given as
an absolute path or by name. A name that several formats use is written `format/name`, for example:

```text
H264/00 - Match Source - High bitrate
```

User presets win over system presets of the same name. `premiere_export` and `premiere_encode`
default to the system `Apple ProRes 422 HQ` preset when `preset` is empty.

## Export with Premiere Pro

```json
{"master": "/work/edit/edit.mov"}
```

`range` is `entire` (the default), `in_out` (the sequence's in and out points; set them with
`premiere_sequence_set`) or `work_area`. The work area cannot be changed from a script, so `work_area` is
the whole sequence unless it was set in the Premiere Pro window.

A real run with `range` `in_out` after setting the in point to 1 and the out point to 3 on a 25 fps
sequence, and the H.264 preset above:

```json
{"master": "/work/edit/edit.mp4", "preset": "H264/00 - Match Source - High bitrate", "range": "in_out"}
```

The result had `frames` 50, `expected_frames` 50 and `complete` true. `ffprobe` reads the file as H.264
video with AAC audio.

`complete` is true when the frame count that `ffprobe` read from the file equals the length of the
range. The export is judged by the report file, by no process holding the output open and by that
frame count, not by the relay's answer: the relay can answer `timed out` while Premiere Pro keeps
exporting.

`burn_captions` true or false exports from a copy of the preset, written to a temporary folder, with its
captions setting changed. An H.264 preset then burns the caption into the picture (white text at the
bottom of the frame); a ProRes preset has no effect.

## Encode in Media Encoder

`premiere_encode` takes the same `master`, `preset`, `range` and `replace`. It starts Media Encoder when it
is not running, waits for it, queues the sequence and starts the batch. Premiere Pro stays free
while the file renders. The call returns when the output exists, no process holds it open and
`ffprobe` finds the expected frames.

## Stills

```json
{"times": [1, 2.24, 4], "folder": "/work/cut/frames", "prefix": "cut"}
```

`premiere_frame_export` writes `<folder>/<prefix>_<n>_<time>s.png`, checks each file and its PNG
header on disk and returns each still's `time`, `path`, `width` and `height`. A time at or past the
sequence end is refused, and so is a `prefix` that contains a path. Times 1, 2.24 and 4 with this prefix on
the quickstart's cut produced `cut_001_1.000s.png`, `cut_002_2.240s.png` and `cut_003_4.000s.png`, each
1280 by 720.

## Interchange

`premiere_interchange` with `action` `xml`, `aaf` or `omf` exports the sequence; `import_xml` adds an FCP
XML's sequence to the project (it keeps its name, so it can share one with the original). OMF also
writes `<name>omfLog.txt` beside the file. `audio_rate` and `bits` apply to AAF and OMF.
