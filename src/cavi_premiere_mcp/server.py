"""MCP server for Adobe Premiere Pro."""

import asyncio
from typing import Annotated, Any, Literal

from cavi_mcp_core.contracts import Result
from cavi_mcp_core.server import DESTRUCTIVE, READ_ONLY, WRITES, Server
from pydantic import BaseModel, ConfigDict, Field

from . import host

mcp = Server("cavi-premiere", package="cavi-premiere-mcp",
             instructions="Premiere Pro, driven through Photoshop BridgeTalk. Paths are absolute.")
Seconds = Annotated[float, Field(ge=0)]
Timeout = Annotated[int, Field(ge=30, le=7200)]
Track = Annotated[int, Field(ge=0)]
Kind = Literal["video", "audio"]


class App(BaseModel):
    app: str
    version: str
    pids: list[int]


class Status(Result):
    premiere: App
    photoshop: App
    prores_preset: str


class Script(Result):
    answer: str
    report: Any = None


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str  # an alias (cross_dissolve, film_dissolve, dip_to_white, dip_to_black) or a name premiere_transitions lists
    frames: int = Field(ge=1, le=600)


class Clip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    start: Seconds
    in_point: Seconds
    out_point: Seconds
    transition: Transition | None = None


class Cut(Result):
    project: str
    master: str
    fps: str
    frames: int
    cut_frames: int
    transitions: list[str]
    warnings: list[str]


class Transitions(Result):
    video: list[str]
    audio: list[str]
    aliases: dict[str, str]


class PresetEntry(BaseModel):
    name: str
    format: str
    source: Literal["premiere", "media_encoder", "user"]
    path: str


class Presets(Result):
    export: list[PresetEntry]
    sequence: list[PresetEntry]


class Project(Result):
    project: str | None
    name: str | None
    open: int
    sequences: int
    closed: str | None = None


class Item(BaseModel):
    name: str
    bin: str
    kind: Literal["clip", "bin", "sequence"]
    media_path: str | None
    offline: bool | None
    duration: float | None
    fps: float | None
    width: int | None
    height: int | None


class TimelineClip(BaseModel):
    position: int
    name: str
    start: float
    end: float
    in_point: float
    out_point: float
    media_path: str | None


class Move(BaseModel):
    name: str | None
    start: float
    end: float


class Lane(BaseModel):
    index: int
    name: str
    clips: list[TimelineClip]
    transitions: list[Move]


class Marker(BaseModel):
    name: str
    comment: str
    start: float
    end: float


class SequenceInfo(BaseModel):
    name: str
    id: str
    fps: float
    width: int
    height: int
    end: float
    video: list[Lane]
    audio: list[Lane]
    markers: list[Marker]


class Inspect(Result):
    project: str
    bins: list[str]
    items: list[Item]
    sequences: list[SequenceInfo]


class Imported(BaseModel):
    name: str
    media_path: str


class Import(Result):
    bin: str
    imported: list[Imported]
    warnings: list[str]


class NewSequence(Result):
    name: str
    id: str
    fps: float
    width: int
    height: int
    video_tracks: int
    audio_tracks: int


class Placed(Result):
    sequence: str
    clip: TimelineClip


class Props(Result):
    clip: str
    applied: dict[str, Any]
    keyframes: dict[str, list[dict[str, Any]]]


class Added(Result):
    clip: str
    transition: Move


class Replaced(Result):
    name: str
    previous_path: str | None
    media_path: str
    offline: bool
    verified: bool
    sequence_clips: int


class Markers(Result):
    sequence: str
    added: int
    total: int


class Mogrt(Result):
    clip: str
    start: float
    end: float
    track: int | None = None
    parameters: list[str] = []
    text: dict[str, str]


class Export(Result):
    sequence: str
    master: str
    fps: float
    frames: int
    expected_frames: int | None
    complete: bool
    warnings: list[str]


class Reframed(Result):
    source: str
    sequence: dict[str, Any]


class Interchange(Result):
    action: str
    path: str
    size: int
    sequence: str | None = None
    imported: list[str] | None = None


class Captions(Result):
    sequence: str
    item: str
    captions: int


class Keyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Seconds
    position: tuple[float, float] | None = None
    scale: float | None = Field(default=None, ge=0)
    rotation: float | None = None
    opacity: float | None = Field(default=None, ge=0, le=100)
    volume_db: float | None = Field(default=None, ge=-96, le=15)


