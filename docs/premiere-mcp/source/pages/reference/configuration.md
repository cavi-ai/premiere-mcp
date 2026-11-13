# Configuration

## Environment variables

| Variable | Meaning |
|---|---|
| `CAVI_PREMIERE_APP` | The Premiere Pro `.app` to use. |
| `CAVI_BRIDGE_APP` | The Adobe Bridge `.app` to use. |
| `CAVI_MEDIA_ENCODER_APP` | The Media Encoder `.app` to use. |

Without an override the newest installed version under `/Applications` is used. An override that
names another application is refused. Set a variable in the `env` object of the server's entry in
your MCP client configuration:

```json
{"mcpServers": {"premiere": {"command": "cavi-premiere-mcp",
  "env": {"CAVI_PREMIERE_APP": "/Applications/Adobe Premiere Pro 2026/Adobe Premiere Pro 2026.app"}}}}
```

## Files the server uses

| Path | Use |
|---|---|
| `~/Library/Application Support/cavi-bridge-relay/` | Mailbox for job and reply files; files older than a day are removed. |
| `~/Library/Application Support/Adobe/Bridge <year>/Startup Scripts/cavi-bridge-relay.jsx` | The relay, written by `premiere_bridge_install`. |

A call that needs a temporary file, such as the script it sends or an export preset copy for
`burn_captions`, uses a temporary folder for the duration of the call.

## Limits

- `timeout` on a tool is 30 to 7200 seconds; each tool's default is in the
  [tools reference](tools.md#tool-index).
- At most 5000 markers per call, and a beat grid that would add more is refused.
- At most 50 stills per `premiere_frame_export` call.
- The server waits up to 300 seconds for Premiere Pro to answer after it starts.
- Paths are absolute, numbers are finite, and a still `prefix` is a plain file-name start.
