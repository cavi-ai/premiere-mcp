"""Clip tools built on the project snapshot: fades, find, copy."""

import asyncio
from typing import Annotated, Literal

from cavi_adobe_mcp.contracts import Result
from cavi_mcp_core.server import DESTRUCTIVE, READ_ONLY
from pydantic import BaseModel, Field

from . import host
from .app import ClipAt, ClipIndex, ClipKind, ClipTrack, Seconds, SequenceName, Timeout, Track, mcp

SILENT_DB = -96


def snapshot(sequence, timeout):
    """The project and the one sequence's tracks, in seconds."""
    listed = host.inspect(sequence, timeout)
    if not listed["sequences"]:
        raise ValueError(f"No sequence {sequence}" if sequence else "The project has no sequence")
    return listed, listed["sequences"][0]


def clip_at(sequence_info, kind, track, at, position_index):
    lanes = sequence_info[kind]
    if track >= len(lanes):
        raise ValueError(f"No {kind} track {track} (the sequence has {len(lanes)})")
    clips = lanes[track]["clips"]
    if position_index is not None:
        if position_index >= len(clips):
            raise ValueError(f"No clip at position {position_index} on {kind} track {track} ({len(clips)} clips)")
        return clips[position_index]
    for clip in clips:
        if clip["start"] - 0.0005 <= at < clip["end"] - 0.0005:
            return clip
    raise ValueError(f"No clip on {kind} track {track} at {at} s")


def fade_keys(kind, length, fade_in, fade_out):
    """Opacity (video) or volume (audio) keyframes, in seconds from the clip's start."""
    if not fade_in and not fade_out:
        raise ValueError("Give fade_in or fade_out")
    if fade_in + fade_out > length + 0.0005:
        raise ValueError(f"The fades ({fade_in + fade_out} s) are longer than the clip ({length} s)")
    low, high = (0, 100) if kind == "video" else (SILENT_DB, 0)
    name = "opacity" if kind == "video" else "volume_db"
    keys = []
    if fade_in:
        keys += [{"time": 0, name: low}, {"time": fade_in, name: high}]
    if fade_out:
        keys += [{"time": length - fade_out, name: high}, {"time": length, name: low}]
    return keys


def fade(sequence, kind, track, at, position_index, fade_in, fade_out, timeout):
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    _, info = snapshot(sequence, timeout)
    clip = clip_at(info, kind, track, at, position_index)
    keys = fade_keys(kind, clip["end"] - clip["start"], fade_in, fade_out)
    props = {"position": None, "scale": None, "rotation": None, "opacity": None, "volume_db": None}
    return host.clip_props(sequence, kind, track, at, position_index, props, keys, timeout)


def find(sequence, query, scope, offline_only, unused_only, timeout):
    return search(host.inspect(None, timeout), sequence, query, scope, offline_only, unused_only)


def search(listed, sequence, query, scope, offline_only, unused_only):
    needle = (query or "").lower()
    clips = []
    for info in listed["sequences"]:
        if sequence and info["name"] != sequence:
            continue
        for kind in ("video", "audio"):
            for lane_index, lane in enumerate(info[kind]):
                for position, clip in enumerate(lane["clips"]):
                    clips.append({"sequence": info["name"], "kind": kind, "track": lane_index,
                                  "position": position, "name": clip["name"], "start": clip["start"],
                                  "end": clip["end"], "media_path": clip.get("media_path")})
    used = {clip["media_path"] for clip in clips if clip["media_path"]}
    items = [{"name": item["name"], "bin": item["bin"], "kind": item["kind"], "media_path": item["media_path"],
              "offline": bool(item["offline"]), "used": item["media_path"] in used}
             for item in listed["items"] if item["kind"] != "sequence"]
    hit = [i for i in items if needle in i["name"].lower() or needle in (i["media_path"] or "").lower()]
    if offline_only:
        hit = [i for i in hit if i["offline"]]
    if unused_only:
        hit = [i for i in hit if not i["used"]]
    found_clips = [c for c in clips if needle in c["name"].lower() or needle in (c["media_path"] or "").lower()]
    if offline_only or unused_only:
        found_clips = []
    return {"items": hit if scope in ("items", "both") else [],
            "clips": found_clips if scope in ("clips", "both") else []}


def copy(sequence, kind, track, at, position_index, to_time, to_track, timeout):
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    listed, info = snapshot(sequence, timeout)
    clip = clip_at(info, kind, track, at, position_index)
    if not clip.get("media_path"):
        raise ValueError(f"{clip['name']} has no media to copy")
    return host.clip_place(info["name"], clip["media_path"], kind, track if to_track is None else to_track,
                           to_time, clip["in_point"], clip["out_point"], "overwrite", timeout)


def slip(sequence, kind, track, at, position_index, offset, in_point, with_linked, timeout):
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    if (offset is None) == (in_point is None):
        raise ValueError("Give exactly one of offset or in_point")
    if in_point is not None and in_point < 0:
        raise ValueError("in_point cannot be negative")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "offset": offset, "in_point": in_point, "with_linked": with_linked}
    return host.invoke("clip_slip", args, timeout)


class Slipped(Result):
    sequence: str
    clip: str
    before: dict
    after: dict
    start: float
    end: float
    linked: int


