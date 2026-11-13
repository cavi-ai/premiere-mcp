# Troubleshooting

Start with `premiere_status`. It shows which applications are installed, their versions and process
ids, whether the relay script is installed and the mailbox folder.

## The relay is not approved

Tools that reach Premiere Pro fail with:

```text
Adobe Bridge has not run the cavi-bridge-relay startup script: approve it in Bridge Settings > Startup Scripts, or run premiere_bridge_install
```

Follow [Set up the Bridge relay](bridge-setup.md). `premiere_status` shows `relay` as `no` or `differs`
when the installed script is missing or not the packaged one.

## A tool waits a long time after Premiere Pro starts

A Premiere Pro that is still starting refuses BridgeTalk messages. A freshly started one needs about 90
seconds before the relay answers; the server keeps asking for up to 300 seconds. A Bridge that is
still loading its startup scripts is waited for as well.

## The relay answered `timed out`, but the export went on

The relay can time out while Premiere Pro keeps exporting. `premiere_export`, `premiere_encode` and
`premiere_cut` therefore judge the result by the report file, the output file with no process holding
it open and its `ffprobe` frame count, not by the relay's answer. Check the output file before you
repeat a long call; `complete` in the result says whether the frame count matched.

## Premiere Pro shows a dialog

A modal dialog in Premiere Pro blocks every later call. Projects are opened without conversion,
locate-file or warning dialogs, and a project with missing media opens with the media offline;
`premiere_find` with `offline_only` lists those items and `premiere_media_replace` relinks one. If a
dialog from another source is open, close it in the application.

## A source file changed but the picture did not

Premiere Pro keeps showing the old frames of a source movie that is overwritten on disk while its
project is open. Call `premiere_media_replace` for the item, with a new file name or with the same path
to refresh it.

## A tool is refused with a message

Inputs are checked before Premiere Pro is touched, and a refusal says what is wrong. Typical messages:

| Message | Meaning |
|---|---|
| `Use an absolute path: <path>` | A path was relative. |
| `Already exists (pass replace=true): <path>` | The output exists and `replace` is false. |
| `Give exactly one of at or position_index` | A clip address was missing or doubled. |
| `Give at least one change` | A call that changes something named no change. |
| `No <kind> preset named <name>; list them with premiere_presets` | The preset name is wrong. |
| `<name> names several presets; use format/name` | Several formats share the name. |
| `Install ffprobe (FFmpeg) to read frame rates, find scene cuts and verify masters` | FFmpeg is not on `PATH`. |

The full error shape is in [Results and errors](../reference/results-and-errors.md).

## The outcome is unknown

A failure that is not a refusal comes back with `outcome` `unknown`, `retry_safe` false and
`next_action` `inspect_application_and_outputs`. The tool may have changed the project. Look at the
project with `premiere_inspect` and at the output files before you call it again.

## Applications do not quit

Quit Premiere Pro and Adobe Bridge from the application, never with `kill`: a termination signal makes
them abort and write a crash report.

## Reporting a bug

Open an issue with the tool name and arguments, the error text, the `premiere_status` output and the
macOS, Premiere Pro and Bridge versions. Do not attach Adobe account details or project files.
