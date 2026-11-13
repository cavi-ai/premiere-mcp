# Contributing

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

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

The documentation tests build and verify `docs/premiere-mcp/source` and fail when the README or
`reference/tools.md` and the registered tools, parameters, defaults or results differ. Change the
documentation in the same pull request as a tool.

The MCP Eval checks need Node.js and the MCP Eval executable (`npm install`, or `MCPEVAL_EXECUTABLE` set to a
build of [cavi-ai/mcp-eval](https://github.com/cavi-ai/mcp-eval)):

```bash
npm install
npm run eval:protocol
npm run eval:core
```

A change to a script under `src/cavi_premiere_mcp/jsx` is also tried in Premiere Pro. A new tool module
imports `mcp` from `app.py`, and `server.py` imports the module. `bridge_relay.jsx` is approved in Bridge by
its content, so any change to it needs a new approval.

Add a line under Unreleased in `CHANGELOG.md`. Versions come from git tags and are never edited in a pull request.
