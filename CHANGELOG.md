# Changelog

Versions come from git tags; a pull request adds its lines under Unreleased and never edits a version.

## Unreleased

### Added

- `premiere_clip_place` takes `clips` to place many project items on one sequence in one job; an entry needs `item` and `at` and takes its other fields from the call; a missing track or item places nothing.
- `premiere_sequence_open` makes a sequence the active one.
- `sequence` takes a sequence's id as well as its name; project items take their id as well as a media path or name.
- `premiere_inspect` returns each item's `id` and each sequence's `active`, and takes `items` and `tracks` to leave those parts out.

### Changed

- A sequence name or an item reference that several sequences or items answer to is refused with their ids instead of taking the first.
- An argument the call does not use is refused: `premiere_project`, `premiere_interchange`, `premiere_markers_edit` and `premiere_bins` per action, `keep_linked` without `remove`, `include_audio` without `apply=cuts`, and `params` with `list=true`.
- `premiere_interchange` `audio_rate` and `bits` default to none; AAF and OMF use 48000 Hz and 16 bits when they are omitted.
- A missing input file is `INPUT_NOT_FOUND`; a relay Bridge never ran is `RELAY_NOT_APPROVED` and a Premiere Pro that never answered is `PREMIERE_NOT_READY`, both `rejected`.
- Results leave out optional fields the tool did not set. Requires cavi-mcp-core 0.1.7.

### Fixed

- Calls drive Premiere Pro one at a time across server processes, and a call that sends several jobs (`premiere_fade`, `premiere_clip_copy`, `premiere_color`, `premiere_scene_detect`, `premiere_media_replace`) holds Premiere Pro until its last job; another call waiting for its whole `timeout` is `PREMIERE_BUSY`.
- `timeout` bounds the whole call; an export could wait the timeout twice plus 330 s.
- The relay mailbox is set to mode `0700` before each job.
- `premiere_clip_edit` `remove` `ripple` is refused when the later clips of a track would move onto a clip that stays there; it used to overwrite that clip.
- `premiere_clip_props` static `opacity` and `volume_db` take the keyframe ranges, 0 to 100 and -96 to 15.
- `premiere_razor`, `premiere_range_remove`, `premiere_clip_speed` and `premiere_frame_export` address the frame at the sequence's exact rate on 23.976, 29.97 and 59.94 fps sequences, in drop-frame timecode on a drop-frame sequence.
- `premiere_inspect` durations of 23.976, 29.97 and 59.94 fps media count the timecode's frames, drop frame included.
- `premiere_sequence_set` sets a frame rate such as 12.5 exactly; a rate within 0.01 of n×1000/1001, such as 29.97, becomes that NTSC rate.
- `premiere_cut` rounds a time half a frame from the grid up, as the scripts do.
- `premiere_cut` closes only a project open at its own path; other open projects stay open.
- `premiere_clip_copy` and `premiere_fade` without `sequence` act on the active sequence, not the project's first.
- `premiere_clip_copy` places the clip's own project item, so a clip whose file is imported twice can be copied.
- `premiere_clip_place` reports a clip placed off the frame grid on the frame where it landed instead of failing after placing it.
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
