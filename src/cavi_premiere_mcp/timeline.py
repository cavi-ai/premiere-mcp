"""Timeline organizing tools: marker edits, gaps, range removal and bins."""

import asyncio
from typing import Annotated, Literal

from cavi_mcp_core.server import DESTRUCTIVE, WRITES, reject_foreign
from pydantic import BaseModel, ConfigDict, Field

from . import host
from .app import ClipAt, ClipIndex, Seconds, SequenceName, Timeout, Track, mcp
from .models import MarkerColor, MarkerType, Result, web_link

MAX_RANGES = 500

MARKERS_EDIT_USES = {"list": set(), "update": {"index", "at", "all", "name", "comment", "move_to", "duration",
                                               "color", "type", "url"},
                     "delete": {"index", "at", "all"}}
BINS_USES = {"create": {"parent"}, "rename": {"new_name"}, "move": {"items"}, "delete": {"force"}}


def markers_edit(sequence, action, index, at, all_, name, comment, move_to, duration, timeout, color=None,
                 type_=None, url=None):
    changes = {"name": name, "comment": comment, "move_to": move_to, "duration": duration, "color": color,
               "type": type_, "url": url}
    reject_foreign(action, {"index": index, "at": at, "all": all_ or None, **changes}, MARKERS_EDIT_USES[action])
    if action != "list":
        if sum([index is not None, at is not None, bool(all_)]) != 1:
            raise ValueError("Give exactly one of index, at or all")
        if action == "update" and all(v is None for v in changes.values()):
            raise ValueError("Give name, comment, move_to, duration, color or type")
        if action == "update" and all_ and (move_to is not None):
            raise ValueError("move_to needs one marker, not all")
        if action == "update" and (type_ is not None or url is not None):
            web_link(type_, url)
    args = {"sequence": sequence, "action": action, "index": index, "at": at, "all": all_, **changes}
    return host.invoke("markers_edit", args, timeout)


def gaps(sequence, action, min_seconds, leading, timeout):
    return host.invoke("gaps", {"sequence": sequence, "action": action, "min_seconds": min_seconds,
                                "leading": leading}, timeout)


def range_remove(sequence, start, end, mode, timeout, ranges=None):
    """One range from start and end, or every entry of ranges in one job, in timeline order; range times are
    the timeline's before anything is removed."""
    if ranges:
        if start is not None or end is not None:
            raise ValueError("Give start and end, or ranges, not both")
    elif start is None or end is None:
        raise ValueError("Give start and end, or ranges")
    else:
        ranges = [{"start": start, "end": end}]
    ranges = sorted(({"start": r["start"], "end": r["end"]} for r in ranges), key=lambda r: r["start"])
    for earlier, later in zip([None, *ranges], ranges):
        if later["end"] <= later["start"]:
            raise ValueError(f"end must be after start ({later['start']}-{later['end']} s)")
        if earlier and later["start"] < earlier["end"]:
            raise ValueError(f"The ranges {earlier['start']}-{earlier['end']} s and {later['start']}-{later['end']} s "
                             "overlap")
    return host.invoke("range_remove", {"sequence": sequence, "ranges": ranges, "mode": mode}, timeout)


def silence(sequence, track, at, position_index, noise_db, min_seconds, pad, apply, timeout):
    """The silences of a placed audio clip as timeline seconds, pad seconds shorter at each end and none
    shorter than a frame; optionally marked, or cut out of every unlocked track in one job."""
    host.one_clip(at, position_index)
    with host.exclusive(timeout):
        listed = host.inspect(sequence, timeout, items=False)["sequences"]
        clip = host.video_clip(listed, sequence, track, at, position_index, "audio")
        frame = 1 / host.single_sequence(listed, sequence)["fps"]
        first, last, ratio = clip["in_point"], clip["out_point"], clip["speed"] / 100

        def placed(t):  # source seconds to timeline seconds, from the out point when the clip plays backwards
            return clip["start"] + ((last - t) if clip["reversed"] else (t - first)) / ratio

        found = []
        for a, b in host.silence_ranges(clip["media_path"], noise_db, min_seconds, timeout, first, last):
            start, end = sorted((placed(a), placed(b)))
            start, end = round(start + pad, 3), round(end - pad, 3)
            if end - start >= frame:
                found.append({"start": start, "end": end})
        found.sort(key=lambda r: r["start"])
        result = {"clip": clip["name"], "silences": found, "applied": apply}
        if found and apply == "markers":
            result["markers"] = host.markers_add(sequence, [{"time": r["start"], "name": "silence", "comment": "",
                                                             "duration": round(r["end"] - r["start"], 3)}
                                                            for r in found], None, timeout)["total"]
        elif found and apply in ("lift", "extract"):
            cut = range_remove(sequence, None, None, apply, timeout, found)
            result.update(silences=cut["ranges"], removed=cut["removed"], moved=cut["moved"],
                          sequence_end=cut["sequence_end"])
        return result


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def transcript(sequence, track, at, position_index, model, language, srt, captions, timeout):
    """The speech of a placed audio clip as segments and words in timeline seconds, through the clip's speed and
    direction; optionally written as an .srt and imported as captions."""
    host.one_clip(at, position_index)
    if captions and not srt:
        raise ValueError("captions needs srt")
    target = host.absolute(srt, ".srt") if srt else None
    model = host.speech_model(model)
    host.speech_tool(model)
    with host.exclusive(timeout):
        listed = host.inspect(sequence, timeout, items=False)["sequences"]
        clip = host.video_clip(listed, sequence, track, at, position_index, "audio")
        first, last, ratio = clip["in_point"], clip["out_point"], clip["speed"] / 100

        def placed(t):  # clip-relative source seconds to timeline seconds
            return clip["start"] + ((last - first - t) if clip["reversed"] else t) / ratio

        spoken = host.transcribe(clip["media_path"], first, last, model, language, timeout)
        segments, words = [], []
        for part in spoken.get("segments", []):
            start, end = sorted((placed(part["start"]), placed(part["end"])))
            segments.append({"start": round(start, 3), "end": round(end, 3), "text": part["text"].strip()})
            for word in part.get("words", []):
                start, end = sorted((placed(word["start"]), placed(word["end"])))
                words.append({"start": round(start, 3), "end": round(end, 3), "word": word["word"].strip()})
        segments.sort(key=lambda s: s["start"])
        words.sort(key=lambda w: w["start"])
        result = {"clip": clip["name"], "language": spoken.get("language", language or ""), "segments": segments,
                  "words": words}
        if target:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("".join(f"{n}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text']}\n\n"
                                      for n, s in enumerate(segments, 1)), encoding="utf-8")
            result["srt"] = str(target)
            if captions:
                result["captions"] = host.captions(sequence, target, 0, "subtitle", timeout)["captions"] if segments \
                    else 0
        return result


