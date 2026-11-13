# Set up the Bridge relay

Premiere Pro reaches the server through a startup script that runs in Adobe Bridge. Bridge approves a
startup script by its content, once, in its own settings. This guide does that setup.

## 1. Install the script

Call `premiere_bridge_install`. It needs Adobe Bridge installed and started at least once (Bridge
creates its user folder on first start). It copies `cavi-bridge-relay.jsx` into
`~/Library/Application Support/Adobe/Bridge <year>/Startup Scripts/` and returns `matches: true` when the
installed copy is the packaged one.

## 2. Restart Bridge and approve the script

1. Quit Adobe Bridge from its menu if it is running, and start it again.
2. Open Bridge **Settings > Startup Scripts**.
3. Approve `cavi-bridge-relay`.

Until the script is approved, any tool that reaches Premiere Pro fails with this message:

```text
Adobe Bridge has not run the cavi-bridge-relay startup script: approve it in Bridge Settings > Startup Scripts, or run premiere_bridge_install
```

The approval is tied to the script's content. Running `premiere_bridge_install` again after a package
upgrade can change the installed copy, and Bridge then asks for approval again. `premiere_status`
shows `relay`: `yes` for a copy that matches the packaged one, `differs` for an older copy and `no`
when none is installed.

## 3. Check it

Call `premiere_inspect` or any other tool that reaches Premiere Pro. When Bridge or Premiere Pro is not
running, the server starts it in the background (`open -g -a`), then waits. A Premiere Pro that is
still starting refuses messages for a while; a freshly started one can need about 90 seconds before
the relay answers, and the relay keeps asking for up to 300 seconds. A Bridge that is still loading
its startup scripts is waited for as well.

## How the relay works

The server writes `<id>.job` into `~/Library/Application Support/cavi-bridge-relay/`. The first line
names the BridgeTalk target and the script follows. The relay polls the folder every 200 ms, sends the
script to the target application and writes `<id>.reply`: `ok` or `error`, then the result. The
relay does not know about Premiere Pro; the target is a parameter. Mailbox files older than a day are
removed.

Headless After Effects (`-noui`) has no BridgeTalk and cannot serve as the relay.

## Quitting

Premiere Pro and Bridge turn a termination signal into an abort and write a crash report. Quit them
from the application, never with `kill`. Close projects through `premiere_project` first when you do
not want to save them.
