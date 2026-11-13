# Version and support

This documentation is for `cavi-premiere-mcp` {{PRODUCT_VERSION}}, released as
`{{RELEASE_TAG}}` from commit `{{RELEASE_COMMIT}}`.

Versions come from git tags: `vX.Y.Z` builds `X.Y.Z`. Before 1.0, the tool surface, parameters and result
fields can still change. Every change is recorded in the repository
[CHANGELOG.md](https://github.com/cavi-ai/premiere-mcp/blob/main/CHANGELOG.md). Until 1.0, security fixes
go to the latest minor release and `main`.

## Checked applications

- Premiere Pro 26.5.2, Adobe Bridge 16.0.8 and Media Encoder 26.5.2 on macOS: the tools were run against
  these versions.
- The requirement is Premiere Pro 2026 or later and Adobe Bridge 2026 or later.

## Package requirements

- Python 3.15 or later.
- FFmpeg (`ffprobe`, and `ffmpeg` for `premiere_scene_detect`).
- The only supported platform is macOS.

## License and trademarks

MIT licensed.

Adobe, Premiere Pro, After Effects, Adobe Bridge and Media Encoder are either registered trademarks or
trademarks of Adobe in the United States and/or other countries. This project is not affiliated with,
endorsed by, or sponsored by Adobe. It does not include or redistribute Adobe software, templates or
presets; you supply your own licensed applications.
