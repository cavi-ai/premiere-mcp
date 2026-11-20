# Overview

Premiere MCP is a Model Context Protocol server for Adobe Premiere Pro on macOS. It gives an MCP
client typed tools to inspect and edit a Premiere Pro project, and one tool that cuts a clip list into
a new project with transitions and a ProRes 422 HQ master.

The server speaks MCP over stdio, runs on your machine and needs a Premiere Pro installation that you
license yourself. It sends no telemetry and uses no accounts.

## What it can do

- Open, create, save and close projects; import media and After Effects compositions into bins; create
  bars and tone, black video and transparent video; organize project items and bins.
- Create and change sequences and tracks; place, trim, move, split, copy, slip and speed-change clips.
- Add transitions, effects, fades, Lumetri Color corrections and looks, markers, captions and Motion
  Graphics templates; set any component parameter, static or keyframed.
- Transcribe a clip's dialogue into timeline words and captions, find silences and hard cuts (with
  ffmpeg or Premiere's own detection), cut time ranges out, close gaps, make Auto Reframe sequences.
- Export a sequence with any export preset, queue it in Media Encoder, export PNG stills, measure a
  master's loudness against a delivery target, and exchange sequences as FCP XML, AAF or OMF.
- Run your own ExtendScript file in Premiere Pro.

The [tools reference](../reference/tools.md) lists all 47 tools with their parameters and results.

## How it works

Premiere Pro has no external scripting interface that a program can call directly, and Adobe Bridge has
no AppleScript dictionary. The server therefore uses a small relay script that runs inside Adobe
Bridge:

1. The server writes a job file into a mailbox folder under `~/Library/Application Support`.
2. The relay, running in Bridge, picks the job up and sends the script to Premiere Pro over
   BridgeTalk.
3. The script runs in Premiere Pro and writes a JSON report; the relay writes the reply.
4. The server reads the report, checks it against the tool's result type and returns it.

Every tool is one script in `src/cavi_premiere_mcp/jsx`. Bridge must have the relay enabled once; see
[Set up the Bridge relay](../guides/bridge-setup.md).

Exports and cuts are not judged by the relay's answer alone. The server also checks the report file,
that no process still holds the output open and the frame count that `ffprobe` reads from the file.

## What was checked

The tools were run against Premiere Pro 26.5.2 and 27.0.0, Adobe Bridge 16.0.8 and 17.0.0, and Media
Encoder 26.5.2 and 27.0.0 on macOS. Behavior that was measured rather than documented by Adobe is recorded in
[Premiere Pro behavior](../reference/premiere-behavior.md).

## Next

[Install](installation.md) the server, then follow the [quickstart](quickstart.md).
