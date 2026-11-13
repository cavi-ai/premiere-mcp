# Cavi Premiere MCP

[![PyPI version](https://img.shields.io/pypi/v/cavi-premiere-mcp)](https://pypi.org/project/cavi-premiere-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

MCP server for Adobe Premiere Pro on macOS. It runs ExtendScript in Premiere Pro through an Adobe Bridge
BridgeTalk relay, exposes the common Premiere Pro operations as 42 typed tools, and cuts a clip list into
a new project with transitions and a ProRes 422 HQ master.

## Try one cut

Cut two clips and a score into a new project with a 12-frame cross dissolve, and export the master. The
stills below were exported by Premiere Pro from that project at 1, 2 and 4 seconds.

![Three stills from the cut: a color test pattern, the pattern dissolving into color bars, and color bars](examples/first-cut/cut-frames.png)

The request is [cut.json](examples/first-cut/cut.json) and the measured answer is
[results.json](examples/first-cut/results.json): a ProRes 422 HQ master, 1280 by 720 at 25 fps, with 125
frames counted by `ffprobe`. [Reproduce the cut](examples/first-cut/README.md); it needs only FFmpeg and
the generated inputs.

## Install

Requires macOS, Premiere Pro 2026 or later, Adobe Bridge 2026 or later (the script relay), FFmpeg
(`ffprobe`) and Python 3.15 or later with [uv](https://docs.astral.sh/uv/). You supply your own licensed Adobe
applications.

```sh
uv tool install cavi-premiere-mcp
```

Upgrade with `uv tool upgrade cavi-premiere-mcp`. To work from a checkout instead, see
[CONTRIBUTING.md](CONTRIBUTING.md).

Install the relay script into Bridge and approve it once in Bridge **Settings > Startup Scripts**; the
steps are in [Set up the Bridge relay](docs/premiere-mcp/source/pages/guides/bridge-setup.md).

## Quickstart

Register the stdio server with your MCP client:

```json
{"mcpServers": {"premiere": {"command": "cavi-premiere-mcp"}}}
```

If your client does not inherit your shell's `PATH`, use the absolute path that
`command -v cavi-premiere-mcp` prints. Then ask your agent to:

1. Call `premiere_status` to see the installed applications and the relay state.
2. Call `premiere_bridge_install`, restart Bridge and approve the relay, once.
3. Call `premiere_cut` with the request from [cut.json](examples/first-cut/cut.json), then
   `premiere_inspect` to read the new project back.

The [quickstart](docs/premiere-mcp/source/pages/introduction/quickstart.md) shows each step with its result.
Paths are absolute, times are seconds, tracks are 0-based, and `sequence` defaults to the active sequence.

## What it does

| Tool | What it does |
|---|---|
| `premiere_status` | Installed Premiere Pro, Adobe Bridge and Media Encoder, relay state and mailbox. |
| `premiere_bridge_install` | Copies the relay startup script into Adobe Bridge. |
| `premiere_script` | Runs a `.jsx` file in Premiere Pro. |
| `premiere_cut` | Cuts a clip list into a new project and exports a ProRes 422 HQ master. |
| `premiere_project` | Opens, creates, saves or closes a project. |
| `premiere_inspect` | Bins, project items, sequences, tracks, clips, transitions and markers. |
| `premiere_transitions` | Lists the video and audio transitions Premiere offers. |
| `premiere_presets` | Lists export and sequence presets. |
| `premiere_effects` | Lists the video and audio effects Premiere offers. |
| `premiere_find` | Finds project items and placed clips by name or path. |
| `premiere_import` | Imports files into a bin. |
| `premiere_items` | Renames, moves, labels, subclips, interprets, proxies or deletes a project item. |
| `premiere_bins` | Creates, renames, deletes bins and moves items into them. |
| `premiere_media_replace` | Points a project item at a new file or refreshes it. |
| `premiere_sequence_new` | Creates an empty sequence. |
| `premiere_sequence_set` | Changes settings, in/out points, nests, duplicates, renames or deletes a sequence. |
| `premiere_tracks` | Adds tracks and sets mute, lock and target state. |
| `premiere_clip_place` | Places a project item on a track. |
| `premiere_clip_edit` | Trims, moves, enables, renames, links or removes a placed clip. |
| `premiere_clip_copy` | Places another copy of a clip. |
| `premiere_clip_slip` | Shows a different part of a clip's source in the same place. |
| `premiere_clip_speed` | Sets a clip's speed or the duration it fills. |
| `premiere_clip_fit` | Scales a clip to fit or fill the frame. |
| `premiere_clip_props` | Sets Motion, Opacity and Volume, static or keyframed. |
| `premiere_fade` | Fades a clip in and out. |
| `premiere_color` | Basic Lumetri Color correction. |
| `premiere_effect_add` | Adds an effect to a clip. |
| `premiere_effect_set` | Sets or lists component parameters. |
| `premiere_transition_add` | Adds a transition to a clip edge. |
| `premiere_razor` | Splits clips at times. |
| `premiere_gaps` | Lists or closes empty gaps. |
| `premiere_range_remove` | Cuts a time range out of every unlocked track. |
| `premiere_scene_detect` | Finds hard cuts in a clip's media and optionally splits or marks them. |
| `premiere_markers_add` | Adds sequence markers or a beat grid. |
| `premiere_markers_edit` | Lists, updates or deletes sequence markers. |
| `premiere_mogrt_add` | Places a Motion Graphics template and sets its text. |
| `premiere_captions` | Imports an `.srt` as a caption track. |
| `premiere_auto_reframe` | Makes a new sequence at another aspect ratio. |
| `premiere_frame_export` | Exports PNG stills of a sequence. |
| `premiere_export` | Exports a sequence with a preset. |
| `premiere_encode` | Queues a sequence in Media Encoder. |
| `premiere_interchange` | Exports FCP XML, AAF or OMF, or imports an FCP XML. |

Every tool is a script in `src/cavi_premiere_mcp/jsx` run through the relay with `CAVI_ARGS`, and answers
the JSON report the script writes. The [tools reference](docs/premiere-mcp/source/pages/reference/tools.md)
has each tool's parameters, defaults and results.

## Documentation

The documentation source is in `docs/premiere-mcp/source`:

- [Overview](docs/premiere-mcp/source/pages/introduction/overview.md),
  [installation](docs/premiere-mcp/source/pages/introduction/installation.md) and
  [quickstart](docs/premiere-mcp/source/pages/introduction/quickstart.md)
- Guides: [Bridge relay setup](docs/premiere-mcp/source/pages/guides/bridge-setup.md),
  [a first edit](docs/premiere-mcp/source/pages/guides/first-edit.md),
  [cutting from a clip list](docs/premiere-mcp/source/pages/guides/cut-from-clip-list.md),
  [export and encode](docs/premiere-mcp/source/pages/guides/exports.md) and
  [troubleshooting](docs/premiere-mcp/source/pages/guides/troubleshooting.md)
- Reference: [tools](docs/premiere-mcp/source/pages/reference/tools.md),
  [results and errors](docs/premiere-mcp/source/pages/reference/results-and-errors.md),
  [configuration](docs/premiere-mcp/source/pages/reference/configuration.md) and
  [Premiere Pro behavior](docs/premiere-mcp/source/pages/reference/premiere-behavior.md)
- [Security model](docs/premiere-mcp/source/pages/security/model.md) and
  [version and support](docs/premiere-mcp/source/pages/release/version-and-support.md)

## Configuration

| Variable | Meaning |
|---|---|
| `CAVI_PREMIERE_APP` | The Premiere Pro `.app` to use. |
| `CAVI_BRIDGE_APP` | The Adobe Bridge `.app` to use. |
| `CAVI_MEDIA_ENCODER_APP` | The Media Encoder `.app` to use. |

Without an override the newest installed version under `/Applications` is used. An override that names
another application is refused.

## Security

The server speaks MCP over stdio, sends no telemetry and uses no accounts. `premiere_script` runs a
caller-chosen `.jsx` file in Premiere Pro, and any local process that can write the relay mailbox can run
ExtendScript in Adobe applications. See the
[security model](docs/premiere-mcp/source/pages/security/model.md) and [SECURITY.md](SECURITY.md).

## Tests

```sh
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked pytest -q
npm install
npm run eval:protocol
npm run eval:core
```

The unit tests need no Adobe application; tests that need FFmpeg or Node.js skip without them. The
tests also fail when the README or the tools reference and the registered tools differ. The two evals run
the server over stdio with MCP Eval: `eval:protocol` checks the MCP contract of the catalog, and
`eval:core` also plays the input checks that happen before Premiere Pro is touched. They use no Adobe
application, so they do not exercise the tools inside Premiere Pro.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, checks and the rules for changes. This project follows
the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).

## Trademarks

Adobe, Premiere Pro, After Effects, Adobe Bridge and Media Encoder are either registered trademarks or
trademarks of Adobe in the United States and/or other countries. This project is not affiliated with,
endorsed by, or sponsored by Adobe. It does not include or redistribute Adobe software, templates or
presets; you supply your own licensed applications.