class BeatGrid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bpm: float = Field(gt=0, le=1000)
    beats_per_bar: int = Field(default=4, ge=1, le=32)
    start: Seconds = 0
    end: Annotated[float, Field(gt=0)]


class NewMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Seconds
    name: str = ""
    comment: str = ""
    duration: Seconds = 0


class EditedClip(BaseModel):
    track: int
    name: str
    start: float
    end: float
    in_point: float
    out_point: float
    enabled: bool
    position: int | None
    linked: int


class Removed(BaseModel):
    name: str
    start: float
    end: float
    mode: str
    partners: int = 0


class ClipEdit(Result):
    sequence: str
    clip: EditedClip | None = None
    removed: Removed | None = None
    note: str | None = None


class Razor(Result):
    sequence: str
    cuts: int
    clips_before: int
    clips_after: int


class Speed(Result):
    clip: str
    speed: float
    reversed: bool
    start: float
    end: float
    duration: float


class SequenceState(BaseModel):
    name: str
    id: str
    width: int
    height: int
    fps: float
    audio_rate: int
    end: float
    in_point: float | None
    out_point: float | None


class SequenceChange(Result):
    sequence: SequenceState | None = None
    nested: SequenceState | None = None
    duplicate: SequenceState | None = None
    deleted: str | None = None
    sequences: list[str]


class TrackCounts(BaseModel):
    video: int
    audio: int


class TrackState(BaseModel):
    index: int
    name: str
    muted: bool
    locked: bool
    targeted: bool
    clips: int


class TrackLists(BaseModel):
    video: list[TrackState]
    audio: list[TrackState]


class Tracks(Result):
    sequence: str
    before: TrackCounts
    after: TrackCounts
    tracks: TrackLists


class Still(BaseModel):
    time: float
    path: str
    width: int
    height: int


class Frames(Result):
    sequence: str
    frames: list[Still]


class LinkRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    track: Track = 0
    position_index: Annotated[int, Field(ge=0)]


class NestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clips: Annotated[list[LinkRef], Field(min_length=1)]
    name: str = ""


class SequenceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: Annotated[int, Field(ge=16, le=16384)] | None = None
    height: Annotated[int, Field(ge=16, le=16384)] | None = None
    fps: Annotated[float, Field(gt=0, le=240)] | None = None
    audio_rate: Annotated[int, Field(ge=8000, le=192000)] | None = None


class TrackSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    track: Track
    muted: bool | None = None
    locked: bool | None = None
    targeted: bool | None = None


@mcp.tool(annotations=READ_ONLY)
async def premiere_status() -> Status:
    """Installed Premiere Pro and Photoshop (the script relay), their pids, and the ProRes preset."""
    return await asyncio.to_thread(host.status)


