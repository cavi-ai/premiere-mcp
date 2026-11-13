# Changelog

Versions come from git tags; a pull request adds its lines under Unreleased and never edits a version.

## Unreleased

### Added

- `CAVI_PREMIERE_APP`, `CAVI_BRIDGE_APP` and `CAVI_MEDIA_ENCODER_APP` choose the application bundle.
- `premiere_status` reports Media Encoder and any application that is not installed.
- LICENSE, CONTRIBUTING, SECURITY, a release workflow and package metadata.

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
- Stale mailbox files are removed.
