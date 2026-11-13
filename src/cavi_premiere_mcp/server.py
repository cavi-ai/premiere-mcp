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
    kind: Literal["cross_dissolve", "film_dissolve", "dip_to_white", "dip_to_black"]
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
                           replace: bool = False, save: bool = False, timeout: Timeout = 300) -> Project:
    """Open, create, save or close a .prproj. new refuses an existing path unless replace; close saves only when save."""
    return await asyncio.to_thread(host.project, action, path, replace, save, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_inspect(sequence: str | None = None, timeout: Timeout = 300) -> Inspect:
    """Bins, project items (media path, offline, duration, fps, size), sequences with each track's clips,
    transitions and markers, all in seconds. sequence limits it to one sequence."""
    return await asyncio.to_thread(host.inspect, sequence, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_import(files: Annotated[list[str], Field(min_length=1)], bin: str | None = None,
                          timeout: Timeout = 300) -> Import:
    """Import files into a bin (created when missing); the project root when bin is empty."""
    return await asyncio.to_thread(host.import_files, files, bin, timeout)


@mcp.tool(annotations=WRITES)
async def premiere_sequence_new(name: str, clip: str | None = None, preset: str | None = None,
                                bin: str | None = None, timeout: Timeout = 300) -> NewSequence:
    """New empty sequence with the settings of a project item (media path or name) or of a .sqpreset
    (absolute path, or a preset's file name without extension such as "HD 1080p 25 fps")."""
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


@mcp.tool(annotations=WRITES)
async def premiere_transition_add(transition: str = "Cross Dissolve", frames: Annotated[int, Field(ge=1, le=600)] = 12,
                                  kind: Kind = "video", track: Track = 0, at: Seconds | None = None,
                                  position_index: int | None = None, edge: Literal["start", "end"] = "start",
                                  alignment: Annotated[float, Field(ge=0, le=1)] = 0.5,
                                  single_sided: bool = False, sequence: str | None = None,
                                  timeout: Timeout = 300) -> Added:
    """QE transition (Premiere's name: Cross Dissolve, Film Dissolve, Dip to Black, Dip to White; audio:
    Constant Power, Constant Gain, Exponential Fade) at the start or end of the clip at `at` or
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


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_export(master: str, preset: str, work_area: Literal["entire", "in_out"] = "entire",
                          replace: bool = False, sequence: str | None = None, timeout: Timeout = 1800) -> Export:
    """Export a sequence with an absolute .epr preset through exportAsMediaDirect. Completion is judged by the
    report file, the output released by every process and the ffprobe frame count, not the relay's answer."""
    return await asyncio.to_thread(host.export, sequence, master, preset, work_area, replace, timeout)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
