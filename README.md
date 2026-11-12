# Premiere MCP

MCP server for Adobe Premiere Pro on macOS. It runs ExtendScript in Premiere through a Photoshop
BridgeTalk relay, and cuts a clip list into a new project with transitions and a ProRes 422 HQ
master.

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

Paths are absolute. Photoshop and Premiere Pro are opened in the background (`open -g -a`) when
they are not running.

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

## Development

```sh
uv sync --dev
uv run ruff check .
uv run pytest
```