def bins(action, name, parent, new_name, items, force, timeout):
    reject_foreign(action, {"parent": parent, "new_name": new_name, "items": items or None, "force": force or None},
                   BINS_USES[action])
    if action == "create" and not name:
        raise ValueError("Give the new bin's name")
    if action in ("rename", "move", "delete") and not name:
        raise ValueError(f"Give the bin to {action}")
    if action == "rename" and not new_name:
        raise ValueError("Give new_name")
    if action == "move" and not items:
        raise ValueError("Give items to move")
    refs = [host.item_ref(i) for i in items or []]
    return host.invoke("bins", {"action": action, "name": name, "parent": parent, "new_name": new_name,
                                "items": refs, "force": force}, timeout)


class MarkerRow(BaseModel):
    index: int
    name: str
    comment: str
    start: float
    end: float
    color: int | None = None
    type: str | None = None
    url: str | None = None


class MarkersEdited(Result):
    sequence: str
    total: int
    markers: list[MarkerRow] | None = None
    updated: list[MarkerRow] | None = None
    deleted: int | None = None


class Gap(BaseModel):
    start: float
    end: float


class Gaps(Result):
    sequence: str
    gaps: list[Gap]
    closed: int | None = None
    moved: int | None = None
    remaining: int | None = None


class Span(BaseModel):
    """One range of a ranges list."""

    model_config = ConfigDict(extra="forbid")
    start: Seconds
    end: Seconds


class RangeRemoved(Result):
    sequence: str
    mode: str
    start: float
    end: float
    ranges: list[Gap]
    removed: int
    moved: int
    sequence_end: float


class Silences(Result):
    clip: str
    silences: list[Gap]
    applied: str
    markers: int | None = None
    removed: int | None = None
    moved: int | None = None
    sequence_end: float | None = None


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Word(BaseModel):
    start: float
    end: float
    word: str


class Transcript(Result):
    clip: str
    language: str
    segments: list[Segment]
    words: list[Word]
    srt: str | None = None
    captions: int | None = None


class BinInfo(BaseModel):
    name: str
    parent: str | None = None
    children: int | None = None


class Deleted(BaseModel):
    name: str
    items: int


