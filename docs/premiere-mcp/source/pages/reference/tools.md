# Tools

The server registers 42 tools. This page lists every tool with its parameters, defaults and result
fields. A test fails when a tool, a parameter, a default or a result field here differs from the
registered catalog.

All paths are absolute. Times are seconds. Tracks are 0-based (`track` 0 is V1 or A1). `sequence`
defaults to the active sequence, and `timeout` (30 to 7200 seconds) bounds the call; its default is
in the index. A tool that runs a script in Premiere Pro can also return `warnings`, a list of strings
for non-fatal findings, and `errors`, which is empty on success; the result lists below name
`warnings` where a tool returns it. For how failures are reported, see
[Results and errors](results-and-errors.md).

A clip is addressed by `kind` (`video` or `audio`), `track`, and either `at` (a timeline time inside
the clip or at its start) or `position_index` (its place on the track). Exactly one of the two is
required.

## Tool index

| Tool | Access | Timeout | What it does |
|---|---|---|---|
| `premiere_status` | read | none | Installed Premiere Pro, Adobe Bridge and Media Encoder, relay state and mailbox. |
| `premiere_bridge_install` | write | none | Copies the relay startup script into Adobe Bridge. |
| `premiere_script` | destructive | 1800 | Runs a `.jsx` file in Premiere Pro. |
| `premiere_cut` | destructive | 1800 | Cuts a clip list into a new project and exports a ProRes 422 HQ master. |
| `premiere_project` | destructive | 300 | Opens, creates, saves or closes a project. |
| `premiere_inspect` | read | 300 | Bins, project items, sequences, tracks, clips, transitions and markers. |
| `premiere_transitions` | read | 300 | Lists the video and audio transitions Premiere offers. |
| `premiere_presets` | read | none | Lists export and sequence presets. |
| `premiere_effects` | read | 300 | Lists the video and audio effects Premiere offers. |
| `premiere_find` | read | 300 | Finds project items and placed clips by name or path. |
| `premiere_import` | write | 300 | Imports files into a bin. |
| `premiere_items` | destructive | 300 | Renames, moves, labels, subclips, interprets, proxies or deletes a project item. |
| `premiere_bins` | destructive | 300 | Creates, renames, deletes bins and moves items into them. |
| `premiere_media_replace` | write | 300 | Points a project item at a new file or refreshes it. |
| `premiere_sequence_new` | write | 300 | Creates an empty sequence. |
| `premiere_sequence_set` | destructive | 300 | Changes settings, in/out points, nests, duplicates, renames or deletes a sequence. |
| `premiere_tracks` | write | 300 | Adds tracks and sets mute, lock and target state. |
| `premiere_clip_place` | write | 300 | Places a project item on a track. |
| `premiere_clip_edit` | destructive | 300 | Trims, moves, enables, renames, links or removes a placed clip. |
| `premiere_clip_copy` | destructive | 300 | Places another copy of a clip. |
| `premiere_clip_slip` | destructive | 300 | Shows a different part of a clip's source in the same place. |
| `premiere_clip_speed` | destructive | 300 | Sets a clip's speed or the duration it fills. |
| `premiere_clip_fit` | write | 300 | Scales a clip to fit or fill the frame. |
| `premiere_clip_props` | write | 300 | Sets Motion, Opacity and Volume, static or keyframed. |
| `premiere_fade` | destructive | 300 | Fades a clip in and out. |
| `premiere_color` | destructive | 300 | Basic Lumetri Color correction. |
| `premiere_effect_add` | write | 300 | Adds an effect to a clip. |
| `premiere_effect_set` | write | 300 | Sets or lists component parameters. |
| `premiere_transition_add` | write | 300 | Adds a transition to a clip edge. |
| `premiere_razor` | destructive | 300 | Splits clips at times. |
| `premiere_gaps` | destructive | 300 | Lists or closes empty gaps. |
| `premiere_range_remove` | destructive | 300 | Cuts a time range out of every unlocked track. |
| `premiere_scene_detect` | write | 600 | Finds hard cuts in a clip's media and optionally splits or marks them. |
| `premiere_markers_add` | write | 300 | Adds sequence markers or a beat grid. |
| `premiere_markers_edit` | destructive | 300 | Lists, updates or deletes sequence markers. |
| `premiere_mogrt_add` | write | 300 | Places a Motion Graphics template and sets its text. |
| `premiere_captions` | write | 300 | Imports an `.srt` as a caption track. |
| `premiere_auto_reframe` | write | 600 | Makes a new sequence at another aspect ratio. |
| `premiere_frame_export` | write | 300 | Exports PNG stills of a sequence. |
| `premiere_export` | destructive | 1800 | Exports a sequence with a preset. |
| `premiere_encode` | destructive | 1800 | Queues a sequence in Media Encoder. |
| `premiere_interchange` | destructive | 600 | Exports FCP XML, AAF or OMF, or imports an FCP XML. |

