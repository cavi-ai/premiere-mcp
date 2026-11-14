# Changelog

Versions come from git tags; a pull request adds its lines under Unreleased and never edits a version.

## Unreleased

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
- `premiere_clip_place` failed after placing the clip because its result had no `media_path`.
- Stale mailbox files are removed.
