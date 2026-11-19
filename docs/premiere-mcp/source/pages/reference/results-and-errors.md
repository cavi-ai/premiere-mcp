# Results and errors

Every tool returns the result and error shapes of the
[MCP Core contract](https://github.com/cavi-ai/mcp-core/blob/main/docs/mcp-core/source/pages/reference/results-and-errors.md):
structured content that matches the tool's output schema, with optional fields the tool did not set left
out, and on failure an `error` with `code`, `outcome` and `next_action`. This page lists what this server
adds. The fields of each tool are in the [tools reference](tools.md). Times are seconds and paths are
absolute.

`premiere_script` returns the script's last value as `answer` and, when `report` names a `.json` path,
the JSON the script wrote as `report`.

## Codes

| `code` | `outcome` | When |
|---|---|---|
| `RELAY_NOT_APPROVED` | `rejected` | Adobe Bridge has not run the relay startup script. Approve it in Bridge Settings > Startup Scripts, or run `premiere_bridge_install`. |
| `PREMIERE_NOT_READY` | `rejected` | Premiere Pro did not answer the relay within 300 s, so no job was sent. |

Each has `next_action` `inspect_inputs`. A file the call reads that does not exist is `INPUT_NOT_FOUND`. An
argument the chosen action does not read, such as `path` for `premiere_project` `save` or `bits` for
`premiere_interchange` `xml`, is refused as `INVALID_ARGUMENT` before Premiere Pro is called.

## Recovery

An `unknown` outcome means the project may have changed: a script that threw, a report that could not be
read, a job that could not start. Read the project with `premiere_inspect` and check the output files
before you call again. A script that throws, an unreadable report and a job that cannot start are reported
at once; the server does not wait out the timeout.