### `premiere_status`

Reports the installed Premiere Pro, Adobe Bridge (the script relay) and Media Encoder with versions
and process ids, whether the relay script is installed, the mailbox folder and the system ProRes 422
HQ export preset. An application that is not installed is reported in its own entry. Takes no
parameters. It starts nothing and talks to no application.

Returns `premiere`, `bridge`, `media_encoder`, `relay`, `mailbox`, `prores_preset`.

### `premiere_bridge_install`

Copies the relay startup script into Adobe Bridge's user Startup Scripts folder and reports whether
the installed copy matches the packaged one. Restart Bridge and approve the script once; see
[Set up the Bridge relay](../guides/bridge-setup.md). Takes no parameters.

Returns `path`, `matches`, `next`.

### `premiere_script`

Runs a `.jsx` file in Premiere Pro with the globals `CAVI_ARGS` (the `args` object) and
`CAVI_REPORT` (the `report` path). The call returns the script's last value as `answer`. A script
that throws is a tool error. When `report` names a `.json` path, the script writes JSON there and the
call returns it as `report`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `script` | string | required | Absolute path of the `.jsx` file. |
| `args` | object | none | Becomes `CAVI_ARGS`. |
| `report` | string | none | Absolute `.json` path the script writes. |

Returns `answer`, `report`.

### `premiere_cut`

Cuts a clip list into a new project: clips on V1, optional audio from 0 on A1, then exports a ProRes
422 HQ `.mov`. See [Cut from a clip list](../guides/cut-from-clip-list.md).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `project` | string | required | The `.prproj` to create. |
| `master` | string | required | The `.mov` to export. |
| `clips` | list of clip | required | At least one clip. |
| `audio` | string | none | One audio file, placed at 0 on A1 and played in full. |
| `replace` | boolean | `false` | Delete an existing project, master and report first. |

A clip has `file`, `start` (timeline seconds), `in_point` and `out_point` (source seconds) and an
optional `transition` with `kind` (`cross_dissolve`, `film_dissolve`, `dip_to_white`, `dip_to_black`
or a name `premiere_transitions` lists) and `frames` (1 to 600).

Returns `project`, `master`, `fps`, `frames`, `cut_frames`, `transitions`, `warnings`.

### `premiere_project`

Opens, creates, saves or closes a `.prproj`. `new` refuses an existing path unless `replace`.
`close` saves only when `save`. `close_others` closes every other open project unsaved after `open`
or `new`; `open` in the result is the number of open projects.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | `open`, `new`, `save`, `close` | required | What to do. |
| `path` | string | none | Required by `open` and `new`. |
| `replace` | boolean | `false` | Let `new` replace an existing file. |
| `save` | boolean | `false` | Save before `close`. |
| `close_others` | boolean | `false` | Close all other projects without saving. |

