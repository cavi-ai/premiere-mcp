# Changelog

Versions come from git tags; a pull request adds its lines under Unreleased and never edits a version.

## Unreleased

### Added

- `premiere_clips_place` places many project items on one sequence in one job; a missing track or item places nothing.
- `premiere_sequence_open` makes a sequence the active one.
- `sequence` takes a sequence's id as well as its name; project items take their id as well as a media path or name.
- `premiere_inspect` returns each item's `id` and each sequence's `active`, and takes `items` and `tracks` to leave those parts out.

### Changed

- A sequence name or an item reference that several sequences or items answer to is refused with their ids instead of taking the first.

### Fixed

- `premiere_razor`, `premiere_range_remove`, `premiere_clip_speed` and `premiere_frame_export` address the frame at the sequence's exact rate on 23.976, 29.97 and 59.94 fps sequences, in drop-frame timecode on a drop-frame sequence.
- `premiere_inspect` durations of 23.976, 29.97 and 59.94 fps media count the timecode's frames, drop frame included.
- `premiere_sequence_set` sets a frame rate such as 12.5 exactly; a rate within 0.01 of n×1000/1001, such as 29.97, becomes that NTSC rate.
- `premiere_cut` rounds a time half a frame from the grid up, as the scripts do.
- `premiere_cut` closes only a project open at its own path; other open projects stay open.
- `premiere_clip_copy` and `premiere_fade` without `sequence` act on the active sequence, not the project's first.
- `premiere_cut`, `premiere_export` and `premiere_encode` with `replace` keep the old files when the ProRes preset, `ffprobe` or Media Encoder is missing.
- `premiere_export` and `premiere_encode` count a master whose container keeps no frame count by its packets, and a master without video by its audio duration; a master that cannot be counted is reported `OUTCOME_UNKNOWN`.

## 0.1.1 - 2026-11-16

### Changed

- No longer depends on `cavi-adobe-mcp`.

## 0.1.0 - 2026-11-14

### Added

- `CAVI_PREMIERE_APP`, `CAVI_BRIDGE_APP` and `CAVI_MEDIA_ENCODER_APP` choose the application bundle.
- `premiere_status` reports Media Encoder and any application that is not installed.
- LICENSE, CONTRIBUTING, SECURITY, a release workflow and package metadata.
- Documentation source under `docs/premiere-mcp/source` (introduction, guides, tools reference, security, release), built and verified by `scripts/docs`, and attached to each release.
- A test that fails when the README or the tools reference and the registered tools, parameters, defaults or results differ.
- `evals/` with MCP Eval protocol and core checks, a first-cut example under `examples/`, a Code of Conduct, issue and pull request templates.

### Changed

- Depends on `cavi-adobe-mcp` and `cavi-mcp-core` by version range; applications are found through `cavi-mcp-core`.
- Tools live in `tools.py`, models in `models.py` and the server object in `app.py`.
- The cut script uses the shared report writer.
- A script that throws, an unreadable report and a job that cannot start are tool errors raised at once.

### Fixed

- `premiere_project` open and new without a path name the missing argument.
- Opening a project with missing media no longer shows a Link Media dialog that blocks Premiere.
- `premiere_razor` refuses a missing track or a time outside the sequence; `premiere_clip_speed` refuses a clip shorter than a frame; `premiere_clip_edit` refuses a locked target track before removing the clip.
- Non-finite numbers, oversized marker lists and file prefixes with a path are refused before Premiere is called.
- `premiere_scene_detect` reports a missing sequence, track or clip, and an unreadable movie, instead of failing with an index error or an empty result.
- A Bridge that is still starting is waited for instead of reported as an unapproved relay.
- `premiere_export` and `premiere_encode` refuse an existing master before looking up the default preset.
- `premiere_presets` lists Media Encoder and user presets when Premiere Pro is not installed.
- `premiere_clip_place` failed after placing the clip because its result had no `media_path`.
- Stale mailbox files are removed.
