# Contributing

## Setup

Install Python 3.15 or newer and [uv](https://docs.astral.sh/uv/), then:

```bash
git clone https://github.com/cavi-ai/premiere-mcp.git
cd premiere-mcp
uv sync --locked --dev
```

No Adobe application is required for the unit tests. Tests that need FFmpeg or Node.js skip without them.

## Checks

```bash
uv run --locked ruff check .
uv run --locked pytest -q
```

A change to a script under `src/cavi_premiere_mcp/jsx` is also tried in Premiere Pro. A new tool module
imports `mcp` from `app.py`, and `server.py` imports the module. `bridge_relay.jsx` is approved in Bridge by
its content, so any change to it needs a new approval.

Add a line under Unreleased in `CHANGELOG.md`. Versions come from git tags and are never edited in a pull request.
