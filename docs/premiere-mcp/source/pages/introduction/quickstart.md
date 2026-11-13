# Quickstart

This walk-through checks the connection and then cuts two clips into a new project with a
dissolve. It assumes the server is [installed](installation.md) and registered, and the relay is
[set up](../guides/bridge-setup.md). The results below are from a real run on Premiere Pro 26.5.2;
folder paths are shortened to `/work`.

## 1. Check the machine

Call `premiere_status`. It starts nothing. It returns, for Premiere Pro, Adobe Bridge and Media Encoder,
the installed bundle, its version and any process ids, plus `relay` (`yes` when the installed relay
script matches the packaged one, `differs` when it does not, `no` when none is installed), the `mailbox`
folder and the `prores_preset` path.

## 2. Install the relay

Call `premiere_bridge_install`. It copies the relay into Bridge's Startup Scripts folder:

```json
{"path": "~/Library/Application Support/Adobe/Bridge 2026/Startup Scripts/cavi-bridge-relay.jsx",
 "matches": true,
 "next": "Restart Adobe Bridge, then approve cavi-bridge-relay in Bridge Settings > Startup Scripts once"}
```

Do the restart and approval once; after that this step is only needed to update the relay.

## 3. Make two clips

Any two clips with distinct file names work. These two come from FFmpeg:

```sh
ffmpeg -y -f lavfi -i "testsrc2=size=1280x720:rate=25:duration=3" -c:v libx264 -pix_fmt yuv420p -g 25 /work/pattern.mp4
ffmpeg -y -f lavfi -i "smptebars=size=1280x720:rate=25:duration=3" -c:v libx264 -pix_fmt yuv420p -g 25 /work/bars.mp4
ffmpeg -y -f lavfi -i "sine=frequency=220:duration=5" -c:a pcm_s16le -ar 48000 /work/score.wav
```

## 4. Cut them

Call `premiere_cut`:

```json
{
  "project": "/work/cut/cut.prproj",
  "master": "/work/cut/master.mov",
  "audio": "/work/score.wav",
  "clips": [
    {"file": "/work/pattern.mp4", "start": 0, "in_point": 0, "out_point": 2},
    {"file": "/work/bars.mp4", "start": 2, "in_point": 0.5, "out_point": 3,
     "transition": {"kind": "cross_dissolve", "frames": 12}}
  ]
}
```

The call returned after about 25 seconds:

```json
{"fps": "25", "frames": 125, "cut_frames": 113, "transitions": ["clip 2: Cross Dissolve 12f"], "warnings": []}
```

`frames` is the frame count `ffprobe` read from the exported master (the 5 second score sets the
length). `cut_frames` is the end of the last clip, 4.52 seconds. The second clip's source in point is
0.48 because 0.5 seconds is between frames at 25 fps and cut times are snapped to the frame grid.

## 5. Look at the result

Open the project with `premiere_project` (`action` `open`, `path` the `.prproj`), then call
`premiere_frame_export` with `times` `[2]`, a `folder` and a `prefix`. The still it writes (1280 by 720)
shows the dissolve between the two clips.

[Make a first edit](../guides/first-edit.md) builds the same kind of result clip by clip.
