"""The Premiere Pro tools."""

import asyncio
from typing import Annotated, Any, Literal

from cavi_mcp_core.server import DESTRUCTIVE, READ_ONLY, WRITES
from pydantic import Field

from . import host
from .app import (
    ClipAt,
    ClipIndex,
    ClipKind,
    ClipTrack,
    Kind,
    Range,
    Seconds,
    SequenceName,
    Timeout,
    Track,
    mcp,
)
from .models import (
    Added,
    BeatGrid,
    BridgeInstall,
    Captions,
    Clip,
    ClipEdit,
    Cut,
    EffectAdded,
    Effects,
    EffectSet,
    Export,
    Fit,
    Frames,
    Import,
    Inspect,
    Interchange,
    Interpret,
    Items,
    Keyframe,
    LinkRef,
    Markers,
    Mogrt,
    NestSpec,
    NewMarker,
    NewSequence,
    Param,
    Placed,
    Presets,
    Project,
    Props,
    Razor,
    Reframed,
    Replaced,
    Scenes,
    Script,
    SequenceChange,
    SequenceSettings,
    Speed,
    Status,
    SubClip,
    Tracks,
    TrackSet,
    Transitions,
)


@mcp.tool(annotations=READ_ONLY)
async def premiere_status() -> Status:
    """Installed Premiere Pro, Adobe Bridge (the script relay) and Media Encoder with versions and pids, the
    relay install state, the mailbox and the ProRes preset. An application that is not installed is
    reported in its entry."""
    return await asyncio.to_thread(host.status)