@mcp.tool(annotations=WRITES)
async def premiere_script(script: str, args: dict[str, Any] | None = None, report: str | None = None,
                          timeout: Timeout = 1800) -> Script:
    """Run a .jsx in Premiere with globals CAVI_ARGS and CAVI_REPORT (a .json path it writes)."""
    return await asyncio.to_thread(host.run_script, script, args or {}, report, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_cut(project: str, master: str, clips: Annotated[list[Clip], Field(min_length=1)],
                       audio: str | None = None, replace: bool = False, timeout: Timeout = 1800) -> Cut:
    """New .prproj with clips (seconds) on V1, optional audio from 0 on A1; exports a ProRes 422 HQ .mov.

    Transitions go at the start of their clip. replace deletes an existing project, master and report.
    """
    return await asyncio.to_thread(host.cut, project, master, [c.model_dump() for c in clips], audio,
                                   replace, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_project(action: Literal["open", "new", "save", "close"], path: str | None = None,
                           replace: bool = False, save: bool = False, close_others: bool = False,
                           timeout: Timeout = 300) -> Project:
    """Open, create, save or close a .prproj. new refuses an existing path unless replace; close saves only
    when save. close_others closes every other open project unsaved after open or new; open is the count."""
    return await asyncio.to_thread(host.project, action, path, replace, save, close_others, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_inspect(sequence: str | None = None, timeout: Timeout = 300) -> Inspect:
    """Bins, project items (media path, offline, duration, fps, size), sequences with each track's clips,
    transitions and markers, all in seconds. sequence limits it to one sequence."""
    return await asyncio.to_thread(host.inspect, sequence, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_transitions(timeout: Timeout = 300) -> Transitions:
    """Every video and audio transition this Premiere offers (QE names), and the short aliases."""
    return await asyncio.to_thread(host.transitions, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_presets() -> Presets:
    """Export presets (.epr: Premiere, Media Encoder and user) and sequence presets (.sqpreset) by name."""
    return await asyncio.to_thread(lambda: {"export": host.presets("export"), "sequence": host.presets("sequence")})


@mcp.tool(annotations=WRITES)
async def premiere_import(files: Annotated[list[str], Field(min_length=1)], bin: str | None = None,
                          timeout: Timeout = 300) -> Import:
    """Import files into a bin (created when missing); the project root when bin is empty."""
    return await asyncio.to_thread(host.import_files, files, bin, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_sequence_new(name: str, clip: str | None = None, preset: str | None = None,
                                bin: str | None = None, timeout: Timeout = 300) -> NewSequence:
    """New empty sequence with the settings of a project item (media path or name) or of a .sqpreset
    (absolute path, or a name premiere_presets lists such as "HD 1080p 25 fps")."""
    return await asyncio.to_thread(host.sequence_new, name, clip, preset, bin, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_clip_place(item: str, at: Seconds, kind: Kind = "video", track: Track = 0,
                              in_point: Seconds | None = None, out_point: Seconds | None = None,
                              mode: Literal["overwrite", "insert"] = "overwrite", sequence: str | None = None,
                              timeout: Timeout = 300) -> Placed:
    """Place a project item (media path or name; a file not yet imported is imported) on a track at a
    time, with optional source in/out. track is 0-based; sequence defaults to the active one."""
    return await asyncio.to_thread(host.clip_place, sequence, item, kind, track, at, in_point, out_point, mode,
                                   timeout)


@mcp.tool(annotations=WRITES)
async def premiere_clip_props(kind: Kind = "video", track: Track = 0, at: Seconds | None = None,
                              position_index: int | None = None,
                              position: tuple[float, float] | None = None, scale: float | None = None,
                              rotation: float | None = None, opacity: float | None = None,
                              volume_db: float | None = None, keyframes: list[Keyframe] | None = None,
                              sequence: str | None = None, timeout: Timeout = 300) -> Props:
    """Motion position (pixels from the top left), scale (percent), rotation (degrees), Opacity (percent)
    and audio Volume (dB) on the clip at time `at` or at clip index position_index. keyframes
    (time in seconds from the clip's start) animate the properties they set and win over the static value."""
    props = {"position": position and list(position), "scale": scale, "rotation": rotation, "opacity": opacity,
             "volume_db": volume_db}
    frames = [{k: (list(v) if isinstance(v, tuple) else v) for k, v in key.model_dump().items() if v is not None}
              for key in keyframes or []]
    return await asyncio.to_thread(host.clip_props, sequence, kind, track, at, position_index, props, frames,
                                   timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_clip_edit(kind: Kind = "video", track: Track = 0, at: Seconds | None = None,
                             position_index: Annotated[int, Field(ge=0)] | None = None, name: str | None = None,
                             trim_start: Seconds | None = None, trim_end: Seconds | None = None,
                             move_to: Seconds | None = None, to_track: Track | None = None,
                             enabled: bool | None = None, new_name: str | None = None,
                             link_with: LinkRef | None = None, unlink: bool = False,
                             remove: Literal["ripple", "lift"] | None = None, keep_linked: bool = False,
                             sequence: str | None = None,
                             timeout: Timeout = 300) -> ClipEdit:
    """Edit the placed clip at time `at`, clip index position_index or clip name on a track. trim_start and
    trim_end are new timeline times (the source in/out follow), move_to is the new start time and to_track
    another track, enabled/new_name set the state and name, link_with links it to another clip, unlink
    unlinks it, remove deletes it and its linked clips unless keep_linked (ripple shifts the later clips of
    every unlocked track left, lift leaves the gap). remove stands alone."""
    edit = {"trim_start": trim_start, "trim_end": trim_end, "move_to": move_to, "to_track": to_track,
            "enabled": enabled, "new_name": new_name, "link_with": link_with and link_with.model_dump(),
            "unlink": unlink or None, "remove": remove, "keep_linked": keep_linked or None}
    return await asyncio.to_thread(host.clip_edit, sequence, kind, track, at, position_index, name, edit, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_razor(times: Annotated[list[Seconds], Field(min_length=1)],
                         kind: Literal["video", "audio", "all"] = "all", track: Track | None = None,
                         sequence: str | None = None, timeout: Timeout = 300) -> Razor:
    """Split clips at each time with the QE razor: every track of `kind`, or one track when `track` is given
    (then kind is video or audio). Times are seconds on the frame grid."""
    return await asyncio.to_thread(host.razor, sequence, times, kind, track, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_clip_speed(kind: Kind = "video", track: Track = 0, at: Seconds | None = None,
                              position_index: Annotated[int, Field(ge=0)] | None = None,
                              speed: Annotated[float, Field(gt=0, le=10000)] | None = None,
                              duration: Annotated[float, Field(gt=0)] | None = None, reverse: bool = False,
                              maintain_pitch: bool = True, ripple: bool = False, sequence: str | None = None,
                              timeout: Timeout = 300) -> Speed:
    """Set a clip's speed in percent, or the timeline duration it should fill in seconds (the source range is
    kept). Reverse plays it backwards, maintain_pitch keeps audio pitch, ripple moves the later clips.
    A clip's linked audio is a separate clip: call it again with kind audio."""
    return await asyncio.to_thread(host.clip_speed, sequence, kind, track, at, position_index, speed, duration,
                                   reverse, maintain_pitch, ripple, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_sequence_set(settings: SequenceSettings | None = None, in_point: Seconds | None = None,
                                out_point: Seconds | None = None, nest: NestSpec | None = None,
                                duplicate: str | None = None, new_name: str | None = None, remove: bool = False,
                                sequence: str | None = None, timeout: Timeout = 300) -> SequenceChange:
    """Change a sequence: settings (frame size, fps, audio rate), in/out points, nest listed clips into a
    new sequence (limited to the in/out range), duplicate (the value names the copy, "" keeps Premiere's
    name), rename, or delete (alone). Applied in that order."""
    change = {"settings": settings and settings.model_dump(), "in_point": in_point, "out_point": out_point,
              "nest": nest and nest.model_dump(), "duplicate": duplicate, "new_name": new_name,
              "remove": remove}
    return await asyncio.to_thread(host.sequence_set, sequence, change, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_tracks(add_video: Annotated[int, Field(ge=0, le=20)] = 0,
                          add_audio: Annotated[int, Field(ge=0, le=20)] = 0, tracks: list[TrackSet] | None = None,
                          sequence: str | None = None, timeout: Timeout = 300) -> Tracks:
    """Add video and stereo audio tracks after the last one, and set mute, lock and target state per track;
    returns the counts before and after and every track's state."""
    states = [t.model_dump() for t in tracks or []]
    return await asyncio.to_thread(host.tracks, sequence, add_video, add_audio, states, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_frame_export(times: Annotated[list[Seconds], Field(min_length=1, max_length=50)], folder: str,
                                prefix: str = "frame", sequence: str | None = None,
                                timeout: Timeout = 300) -> Frames:
    """Export PNG stills of the sequence at the given seconds into a folder and return their paths and
    sizes (open them to look at the result). An existing file of the same name is replaced."""
    return await asyncio.to_thread(host.frame_export, sequence, times, folder, prefix, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_transition_add(transition: str = "Cross Dissolve", frames: Annotated[int, Field(ge=1, le=600)] = 12,
                                  kind: Kind = "video", track: Track = 0, at: Seconds | None = None,
                                  position_index: int | None = None, edge: Literal["start", "end"] = "start",
                                  alignment: Annotated[float, Field(ge=0, le=1)] = 0.5,
                                  single_sided: bool = False, sequence: str | None = None,
                                  timeout: Timeout = 300) -> Added:
    """QE transition (a name premiere_transitions lists, or cross_dissolve, film_dissolve, dip_to_black,
    dip_to_white) at the start or end of the clip at `at` or
    position_index. alignment 0 starts at the cut, 0.5 centers on it, 1 ends at it."""
    return await asyncio.to_thread(host.transition_add, sequence, kind, track, at, position_index, transition,
                                   frames, edge, alignment, single_sided, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_media_replace(item: str, path: str, timeout: Timeout = 300) -> Replaced:
    """Point a project item (media path or name) at a new file, or refresh it when the path is unchanged,
    so sequences show the new media; checks the project through premiere_inspect."""
    return await asyncio.to_thread(host.media_replace, item, path, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_markers_add(markers: list[NewMarker] | None = None, beat_grid: BeatGrid | None = None,
                               sequence: str | None = None, timeout: Timeout = 300) -> Markers:
    """Sequence markers at seconds, and/or one per beat from bpm (named bar.beat, bar starts commented
    "downbeat") between start and end."""
    return await asyncio.to_thread(host.markers_add, sequence, [m.model_dump() for m in markers or []],
                                   beat_grid and beat_grid.model_dump(), timeout)


@mcp.tool(annotations=WRITES)
async def premiere_mogrt_add(mogrt: str, at: Seconds, video_track: Track = 1, audio_track: Track = 0,
                             duration: Annotated[float, Field(gt=0)] | None = None,
                             text: dict[str, str] | None = None, sequence: str | None = None,
                             timeout: Timeout = 300) -> Mogrt:
    """Import a .mogrt on a video track at a time and set its text parameters by name. Only templates
    built in After Effects expose text parameters; native Essential Graphics titles do not."""
    return await asyncio.to_thread(host.mogrt_add, sequence, mogrt, at, video_track, audio_track, duration,
                                   text or {}, timeout)


Range = Literal["entire", "in_out", "work_area"]


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_export(master: str, preset: str | None = None, range: Range = "entire",
                          replace: bool = False, sequence: str | None = None, timeout: Timeout = 1800) -> Export:
    """Export a sequence through exportAsMediaDirect with a preset: an absolute .epr path or a name
    premiere_presets lists (format/name when the name is not unique, e.g. H264/...); default ProRes 422 HQ.
    range is the whole sequence, its in/out points or its work area. Completion is judged by the
    report file, the output released by every process and the ffprobe frame count, not the relay's answer."""
    return await asyncio.to_thread(host.export, sequence, master, preset, range, replace, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_encode(master: str, preset: str | None = None, range: Range = "entire",
                          replace: bool = False, sequence: str | None = None, timeout: Timeout = 1800) -> Export:
    """Queue a sequence in Adobe Media Encoder (started when needed) with a preset (an absolute .epr path or
    a name premiere_presets lists) and start the batch. Premiere stays free; completion is judged by the
    output file, no process holding it open and the ffprobe frame count."""
    return await asyncio.to_thread(host.encode, sequence, master, preset, range, replace, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_auto_reframe(ratio: str, motion: Literal["slower", "default", "faster"] = "default",
                                name: str | None = None, nest: bool = False, sequence: str | None = None,
                                timeout: Timeout = 600) -> Reframed:
    """New sequence at another aspect ratio (width:height, such as 9:16, 1:1 or 4:5) from Auto Reframe,
    with the motion preset; nest puts the clips in nested sequences. Returns the new sequence."""
    return await asyncio.to_thread(host.auto_reframe, sequence, ratio, motion, name, nest, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_interchange(action: Literal["xml", "aaf", "omf", "import_xml"], path: str,
                               replace: bool = False, audio_rate: Annotated[int, Field(ge=8000, le=192000)] = 48000,
                               bits: Literal[16, 24] = 16, sequence: str | None = None,
                               timeout: Timeout = 600) -> Interchange:
    """Export a sequence as FCP XML (xml), AAF or OMF to an absolute path, or import an FCP XML
    (import_xml) into the project; the file or the new sequence is checked. audio_rate and bits
    are for AAF and OMF."""
    return await asyncio.to_thread(host.interchange, sequence, action, path, replace, audio_rate, bits, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_captions(file: str, start: Seconds = 0,
                            format: Literal["subtitle", "608", "708", "teletext", "op42", "op47", "open_ebu"] = "subtitle",
                            sequence: str | None = None, timeout: Timeout = 300) -> Captions:
    """Import an .srt and create a caption track on the sequence from `start` seconds. Returns the caption
    count read from the file. Captions appear in premiere_frame_export stills."""
    return await asyncio.to_thread(host.captions, sequence, file, start, format, timeout)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