LUMETRI = (("exposure", "Exposure"), ("contrast", "Contrast"), ("highlights", "Highlights"),
           ("shadows", "Shadows"), ("whites", "Whites"), ("blacks", "Blacks"), ("temperature", "Temperature"),
           ("tint", "Tint"), ("saturation", "Saturation"), ("vibrance", "Vibrance"))


def color(sequence, track, at, position_index, values, timeout):
    """Set Lumetri Color basic parameters on a video clip, adding the effect when the clip lacks it."""
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    given = {key: value for key, value in values.items() if value is not None}
    if not given:
        raise ValueError("Give at least one color value")
    present = host.effect_set(sequence, "video", track, at, position_index, None, 0, True, [], timeout)
    if not any(c["name"] == "Lumetri Color" for c in present["components"]):
        host.effect_add(sequence, "video", track, at, position_index, "Lumetri Color", timeout)
    specs = [{"name": name, "value": given[key]} for key, name in LUMETRI if key in given]
    return host.effect_set(sequence, "video", track, at, position_index, "Lumetri Color", 0, False, specs, timeout)


class Colored(Result):
    clip: str
    applied: dict


class Faded(Result):
    clip: str
    keyframes: dict


class Item(BaseModel):
    name: str
    bin: str
    kind: str
    media_path: str | None
    offline: bool
    used: bool


class Placed(BaseModel):
    sequence: str
    kind: str
    track: int
    position: int
    name: str
    start: float
    end: float
    media_path: str | None


class Found(Result):
    items: list[Item]
    clips: list[Placed]


class Copied(Result):
    sequence: str
    clip: dict


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_fade(
        fade_in: Annotated[Seconds, Field(description="Fade-in length at the clip's start, in seconds.")] = 0,
        fade_out: Annotated[Seconds, Field(description="Fade-out length at the clip's end, in seconds.")] = 0,
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Faded:
    """Fade a clip in and out with keyframes: opacity 0 to 100 percent (video) or volume silent to 0 dB
    (audio)."""
    return await asyncio.to_thread(fade, sequence, kind, track, at, position_index, fade_in, fade_out, timeout)


@mcp.tool(annotations=READ_ONLY)
async def premiere_find(
        query: Annotated[str, Field(description="Text the name or media path contains; everything when "
                                                "empty.")] = "",
        scope: Annotated[Literal["items", "clips", "both"], Field(description="Search project items, placed "
                                                                              "clips or both.")] = "both",
        offline_only: Annotated[bool, Field(description="Only items whose media is missing.")] = False,
        unused_only: Annotated[bool, Field(description="Only items placed on no sequence.")] = False,
        sequence: Annotated[str | None, Field(description="Search the clips of this sequence only; every "
                                                          "sequence when omitted.")] = None,
        timeout: Timeout = 300) -> Found:
    """Find project items and placed clips whose name or media path contains the query."""
    return await asyncio.to_thread(find, sequence, query, scope, offline_only, unused_only, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_clip_copy(
        to_time: Annotated[Seconds, Field(description="Sequence time where the copy starts, in seconds.")],
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        to_track: Annotated[Track | None, Field(description="0-based track for the copy; the clip's own when "
                                                            "omitted.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Copied:
    """Place another copy of a clip (same media and source range) on a track of the same kind. The copy
    overwrites what is there and does not carry effects."""
    return await asyncio.to_thread(copy, sequence, kind, track, at, position_index, to_time, to_track, timeout)


Grade = Annotated[float, Field(ge=-100, le=100)]


def grade(name):
    return Annotated[Grade | None, Field(description=f"Lumetri {name}, -100 to 100.")]


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_color(
        exposure: Annotated[Annotated[float, Field(ge=-5, le=5)] | None,
                            Field(description="Lumetri Exposure in stops, -5 to 5.")] = None,
        contrast: grade("Contrast") = None, highlights: grade("Highlights") = None,
        shadows: grade("Shadows") = None, whites: grade("Whites") = None, blacks: grade("Blacks") = None,
        temperature: grade("Temperature") = None, tint: grade("Tint") = None,
        saturation: Annotated[Annotated[float, Field(ge=0, le=200)] | None,
                              Field(description="Lumetri Saturation, 0 to 200; 100 is neutral.")] = None,
        vibrance: grade("Vibrance") = None,
        track: Annotated[Track, Field(description="0-based video track index of the clip; 0 is V1.")] = 0,
        at: ClipAt = None, position_index: ClipIndex = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Colored:
    """Basic color correction on a video clip with Lumetri Color, added when the clip has none."""
    values = {"exposure": exposure, "contrast": contrast, "highlights": highlights, "shadows": shadows,
              "whites": whites, "blacks": blacks, "temperature": temperature, "tint": tint,
              "saturation": saturation, "vibrance": vibrance}
    return await asyncio.to_thread(color, sequence, track, at, position_index, values, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_clip_slip(
        offset: Annotated[float | None, Field(description="Seconds to shift the source in point; positive shows "
                                                          "later footage.")] = None,
        in_point: Annotated[Seconds | None, Field(description="New source in point, in seconds.")] = None,
        kind: ClipKind = "video", track: ClipTrack = 0, at: ClipAt = None, position_index: ClipIndex = None,
        with_linked: Annotated[bool, Field(description="Slip the linked clips too.")] = True,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Slipped:
    """Slip a clip: show a different part of its source while its place and length on the timeline stay.
    A slip past the end of the media is undone and reported."""
    return await asyncio.to_thread(slip, sequence, kind, track, at, position_index, offset, in_point, with_linked,
                                   timeout)
