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

## 3. Get the clips

Any clips with distinct file names work. This walk-through uses the three shots and the score in
`examples/first-cut/media` of the repository: `aisle.mp4`, `circuit.mp4` and `cubes.mp4` (3.75 seconds
each, 1280 by 720 at 24 fps) and `score.wav` (9 seconds). Copy them to `/work`.

## 4. Cut them

Call `premiere_cut`:

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

It returned:

```json
{"fps": "24", "frames": 216, "cut_frames": 216,
 "transitions": ["clip 2: Cross Dissolve 12f", "clip 3: Cross Dissolve 12f"], "warnings": []}
```

`frames` is the frame count `ffprobe` read from the exported master, 9 seconds at the first clip's 24
fps. `cut_frames` is the end of the last clip; it matches because the score and the clips both end at 9
seconds. The second and third clips start their source at 0.5 seconds, which leaves the handles each
centered dissolve needs.

## 5. Look at the result

Open the project with `premiere_project` (`action` `open`, `path` the `.prproj`), then call
`premiere_frame_export` with `times` `[1.5, 3, 4.5, 7.5]` and a `folder`. It writes four 1280 by 720
PNGs: the aisle, the aisle dissolving into the circuit board, the circuit board and the glass cubes.

[Make a first edit](../guides/first-edit.md) builds the same kind of result clip by clip.