@mcp.tool(annotations=WRITES)
async def premiere_bridge_install() -> BridgeInstall:
    """Copy the relay startup script into Adobe Bridge; restart Bridge and approve it once in its settings."""
    return await asyncio.to_thread(host.bridge_install)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_script(
        script: Annotated[str, Field(description="Absolute path of the .jsx to run.")],
        args: Annotated[dict[str, Any] | None, Field(description="Values the script reads as CAVI_ARGS.")] = None,
        report: Annotated[str | None, Field(description="Absolute .json path the script writes as CAVI_REPORT.")] = None,
        timeout: Timeout = 1800) -> Script:
    """Run a .jsx in Premiere with globals CAVI_ARGS and CAVI_REPORT (a .json path it writes). A script that
    throws is a tool error; its last value is the answer."""
    return await asyncio.to_thread(host.run_script, script, args or {}, report, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_cut(
        project: Annotated[str, Field(description="Absolute path of the new .prproj.")],
        master: Annotated[str, Field(description="Absolute path of the exported .mov.")],
        clips: Annotated[list[Clip], Field(min_length=1, description="Clips placed on V1 in timeline order.")],
        audio: Annotated[str | None, Field(description="Absolute path of an audio file placed on A1 from 0.")] = None,
        replace: Annotated[bool, Field(description="Delete an existing project, master and report first.")] = False,
        timeout: Timeout = 1800) -> Cut:
    """New .prproj with clips (seconds) on V1, optional audio from 0 on A1; exports a ProRes 422 HQ .mov.

    Transitions go at the start of their clip. replace deletes an existing project, master and report.
    """
    return await asyncio.to_thread(host.cut, project, master, [c.model_dump() for c in clips], audio,
                                   replace, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_project(
        action: Annotated[Literal["open", "new", "save", "close"], Field(description="What to do with the project.")],
        path: Annotated[str | None, Field(description="Absolute .prproj path; required for open and new.")] = None,
        replace: Annotated[bool, Field(description="Let new overwrite an existing project file.")] = False,
        save: Annotated[bool, Field(description="Save the project before close.")] = False,
        close_others: Annotated[bool, Field(description="After open or new, close every other open project "
                                                        "without saving.")] = False,
        timeout: Timeout = 300) -> Project:
    """Open, create, save or close a .prproj. The result's open is the number of open projects."""
    return await asyncio.to_thread(host.project, action, path, replace, save, close_others, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_inspect(
        sequence: Annotated[str | None, Field(description="Report only this sequence; every sequence when "
                                                          "omitted.")] = None,
        timeout: Timeout = 300) -> Inspect:
    """Bins, project items (media path, offline, duration, fps, size), sequences with each track's clips,
    transitions and markers, all in seconds."""
    return await asyncio.to_thread(host.inspect, sequence, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_transitions(timeout: Timeout = 300) -> Transitions:
    """Every video and audio transition this Premiere offers (QE names), and the short aliases."""
    return await asyncio.to_thread(host.transitions, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_presets() -> Presets:
    """Export presets (.epr: Premiere, Media Encoder and user) and sequence presets (.sqpreset) by name."""
    return await asyncio.to_thread(host.all_presets)


@mcp.tool(annotations=WRITES)
async def premiere_import(
        files: Annotated[list[str], Field(min_length=1, description="Absolute paths of the files to import.")],
        bin: Annotated[str | None, Field(description="Bin to import into, created when missing; the project "
                                                     "root when omitted.")] = None,
        timeout: Timeout = 300) -> Import:
    """Import files into the project, into a bin when one is named."""
    return await asyncio.to_thread(host.import_files, files, bin, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_sequence_new(
        name: Annotated[str, Field(description="Name of the new sequence.")],
        clip: Annotated[str | None, Field(description="Project item (media path or name) whose settings the "
                                                      "sequence takes.")] = None,
        preset: Annotated[str | None, Field(description="Sequence preset: absolute .sqpreset path or a name "
                                                        "premiere_presets lists.")] = None,
        bin: Annotated[str | None, Field(description="Bin to put the sequence in.")] = None,
        timeout: Timeout = 300) -> NewSequence:
    """New empty sequence with the settings of a project item or of a sequence preset (exactly one)."""
    return await asyncio.to_thread(host.sequence_new, name, clip, preset, bin, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_clip_place(
        item: Annotated[str, Field(description="Project item to place: media path or name.")],
        at: Annotated[Seconds, Field(description="Sequence time where the clip starts, in seconds.")],
        kind: Annotated[Kind, Field(description="Track type to place on.")] = "video",
        track: Annotated[Track, Field(description="0-based track index; 0 is V1 or A1.")] = 0,
        in_point: Annotated[Seconds | None, Field(description="Source in point, in seconds.")] = None,
        out_point: Annotated[Seconds | None, Field(description="Source out point, in seconds.")] = None,
        mode: Annotated[Literal["overwrite", "insert"], Field(description="overwrite replaces what is there; "
                                                                          "insert pushes later clips right.")]
        = "overwrite",
        sequence: SequenceName = None, timeout: Timeout = 300) -> Placed:
    """Place a project item on a track at a time; a file not yet imported is imported first."""
    return await asyncio.to_thread(host.clip_place, sequence, item, kind, track, at, in_point, out_point, mode,
                                   timeout)


@mcp.tool(annotations=WRITES)
async def premiere_clip_props(
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        position: Annotated[tuple[float, float] | None, Field(description="Motion position in pixels from the "
                                                                          "top left.")] = None,
        scale: Annotated[float | None, Field(description="Motion scale in percent.")] = None,
        rotation: Annotated[float | None, Field(description="Motion rotation in degrees.")] = None,
        opacity: Annotated[float | None, Field(description="Opacity in percent.")] = None,
        volume_db: Annotated[float | None, Field(description="Audio volume in dB.")] = None,
        keyframes: Annotated[list[Keyframe] | None, Field(description="Keyframes, timed in seconds from the "
                                                                      "clip's start.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Props:
    """Set Motion, Opacity and audio Volume on a clip. keyframes animate the properties they set and win
    over the static value."""
    props = {"position": position and list(position), "scale": scale, "rotation": rotation, "opacity": opacity,
             "volume_db": volume_db}
    frames = [{k: (list(v) if isinstance(v, tuple) else v) for k, v in key.model_dump().items() if v is not None}
              for key in keyframes or []]
    return await asyncio.to_thread(host.clip_props, sequence, kind, track, at, position_index, props, frames,
                                   timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_clip_edit(
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        name: Annotated[str | None, Field(description="Picks the clip by its name on the track.")] = None,
        trim_start: Annotated[Seconds | None, Field(description="New timeline start; the source in point "
                                                                "follows.")] = None,
        trim_end: Annotated[Seconds | None, Field(description="New timeline end; the source out point "
                                                              "follows.")] = None,
        move_to: Annotated[Seconds | None, Field(description="New start time, in seconds.")] = None,
        to_track: Annotated[Track | None, Field(description="0-based track to move the clip to.")] = None,
        enabled: Annotated[bool | None, Field(description="Enable or disable the clip.")] = None,
        new_name: Annotated[str | None, Field(description="New clip name.")] = None,
        link_with: Annotated[LinkRef | None, Field(description="Another clip to link this one with.")] = None,
        unlink: Annotated[bool, Field(description="Unlink the clip from its linked clips.")] = False,
        remove: Annotated[Literal["ripple", "lift"] | None,
                          Field(description="Delete the clip: ripple closes the gap, lift leaves it.")] = None,
        keep_linked: Annotated[bool, Field(description="With remove, keep the linked clips.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 300) -> ClipEdit:
    """Trim, move, enable, rename, link, unlink or remove a placed clip. remove stands alone and also deletes
    the linked clips; ripple shifts the later clips of every unlocked track left."""
    edit = {"trim_start": trim_start, "trim_end": trim_end, "move_to": move_to, "to_track": to_track,
            "enabled": enabled, "new_name": new_name, "link_with": link_with and link_with.model_dump(),
            "unlink": unlink or None, "remove": remove, "keep_linked": keep_linked or None}
    return await asyncio.to_thread(host.clip_edit, sequence, kind, track, at, position_index, name, edit, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_razor(
        times: Annotated[list[Seconds], Field(min_length=1, description="Sequence times to split at, in "
                                                                        "seconds.")],
        kind: Annotated[Literal["video", "audio", "all"], Field(description="Track types to split.")] = "all",
        track: Annotated[Track | None, Field(description="Split only this 0-based track; kind must then be "
                                                         "video or audio.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Razor:
    """Split clips at each time with the QE razor, on every track of kind or on one track. Times snap to
    the frame grid."""
    return await asyncio.to_thread(host.razor, sequence, times, kind, track, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_clip_speed(
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        speed: Annotated[Annotated[float, Field(gt=0, le=10000)] | None,
                         Field(description="Speed in percent; 100 is normal.")] = None,
        duration: Annotated[Annotated[float, Field(gt=0)] | None,
                            Field(description="Timeline duration the clip should fill, in seconds.")] = None,
        reverse: Annotated[bool, Field(description="Play the clip backwards.")] = False,
        maintain_pitch: Annotated[bool, Field(description="Keep the audio pitch.")] = True,
        ripple: Annotated[bool, Field(description="Move the later clips with the new length.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Speed:
    """Set a clip's speed or the timeline duration it fills (exactly one; the source range is kept). Linked
    audio is a separate clip: call again with kind audio."""
    return await asyncio.to_thread(host.clip_speed, sequence, kind, track, at, position_index, speed, duration,
                                   reverse, maintain_pitch, ripple, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_sequence_set(
        settings: Annotated[SequenceSettings | None, Field(description="Frame size, frame rate and audio "
                                                                       "rate.")] = None,
        in_point: Annotated[Seconds | None, Field(description="Sequence in point, in seconds.")] = None,
        out_point: Annotated[Seconds | None, Field(description="Sequence out point, in seconds.")] = None,
        nest: Annotated[NestSpec | None, Field(description="Clips to nest into a new sequence.")] = None,
        duplicate: Annotated[str | None, Field(description="Name of a copy of the sequence; \"\" keeps "
                                                           "Premiere's name.")] = None,
        new_name: Annotated[str | None, Field(description="New sequence name.")] = None,
        remove: Annotated[bool, Field(description="Delete the sequence; give no other change.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 300) -> SequenceChange:
    """Change a sequence: settings, in/out points, nest clips into a new sequence (within the in/out
    range), duplicate, rename or delete. Applied in that order."""
    change = {"settings": settings and settings.model_dump(), "in_point": in_point, "out_point": out_point,
              "nest": nest and nest.model_dump(), "duplicate": duplicate, "new_name": new_name,
              "remove": remove}
    return await asyncio.to_thread(host.sequence_set, sequence, change, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_tracks(
        add_video: Annotated[int, Field(ge=0, le=20, description="Video tracks to add after the last one.")] = 0,
        add_audio: Annotated[int, Field(ge=0, le=20, description="Stereo audio tracks to add after the last "
                                                                 "one.")] = 0,
        tracks: Annotated[list[TrackSet] | None, Field(description="Mute, lock and target state per "
                                                                   "track.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Tracks:
    """Add tracks and set mute, lock and target per track; returns the counts before and after and every
    track's state."""
    states = [t.model_dump() for t in tracks or []]
    return await asyncio.to_thread(host.tracks, sequence, add_video, add_audio, states, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_frame_export(
        times: Annotated[list[Seconds], Field(min_length=1, max_length=50, description="Sequence times of the "
                                                                                       "stills, in seconds.")],
        folder: Annotated[str, Field(description="Absolute path of the folder the PNGs go to.")],
        prefix: Annotated[str, Field(description="File name prefix; a plain name, no folders.")] = "frame",
        sequence: SequenceName = None, timeout: Timeout = 300) -> Frames:
    """Export PNG stills of the sequence and return their paths and sizes (open them to look at the
    result). A file of the same name is replaced."""
    return await asyncio.to_thread(host.frame_export, sequence, times, folder, prefix, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_effects(
        filter: Annotated[str, Field(description="List only effects whose name contains this text.")] = "",
        timeout: Timeout = 300) -> Effects:
    """Video and audio effects Premiere offers (QE names), limited to names containing `filter`."""
    return await asyncio.to_thread(host.effects, filter, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_effect_add(
        effect: Annotated[str, Field(description="Effect name, as premiere_effects lists it.")],
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> EffectAdded:
    """Add a video or audio effect to a clip; returns the clip's components with their parameters."""
    return await asyncio.to_thread(host.effect_add, sequence, kind, track, at, position_index, effect, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_effect_set(
        component: Annotated[str | None, Field(description="Component display name, such as Motion, Opacity "
                                                           "or Lumetri Color.")] = None,
        params: Annotated[list[Param] | None, Field(description="Parameters to set by display name.")] = None,
        list: Annotated[bool, Field(description="Return the parameters and their values instead of "
                                                "setting.")] = False,
        component_index: Annotated[int, Field(ge=0, description="Which of several components with the same "
                                                                "name, 0-based.")] = 0,
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> EffectSet:
    """Set or list parameters of a clip's component by display name. A param is a value, a #RRGGBB color or
    keyframes (seconds from the clip's start; linear, hold or bezier); its index picks among parameters
    that share a name. list without component lists every component."""
    specs = [p.model_dump(exclude_none=True) for p in params or []]
    return await asyncio.to_thread(host.effect_set, sequence, kind, track, at, position_index, component,
                                   component_index, list, specs, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_clip_fit(
        mode: Annotated[Literal["fit", "fill"], Field(description="fit shows the whole source; fill covers the "
                                                                  "frame.")] = "fit",
        track: Annotated[Track, Field(description="0-based video track index of the clip; 0 is V1.")] = 0,
        at: ClipAt = None, position_index: ClipIndex = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Fit:
    """Scale and center a video clip so its source fits inside the frame or covers it, whatever its size."""
    return await asyncio.to_thread(host.clip_fit, sequence, track, at, position_index, mode, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_items(
        item: Annotated[str, Field(description="Project item (media path or name), or a bin by name.")],
        rename: Annotated[str | None, Field(description="New item name.")] = None,
        bin: Annotated[str | None, Field(description="Bin to move the item to, created when missing.")] = None,
        label: Annotated[Annotated[int, Field(ge=0, le=15)] | None,
                         Field(description="Color label index, 0 to 15.")] = None,
        subclip: Annotated[SubClip | None, Field(description="Make a subclip from a source range.")] = None,
        interpret: Annotated[Interpret | None, Field(description="Footage interpretation to set.")] = None,
        proxy: Annotated[str | None, Field(description="Absolute path of a proxy file to attach.")] = None,
        xmp: Annotated[dict[str, str] | None, Field(description="xmpDM metadata text by field, such as "
                                                                "logComment or scene.")] = None,
        remove: Annotated[bool, Field(description="Delete the bin named by item.")] = False,
        timeout: Timeout = 300) -> Items:
    """Organize a project item: rename, move to a bin, color label, subclip, interpretation, proxy or
    xmpDM metadata, or delete a bin. Clip items cannot be deleted from a script."""
    change = {"rename": rename, "bin": bin, "label": label, "subclip": subclip and subclip.model_dump(),
              "interpret": interpret and interpret.model_dump(exclude_none=True) or None,
              "proxy": proxy and {"path": proxy}, "xmp": xmp, "remove": remove}
    return await asyncio.to_thread(host.items, item, change, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_scene_detect(
        track: Annotated[Track, Field(description="0-based video track index of the clip; 0 is V1.")] = 0,
        at: ClipAt = None, position_index: ClipIndex = None,
        threshold: Annotated[float, Field(gt=0, lt=1, description="ffmpeg scene score a cut must exceed.")] = 0.3,
        apply: Annotated[Literal["report", "cuts", "markers"],
                         Field(description="report only, split the clip at each cut, or add a marker per "
                                           "cut.")] = "report",
        include_audio: Annotated[bool, Field(description="With cuts, split every track, audio "
                                                         "included.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 600) -> Scenes:
    """Find hard cuts inside a placed video clip from its media and return them as timeline seconds;
    optionally split the clip or add a marker at each."""
    return await asyncio.to_thread(host.scene_detect, sequence, track, at, position_index, threshold, apply,
                                   include_audio, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_transition_add(
        transition: Annotated[str, Field(description="Transition name premiere_transitions lists, or an "
                                                     "alias.")] = "Cross Dissolve",
        frames: Annotated[int, Field(ge=1, le=600, description="Transition length in frames.")] = 12,
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        edge: Annotated[Literal["start", "end"], Field(description="Which end of the clip.")] = "start",
        alignment: Annotated[float, Field(ge=0, le=1, description="0 starts at the cut, 0.5 centers on it, 1 "
                                                                  "ends at it.")] = 0.5,
        single_sided: Annotated[bool, Field(description="Apply to this clip only, not across the "
                                                        "cut.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Added:
    """Add a QE transition at the start or end of a clip. Aliases: cross_dissolve, film_dissolve,
    dip_to_black, dip_to_white."""
    return await asyncio.to_thread(host.transition_add, sequence, kind, track, at, position_index, transition,
                                   frames, edge, alignment, single_sided, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_media_replace(
        item: Annotated[str, Field(description="Project item to repoint: media path or name.")],
        path: Annotated[str, Field(description="Absolute path of the new media; the same path refreshes it.")],
        timeout: Timeout = 300) -> Replaced:
    """Point a project item at a new file, or refresh it, so sequences show the new media; the result is
    checked through premiere_inspect."""
    return await asyncio.to_thread(host.media_replace, item, path, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_markers_add(
        markers: Annotated[Annotated[list[NewMarker], Field(max_length=host.MAX_MARKERS)] | None,
                           Field(description="Markers to add, timed in seconds.")] = None,
        beat_grid: Annotated[BeatGrid | None, Field(description="One marker per beat at a tempo between two "
                                                                "times.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Markers:
    """Add sequence markers, a beat grid (named bar.beat; bar starts commented "downbeat") or both."""
    return await asyncio.to_thread(host.markers_add, sequence, [m.model_dump() for m in markers or []],
                                   beat_grid and beat_grid.model_dump(), timeout)


@mcp.tool(annotations=WRITES)
async def premiere_mogrt_add(
        mogrt: Annotated[str, Field(description="Absolute path of the .mogrt.")],
        at: Annotated[Seconds, Field(description="Sequence time where the graphic starts, in seconds.")],
        video_track: Annotated[Track, Field(description="0-based video track for the graphic.")] = 1,
        audio_track: Annotated[Track, Field(description="0-based audio track for its audio.")] = 0,
        duration: Annotated[Annotated[float, Field(gt=0)] | None,
                            Field(description="Length on the timeline in seconds; the template's when "
                                              "omitted.")] = None,
        text: Annotated[dict[str, str] | None, Field(description="Text parameter values by parameter "
                                                                 "name.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Mogrt:
    """Add a .mogrt to the sequence and set its text parameters. Only templates built in After Effects
    expose text parameters."""
    return await asyncio.to_thread(host.mogrt_add, sequence, mogrt, at, video_track, audio_track, duration,
                                   text or {}, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_export(
        master: Annotated[str, Field(description="Absolute path of the exported file.")],
        preset: Annotated[str | None, Field(description="Export preset: absolute .epr path or a name "
                                                        "premiere_presets lists; ProRes 422 HQ when "
                                                        "omitted.")] = None,
        range: Annotated[Range, Field(description="Whole sequence, its in/out points or its work "
                                                  "area.")] = "entire",
        replace: Annotated[bool, Field(description="Overwrite an existing file.")] = False,
        burn_captions: Annotated[bool | None, Field(description="Burn captions in or not; the preset's setting "
                                                                "when omitted.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 1800) -> Export:
    """Export a sequence with exportAsMediaDirect. A preset name that is not unique takes format/name.
    burn_captions exports from a copy of the preset (H.264 burns captions in; ProRes does not). Done means
    the report, the file released by every process and the ffprobe frame count agree."""
    return await asyncio.to_thread(host.export, sequence, master, preset, range, replace, timeout, burn_captions)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_encode(
        master: Annotated[str, Field(description="Absolute path of the encoded file.")],
        preset: Annotated[str | None, Field(description="Export preset: absolute .epr path or a name "
                                                        "premiere_presets lists.")] = None,
        range: Annotated[Range, Field(description="Whole sequence, its in/out points or its work "
                                                  "area.")] = "entire",
        replace: Annotated[bool, Field(description="Overwrite an existing file.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 1800) -> Export:
    """Queue a sequence in Adobe Media Encoder (started when needed) and start the batch; Premiere stays
    free. Done means the file exists, no process holds it and the ffprobe frame count matches."""
    return await asyncio.to_thread(host.encode, sequence, master, preset, range, replace, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_auto_reframe(
        ratio: Annotated[str, Field(description="Target aspect ratio as width:height, such as 9:16.")],
        motion: Annotated[Literal["slower", "default", "faster"], Field(description="Auto Reframe motion "
                                                                                    "preset.")] = "default",
        name: Annotated[str | None, Field(description="Name of the new sequence.")] = None,
        nest: Annotated[bool, Field(description="Put the clips in nested sequences.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 600) -> Reframed:
    """New sequence at another aspect ratio from Auto Reframe; returns the new sequence."""
    return await asyncio.to_thread(host.auto_reframe, sequence, ratio, motion, name, nest, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_interchange(
        action: Annotated[Literal["xml", "aaf", "omf", "import_xml"],
                          Field(description="Export as FCP XML, AAF or OMF, or import an FCP XML.")],
        path: Annotated[str, Field(description="Absolute path of the file to write or import.")],
        replace: Annotated[bool, Field(description="Overwrite an existing file.")] = False,
        audio_rate: Annotated[int, Field(ge=8000, le=192000, description="AAF and OMF audio sample rate in "
                                                                         "Hz.")] = 48000,
        bits: Annotated[Literal[16, 24], Field(description="AAF and OMF audio bit depth.")] = 16,
        sequence: SequenceName = None, timeout: Timeout = 600) -> Interchange:
    """Export a sequence as FCP XML, AAF or OMF, or import an FCP XML into the project; the file or the
    new sequence is checked."""
    return await asyncio.to_thread(host.interchange, sequence, action, path, replace, audio_rate, bits, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_captions(
        file: Annotated[str, Field(description="Absolute path of the .srt.")],
        start: Annotated[Seconds, Field(description="Sequence time where the captions start, in seconds.")] = 0,
        format: Annotated[Literal["subtitle", "608", "708", "teletext", "op42", "op47", "open_ebu"],
                          Field(description="Caption track format.")] = "subtitle",
        sequence: SequenceName = None, timeout: Timeout = 300) -> Captions:
    """Import an .srt as a caption track; returns the caption count read from the file. Captions appear in
    premiere_frame_export stills."""
    return await asyncio.to_thread(host.captions, sequence, file, start, format, timeout)

