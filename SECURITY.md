# Security Policy

## Reporting a vulnerability

Report vulnerabilities privately through GitHub's private vulnerability reporting:
<https://github.com/cavi-ai/premiere-mcp/security/advisories/new>. Do not open a public issue.
Include affected versions, reproduction steps and impact. Do not include Adobe account details or project files.

## Supported versions

Until 1.0, security fixes go to the latest minor release and `main`.

## Scope

- `premiere_script` runs a caller-chosen `.jsx` file in Premiere with the user's permissions. Connect it only to
  clients you trust.
- Scripts reach Premiere through a Bridge startup script that reads job files from
  `~/Library/Application Support/cavi-bridge-relay/`. Any local process that can write there can run
  ExtendScript in Adobe applications; the folder belongs to the user.
- The server speaks MCP over stdio, sends no telemetry and uses no accounts.
- Adobe applications and their licenses are out of scope; report those to Adobe.
