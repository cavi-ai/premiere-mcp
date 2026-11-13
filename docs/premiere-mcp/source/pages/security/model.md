# Security model

## What the server can do

The server speaks MCP over stdio, opens no network port, sends no telemetry and uses no accounts. It acts
with the permissions of the user who runs it, on that user's Premiere Pro, and exposes the operations in
the [tools reference](../reference/tools.md). Connect it only to MCP clients you trust.

## Running scripts

`premiere_script` runs a caller-chosen `.jsx` file in Premiere Pro. ExtendScript in Premiere Pro can read
and write files and change any open project, so a client that can call this tool can do what you can do in
Premiere Pro. The other tools run only the scripts that ship in the package.

## The relay mailbox

Scripts reach Premiere Pro through a Bridge startup script that reads job files from
`~/Library/Application Support/cavi-bridge-relay/`. Any local process that can write there can run
ExtendScript in Adobe applications, so the folder belongs to the user and must not be shared or made
writable by others.

Adobe Bridge approves the relay by its content, once. The package never changes Bridge's settings; it only
copies the script into the Startup Scripts folder when you call `premiere_bridge_install`, and you approve
it in Bridge yourself.

## Inputs

Inputs are checked before Premiere Pro is touched: absolute paths, finite numbers, at most 5000 markers
per call and a plain file-name `prefix` for stills. Calls that write a file refuse an existing file
unless `replace` is true.

## No background activity

There are no uploads or scheduled work. The server starts Premiere Pro, Adobe Bridge
and Media Encoder in the background when a call needs them, and leaves them running. It does not install
Adobe software, sign in, accept terms or dismiss license prompts.

## Reporting a vulnerability

Report vulnerabilities privately as described in `SECURITY.md` in the repository. Adobe applications and
their licenses are out of scope; report those to Adobe.
