# Installation

## Requirements

- macOS.
- Adobe Premiere Pro 2026 or later and Adobe Bridge 2026 or later (Bridge runs the script relay).
  Adobe Media Encoder is needed only for `premiere_encode`.
- FFmpeg (`ffprobe`, and `ffmpeg` for `premiere_scene_detect`) on `PATH`.
- Python 3.15 or later and [uv](https://docs.astral.sh/uv/).

The package does not include or supply Adobe software or licenses. It does not sign in to Adobe
accounts.

## Install the server

```sh
uv tool install cavi-premiere-mcp
```

Upgrade with `uv tool upgrade cavi-premiere-mcp`. To work from a checkout instead, see
[CONTRIBUTING.md](https://github.com/cavi-ai/premiere-mcp/blob/main/CONTRIBUTING.md).

## Register it with your MCP client

```json
{"mcpServers": {"premiere": {"command": "cavi-premiere-mcp"}}}
```

A desktop client that does not inherit your shell's `PATH` needs the absolute path that
`command -v cavi-premiere-mcp` prints.

## Install and approve the relay

The relay script is installed by the `premiere_bridge_install` tool and approved once in Adobe Bridge.
The steps are in [Set up the Bridge relay](../guides/bridge-setup.md).

## Application bundles

Without an override the newest installed version under `/Applications` is used. To choose another
bundle, see [Configuration](../reference/configuration.md).