class Bins(Result):
    action: str
    bin: BinInfo | None = None
    moved: list[str] | None = None
    deleted: Deleted | None = None


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_markers_edit(
        action: Annotated[Literal["list", "update", "delete"], Field(description="What to do with the "
                                                                                 "markers.")],
        index: Annotated[Annotated[int, Field(ge=0)] | None,
                         Field(description="Picks a marker by its 0-based place in time order.")] = None,
        at: Annotated[Seconds | None, Field(description="Picks the marker that starts at this time, in "
                                                        "seconds.")] = None,
        all: Annotated[bool, Field(description="Act on every marker.")] = False,
        name: Annotated[str | None, Field(description="New marker name.")] = None,
        comment: Annotated[str | None, Field(description="New marker comment.")] = None,
        move_to: Annotated[Seconds | None, Field(description="New start time, in seconds.")] = None,
        duration: Annotated[Seconds | None, Field(description="New duration, in seconds.")] = None,
        color: Annotated[MarkerColor | None, Field(description="New color index, 0 to 7.")] = None,
        type: Annotated[MarkerType | None, Field(description="New marker type; weblink needs url.")] = None,
        url: Annotated[str | None, Field(description="Link of a weblink marker; give with type weblink.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> MarkersEdited:
    """List sequence markers with their color and type, or update or delete one of them (by index or at) or
    all of them."""
    return await asyncio.to_thread(markers_edit, sequence, action, index, at, all, name, comment, move_to,
                                   duration, timeout, color, type, url)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_gaps(
        action: Annotated[Literal["list", "close"], Field(description="List the gaps or close them.")] = "list",
        min_seconds: Annotated[Seconds, Field(description="Ignore gaps shorter than this, in seconds.")] = 0,
        leading: Annotated[bool, Field(description="Include the space before the first clip.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 300) -> Gaps:
    """List or close gaps: time ranges with no clip on any unlocked track. close moves every later clip left,
    last gap first, so tracks stay in sync."""
    return await asyncio.to_thread(gaps, sequence, action, min_seconds, leading, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_range_remove(
        start: Annotated[Seconds | None, Field(description="Start of the range, in seconds.")] = None,
        end: Annotated[Seconds | None, Field(description="End of the range, in seconds; after start.")] = None,
        mode: Annotated[Literal["lift", "extract"], Field(description="extract closes the hole; lift leaves it "
                                                                      "empty.")] = "extract",
        ranges: Annotated[Annotated[list[Span], Field(max_length=MAX_RANGES)] | None,
                          Field(description="Several ranges instead of start and end, cut in one job; their "
                                            "times are the timeline's before anything is removed.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> RangeRemoved:
    """Cut a time range out of every unlocked track, or many with ranges in one job: clips are split at both
    times and the ones inside are removed."""
    return await asyncio.to_thread(range_remove, sequence, start, end, mode, timeout,
                                   [r.model_dump() for r in ranges or []])


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_silence(
        track: Annotated[Track, Field(description="0-based audio track index of the clip; 0 is A1.")] = 0,
        at: ClipAt = None, position_index: ClipIndex = None,
        noise_db: Annotated[float, Field(ge=-90, le=0, description="Audio quieter than this is silent, in "
                                                                   "dBFS.")] = -35,
        min_seconds: Annotated[float, Field(gt=0, le=60, description="Shortest silence found, in "
                                                                     "seconds.")] = 0.5,
        pad: Annotated[float, Field(ge=0, le=5, description="Seconds of silence kept at each end of a "
                                                            "silence.")] = 0.1,
        apply: Annotated[Literal["report", "markers", "lift", "extract"],
                         Field(description="report only, add a marker per silence, or cut the silences out of "
                                           "every unlocked track in one job: lift leaves the holes, extract "
                                           "closes them.")] = "report",
        sequence: SequenceName = None, timeout: Timeout = 600) -> Silences:
    """Find the silences in a placed audio clip from its media and return them as timeline seconds; optionally
    mark them or cut them out."""
    return await asyncio.to_thread(silence, sequence, track, at, position_index, noise_db, min_seconds, pad, apply,
                                   timeout)


@mcp.tool(annotations=WRITES)
async def premiere_transcript(
        track: Annotated[Track, Field(description="0-based audio track index of the clip; 0 is A1.")] = 0,
        at: ClipAt = None, position_index: ClipIndex = None,
        model: Annotated[str | None, Field(description="Whisper model name (tiny, base, small, medium, large, "
                                                       "turbo and variants), or an absolute path to a local model "
                                                       "folder, run with mlx-audio. CAVI_WHISPER_MODEL, else "
                                                       "base, when omitted.")] = None,
        language: Annotated[str | None, Field(description="Spoken language code, such as en; detected when "
                                                         "omitted.")] = None,
        srt: Annotated[str | None, Field(description="Absolute path of an .srt to write from the segments, in "
                                                     "timeline seconds.")] = None,
        captions: Annotated[bool, Field(description="Import the .srt as a caption track; needs srt.")] = False,
        sequence: SequenceName = None, timeout: Timeout = 1800) -> Transcript:
    """Transcribe a placed audio clip with local whisper and return segments and words as timeline seconds;
    optionally write an .srt and import it as captions. Word times feed premiere_range_remove ranges."""
    return await asyncio.to_thread(transcript, sequence, track, at, position_index, model, language, srt, captions,
                                   timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_bins(
        action: Annotated[Literal["create", "rename", "move", "delete"], Field(description="What to do with "
                                                                                           "the bin.")],
        name: Annotated[str | None, Field(description="The bin to create, rename, move items into or "
                                                      "delete.")] = None,
        parent: Annotated[str | None, Field(description="Bin to create inside; the project root when "
                                                        "omitted.")] = None,
        new_name: Annotated[str | None, Field(description="New bin name, for rename.")] = None,
        items: Annotated[list[str] | None, Field(description="Project items to move: ids, media paths or "
                                                             "names.")] = None,
        force: Annotated[bool, Field(description="Delete a bin that holds items, with their clips.")] = False,
        timeout: Timeout = 300) -> Bins:
    """Create, rename or delete a project bin, or move items into it. A bin that holds items is deleted only
    with force, which removes its items and their clips from every sequence."""
    return await asyncio.to_thread(bins, action, name, parent, new_name, items, force, timeout)