Returns `project`, `name`, `open`, `sequences`, `closed`, `warnings`.

### `premiere_inspect`

Reports bins, project items (media path, offline state, duration, frame rate, frame size, label),
sequences with every track's clips and transitions, and sequence markers, all in seconds.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `sequence` | string | none | Limit the report to one sequence. |

Returns `project`, `bins`, `items`, `sequences`, `warnings`.

### `premiere_transitions`

Lists every video and audio transition this Premiere Pro offers (QE names) and the short aliases
`cross_dissolve`, `film_dissolve`, `dip_to_white` and `dip_to_black`. Takes no parameters besides
`timeout`.

Returns `video`, `audio`, `aliases`.

### `premiere_presets`

Lists export presets (`.epr` from Premiere Pro, Media Encoder and the user's folders) and sequence
presets (`.sqpreset`) by name, format, source and path. Reads files only. Takes no parameters.

Returns `export`, `sequence`.

### `premiere_effects`

Lists the video and audio effects Premiere Pro offers (QE names).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `filter` | string | `""` | Keep names that contain this text. |

Returns `video`, `audio`, `warnings`.

### `premiere_find`

Finds project items and placed clips whose name or media path contains `query`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | `""` | Text to look for. |
| `scope` | `items`, `clips`, `both` | `"both"` | What to search. |
| `offline_only` | boolean | `false` | Only items whose media is missing. |
| `unused_only` | boolean | `false` | Only items placed on no sequence. |
| `sequence` | string | none | Sequence for the clip search. |

Returns `items`, `clips`, `warnings`.

### `premiere_import`

Imports files into a bin, created when missing; the project root when `bin` is empty.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `files` | list of string | required | At least one absolute path. |
| `bin` | string | none | Target bin name. |

Returns `bin`, `imported`, `warnings`.

### `premiere_items`

Organizes one project item, addressed by media path or name (bins by name). Clip items cannot be
deleted from a script; `remove` deletes bins only, with their contents.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `item` | string | required | Media path or name. |
| `rename` | string | none | New name. |
| `bin` | string | none | Move to this bin, created when missing. |
| `label` | integer | none | Color label 0 to 15. |
| `subclip` | object | none | `name`, `in_point` and `out_point` (source seconds) and `hard`. |
| `interpret` | object | none | `frame_rate`, `pixel_aspect`, `alpha` (`none`, `straight`, `premultiplied`, `ignore`), `invert_alpha`, `field_order` (`default`, `progressive`, `upper`, `lower`) and `remove_pulldown`. |
| `proxy` | string | none | Absolute path of a proxy file that matches the clip. |
| `xmp` | object | none | xmpDM text properties such as `logComment` and `shotName`. |
| `remove` | boolean | `false` | Delete the bin. |

Returns `item`, `subclip`, `interpretation`, `proxy`, `deleted`, `warnings`.

### `premiere_bins`

Creates, renames and deletes project bins and moves items into them. Deleting a bin removes its items
and their clips from every sequence, and is refused when the bin holds items unless `force`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | `create`, `rename`, `move`, `delete` | required | What to do. |
| `name` | string | none | The bin. |
| `parent` | string | none | Parent bin for `create`; the root when empty. |
| `new_name` | string | none | New name for `rename`. |
| `items` | list of string | none | Media paths or names for `move`. |
| `force` | boolean | `false` | Delete a bin that holds items. |

Returns `action`, `bin`, `moved`, `deleted`, `warnings`.

### `premiere_media_replace`

Points a project item at a new file, or refreshes it when the path is unchanged, so sequences show
the new media. The call checks the result through the project.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `item` | string | required | Media path or name. |
| `path` | string | required | The new file. |

Returns `name`, `previous_path`, `media_path`, `offline`, `verified`, `sequence_clips`, `warnings`.

### `premiere_sequence_new`

Creates an empty sequence with the settings of a project item or of a `.sqpreset`. Exactly one of
`clip` and `preset` is required.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | required | Sequence name. |
| `clip` | string | none | Project item (media path or name). |
| `preset` | string | none | Absolute `.sqpreset` path or a name `premiere_presets` lists. |
| `bin` | string | none | Bin for the new sequence. |

Returns `name`, `id`, `fps`, `width`, `height`, `video_tracks`, `audio_tracks`, `warnings`.

### `premiere_sequence_set`

Changes a sequence. At least one change is required; changes apply in this order: settings, in/out
points, nest, duplicate, rename, delete (alone).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `settings` | object | none | `width`, `height`, `fps` and `audio_rate`. |
| `in_point` | number | none | In point in seconds. |
| `out_point` | number | none | Out point in seconds. |
| `nest` | object | none | `clips` (a list of `kind`, `track`, `position_index`) and `name`; limited to the in/out range. |
| `duplicate` | string | none | Name of the copy; an empty string keeps Premiere's name. |
| `new_name` | string | none | Rename the sequence. |
| `remove` | boolean | `false` | Delete the sequence. |
| `sequence` | string | none | The sequence to change. |

Returns `sequence`, `nested`, `duplicate`, `deleted`, `sequences`, `warnings`.

### `premiere_tracks`

Adds video and stereo audio tracks after the last one and sets mute, lock and target state per
track. At least one of them is required.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `add_video` | integer | `0` | Video tracks to add, 0 to 20. |
| `add_audio` | integer | `0` | Audio tracks to add, 0 to 20. |
| `tracks` | list of object | none | Each has `kind`, `track` and any of `muted`, `locked`, `targeted`. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `before`, `after`, `tracks`, `warnings`.

### `premiere_clip_place`

Places a project item on a track at a time, with optional source in and out. A file that is not in the
project is imported first.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `item` | string | required | Media path or name. |
| `at` | number | required | Timeline start in seconds. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `in_point` | number | none | Source in point in seconds. |
| `out_point` | number | none | Source out point in seconds. |
| `mode` | `overwrite`, `insert` | `"overwrite"` | Replace what is there or push it right. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `clip`, `warnings`.

### `premiere_clip_edit`

Edits one placed clip. At least one edit is required, and `remove` stands alone.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `name` | string | none | Address by clip name. |
| `trim_start` | number | none | New start time; the source in point follows. |
| `trim_end` | number | none | New end time; the source out point follows. |
| `move_to` | number | none | New start time; moves only this clip. |
| `to_track` | integer | none | Move to another track of the same kind. |
| `enabled` | boolean | none | Enable or disable the clip. |
| `new_name` | string | none | Rename the clip. |
| `link_with` | object | none | `kind`, `track` and `position_index` of the clip to link. |
| `unlink` | boolean | `false` | Take apart the clip's link group. |
| `remove` | `ripple`, `lift` | none | Delete the clip and its linked clips. |
| `keep_linked` | boolean | `false` | With `remove`, keep the linked clips. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `clip`, `removed`, `note`, `warnings`.

### `premiere_clip_copy`

Places another copy of a clip (same media, same source range) at `to_time`, optionally on another
track of the same kind. The copy overwrites what is there and does not carry effects.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `to_time` | number | required | Start of the copy in seconds. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Source track. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `to_track` | integer | none | Target track; the source track when empty. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `clip`, `warnings`.

### `premiere_clip_slip`

Shows a different part of the clip's source while its place and length on the timeline stay. A slip
past the end of the media is undone and reported. Exactly one of `offset` and `in_point` is required.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `offset` | number | none | Seconds to move the source in point; positive shows later footage. |
| `in_point` | number | none | Set the source in point. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `with_linked` | boolean | `true` | Slip the linked clips too. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `clip`, `before`, `after`, `start`, `end`, `linked`, `warnings`.

### `premiere_clip_speed`

Sets a clip's speed in percent, or the timeline duration it should fill; the source range is kept.
Exactly one of `speed` and `duration` is required. A clip's linked audio is a separate clip: call
again with `kind` audio.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `speed` | number | none | Percent, above 0 and up to 10000. |
| `duration` | number | none | Seconds the clip should fill. |
| `reverse` | boolean | `false` | Play backwards. |
| `maintain_pitch` | boolean | `true` | Keep audio pitch. |
| `ripple` | boolean | `false` | Move the later clips; otherwise the clip stops at its neighbour. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `speed`, `reversed`, `start`, `end`, `duration`, `warnings`.

### `premiere_clip_fit`

Sets a video clip's Motion Scale and centers it so its source fits inside the frame or covers it.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `mode` | `fit`, `fill` | `"fit"` | Fit inside or cover the frame. |
| `track` | integer | `0` | Video track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `source`, `sequence_size`, `scale`, `warnings`.

### `premiere_clip_props`

Sets Motion position, scale and rotation, Opacity and audio Volume on a clip.
`keyframes` animate the properties they set and win over the static value.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `position` | pair of numbers | none | Pixels from the top left. |
| `scale` | number | none | Percent. |
| `rotation` | number | none | Degrees. |
| `opacity` | number | none | Percent. |
| `volume_db` | number | none | dB; 0 is unity. |
| `keyframes` | list of object | none | Each has `time` (seconds from the clip's start) and any of `position`, `scale`, `rotation`, `opacity` (0 to 100), `volume_db` (-96 to 15). |
| `sequence` | string | none | The sequence. |

Returns `clip`, `applied`, `keyframes`, `warnings`.

### `premiere_fade`

Fades a clip in and out with opacity keyframes (video, 0 to 100 percent) or volume keyframes (audio,
silent to 0 dB). At least one of `fade_in` and `fade_out` is required.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `fade_in` | number | `0` | Seconds at the start. |
| `fade_out` | number | `0` | Seconds at the end. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `keyframes`, `warnings`.

### `premiere_color`

Basic color correction on a video clip with Lumetri Color, added when the clip has none. `exposure` is
in stops from -5 to 5, `saturation` runs 0 to 200 (100 is neutral) and the others run -100 to 100.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `exposure` | number | none | Exposure in stops. |
| `contrast` | number | none | Contrast. |
| `highlights` | number | none | Highlights. |
| `shadows` | number | none | Shadows. |
| `whites` | number | none | Whites. |
| `blacks` | number | none | Blacks. |
| `temperature` | number | none | Temperature. |
| `tint` | number | none | Tint. |
| `saturation` | number | none | Saturation. |
| `vibrance` | number | none | Vibrance. |
| `track` | integer | `0` | Video track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `applied`, `warnings`.

### `premiere_effect_add`

Adds a video or audio effect (a name `premiere_effects` lists) to a clip and returns the clip's
components with their parameters.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `effect` | string | required | Effect name. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `components_before`, `components`, `warnings`.

### `premiere_effect_set`

Sets parameters of a clip's component by display name (Motion, Opacity, Lumetri Color, Crop, ...), or
lists them. Either `params` or `list` is required.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `component` | string | none | Component display name; with `list`, empty lists every component. |
| `params` | list of object | none | Each has `name`, one of `value`, `color` (`#RRGGBB`) or `keyframes`, and `index` (which of several parameters share the name). A keyframe has `time` (seconds from the clip's start), `value` or `color`, and `interpolation` (`linear`, `hold`, `bezier`). |
| `list` | boolean | `false` | Return the parameters with their values. |
| `component_index` | integer | `0` | Which of several components share the name. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `applied`, `components`, `warnings`.

### `premiere_transition_add`

Adds a QE transition at the start or end of a clip. `alignment` 0 starts the transition at the cut,
0.5 centers it, 1 ends it there. A transition needs source handles on both sides to reach its full
length.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `transition` | string | `"Cross Dissolve"` | A name `premiere_transitions` lists or an alias. |
| `frames` | integer | `12` | Length in frames, 1 to 600. |
| `kind` | `video`, `audio` | `"video"` | Track kind. |
| `track` | integer | `0` | Track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `edge` | `start`, `end` | `"start"` | Which edge of the clip. |
| `alignment` | number | `0.5` | 0 to 1. |
| `single_sided` | boolean | `false` | One-sided transition. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `transition`, `warnings`.

### `premiere_razor`

Splits clips at each time with the QE razor: every track of `kind`, or one track when `track` is given
(then `kind` is `video` or `audio`). Times are on the frame grid.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `times` | list of number | required | At least one time in seconds. |
| `kind` | `video`, `audio`, `all` | `"all"` | Which tracks. |
| `track` | integer | none | One track of `kind`. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `cuts`, `clips_before`, `clips_after`, `warnings`.

### `premiere_gaps`

Lists or closes empty gaps: time ranges with no clip on any unlocked track. `close` moves every later
clip left, last gap first, so tracks stay in sync.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | `list`, `close` | `"list"` | What to do. |
| `min_seconds` | number | `0` | Ignore shorter gaps. |
| `leading` | boolean | `false` | Include the space before the first clip. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `gaps`, `closed`, `moved`, `remaining`, `warnings`.

### `premiere_range_remove`

Cuts a time range out of every unlocked track: clips are split at both times and the ones inside are
removed. `extract` also moves later clips left to close the hole; `lift` leaves it empty.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `start` | number | required | Range start in seconds. |
| `end` | number | required | Range end in seconds. |
| `mode` | `lift`, `extract` | `"extract"` | Close the hole or leave it. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `mode`, `start`, `end`, `removed`, `moved`, `sequence_end`, `warnings`.

### `premiere_scene_detect`

Finds hard cuts inside a placed video clip from its media (an ffmpeg scene score above `threshold`)
and returns them as timeline seconds. Needs `ffmpeg`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `track` | integer | `0` | Video track index. |
| `at` | number | none | Address by time. |
| `position_index` | integer | none | Address by place on the track. |
| `threshold` | number | `0.3` | Scene score between 0 and 1, exclusive. |
| `apply` | `report`, `cuts`, `markers` | `"report"` | Only report, split the clip at each cut, or add a marker per cut. |
| `include_audio` | boolean | `false` | With `cuts`, split the audio tracks too. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `cuts`, `applied`, `clips_after`, `markers`, `warnings`.

### `premiere_markers_add`

Adds sequence markers at given times, one marker per beat from a tempo, or both. At least one of
`markers` and `beat_grid` is required. A beat grid names markers `bar.beat` and comments the first
beat of each bar `downbeat`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `markers` | list of object | none | Each has `time`, `name` (default empty), `comment` (default empty) and `duration` (default 0); at most 5000. |
| `beat_grid` | object | none | `bpm`, `beats_per_bar` (default 4), `start` (default 0) and `end`. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `added`, `total`, `warnings`.

### `premiere_markers_edit`

Lists sequence markers, or updates or deletes one by time-order index or start time, or all of them.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | `list`, `update`, `delete` | required | What to do. |
| `index` | integer | none | Address by time-order index. |
| `at` | number | none | Address by start time. |
| `all` | boolean | `false` | Apply to every marker. |
| `name` | string | none | New name for `update`. |
| `comment` | string | none | New comment for `update`. |
| `move_to` | number | none | New start time for `update`. |
| `duration` | number | none | New duration for `update`. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `total`, `markers`, `updated`, `deleted`, `warnings`.

### `premiere_mogrt_add`

Imports a `.mogrt` onto a video track at a time and sets its text parameters by name. Only templates
built in After Effects expose text parameters; the native Essential Graphics titles do not, and a
request for text on one is refused.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `mogrt` | string | required | Absolute path of the template. |
| `at` | number | required | Start in seconds. |
| `video_track` | integer | `1` | An existing video track. |
| `audio_track` | integer | `0` | Audio track for the template's audio. |
| `duration` | number | none | Length in seconds. |
| `text` | object | none | Parameter name to text. |
| `sequence` | string | none | The sequence. |

Returns `clip`, `start`, `end`, `track`, `parameters`, `text`, `warnings`.

### `premiere_captions`

Imports an `.srt` and creates a caption track on a sequence from `start` seconds. The count is read
from the file.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `file` | string | required | Absolute path of the `.srt`. |
| `start` | number | `0` | Where the captions start, in seconds. |
| `format` | `subtitle`, `608`, `708`, `teletext`, `op42`, `op47`, `open_ebu` | `"subtitle"` | Caption format. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `item`, `captions`, `warnings`.

### `premiere_auto_reframe`

Makes a new sequence at another aspect ratio with Auto Reframe.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `ratio` | string | required | `width:height`, such as `9:16`, `1:1` or `4:5`. |
| `motion` | `slower`, `default`, `faster` | `"default"` | Motion preset. |
| `name` | string | none | Name of the new sequence. |
| `nest` | boolean | `false` | Put the clips in nested sequences. |
| `sequence` | string | none | The source sequence. |

Returns `source`, `sequence`, `warnings`.

### `premiere_frame_export`

Exports PNG stills of a sequence at the given seconds into a folder and returns their paths and
sizes. Files are named `<prefix>_<n>_<time>s.png`; an existing file of the same name is replaced.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `times` | list of number | required | 1 to 50 times inside the sequence. |
| `folder` | string | required | Absolute folder path. |
| `prefix` | string | `"frame"` | A plain file-name prefix. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `frames`, `warnings`.

### `premiere_export`

Exports a sequence with a preset and confirms the file. Completion is judged by the report file, the
output released by every process and the `ffprobe` frame count, not by the relay's answer. See
[Export and encode](../guides/exports.md).

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `master` | string | required | Absolute output path. |
| `preset` | string | none | Absolute `.epr` path or a name `premiere_presets` lists; ProRes 422 HQ when empty. |
| `range` | `entire`, `in_out`, `work_area` | `"entire"` | What to export. |
| `replace` | boolean | `false` | Replace an existing file. |
| `burn_captions` | boolean | none | Export from a copy of the preset with its captions setting changed. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `master`, `fps`, `frames`, `expected_frames`, `complete`, `warnings`.

### `premiere_encode`

Queues a sequence in Adobe Media Encoder, started when needed, and starts the batch. Premiere Pro
stays free; completion is judged by the output file, no process holding it open and the `ffprobe`
frame count.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `master` | string | required | Absolute output path. |
| `preset` | string | none | Absolute `.epr` path or a name `premiere_presets` lists. |
| `range` | `entire`, `in_out`, `work_area` | `"entire"` | What to encode. |
| `replace` | boolean | `false` | Replace an existing file. |
| `sequence` | string | none | The sequence. |

Returns `sequence`, `master`, `fps`, `frames`, `expected_frames`, `complete`, `warnings`.

### `premiere_interchange`

Exports a sequence as FCP XML (`xml`), AAF or OMF to an absolute path, or imports an FCP XML
(`import_xml`) into the project. The file or the new sequence is checked.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | `xml`, `aaf`, `omf`, `import_xml` | required | What to do. |
| `path` | string | required | Absolute path of the file. |
| `replace` | boolean | `false` | Replace an existing file. |
| `audio_rate` | integer | `48000` | Audio rate for AAF and OMF, 8000 to 192000. |
| `bits` | `16`, `24` | `16` | Audio bit depth for AAF and OMF. |
| `sequence` | string | none | The sequence to export. |

Returns `action`, `path`, `size`, `sequence`, `imported`, `warnings`.
