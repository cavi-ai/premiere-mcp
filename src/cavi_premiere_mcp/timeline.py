"""Timeline organizing tools: marker edits, gaps, range removal and bins."""

import asyncio
from typing import Annotated, Literal

from cavi_adobe_mcp.contracts import Result
from cavi_mcp_core.server import DESTRUCTIVE
from pydantic import BaseModel, Field

from . import host
from .app import Seconds, SequenceName, Timeout, mcp


def markers_edit(sequence, action, index, at, all_, name, comment, move_to, duration, timeout):
    if action != "list":
        if sum([index is not None, at is not None, bool(all_)]) != 1:
            raise ValueError("Give exactly one of index, at or all")
        if action == "update" and all(v is None for v in (name, comment, move_to, duration)):
            raise ValueError("Give name, comment, move_to or duration")
        if action == "update" and all_ and (move_to is not None):
            raise ValueError("move_to needs one marker, not all")
    args = {"sequence": sequence, "action": action, "index": index, "at": at, "all": all_, "name": name,
            "comment": comment, "move_to": move_to, "duration": duration}
    return host.invoke("markers_edit", args, timeout)


def gaps(sequence, action, min_seconds, leading, timeout):
    return host.invoke("gaps", {"sequence": sequence, "action": action, "min_seconds": min_seconds,
                                "leading": leading}, timeout)


def range_remove(sequence, start, end, mode, timeout):
    if end <= start:
        raise ValueError("end must be after start")
    return host.invoke("range_remove", {"sequence": sequence, "start": start, "end": end, "mode": mode}, timeout)


def bins(action, name, parent, new_name, items, force, timeout):
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


class RangeRemoved(Result):
    sequence: str
    mode: str
    start: float
    end: float
    removed: int
    moved: int
    sequence_end: float


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
        sequence: SequenceName = None, timeout: Timeout = 300) -> MarkersEdited:
    """List sequence markers, or update or delete one of them (by index or at) or all of them."""
    return await asyncio.to_thread(markers_edit, sequence, action, index, at, all, name, comment, move_to,
                                   duration, timeout)


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
        start: Annotated[Seconds, Field(description="Start of the range, in seconds.")],
        end: Annotated[Seconds, Field(description="End of the range, in seconds; after start.")],
        mode: Annotated[Literal["lift", "extract"], Field(description="extract closes the hole; lift leaves it "
                                                                      "empty.")] = "extract",
        sequence: SequenceName = None, timeout: Timeout = 300) -> RangeRemoved:
    """Cut a time range out of every unlocked track: clips are split at both times and the ones inside are
    removed."""
    return await asyncio.to_thread(range_remove, sequence, start, end, mode, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_bins(
        action: Annotated[Literal["create", "rename", "move", "delete"], Field(description="What to do with "
                                                                                           "the bin.")],
        name: Annotated[str | None, Field(description="The bin to create, rename, move items into or "
                                                      "delete.")] = None,
        parent: Annotated[str | None, Field(description="Bin to create inside; the project root when "
                                                        "omitted.")] = None,
        new_name: Annotated[str | None, Field(description="New bin name, for rename.")] = None,
        items: Annotated[list[str] | None, Field(description="Project items to move: media paths or "
                                                             "names.")] = None,
        force: Annotated[bool, Field(description="Delete a bin that holds items, with their clips.")] = False,
        timeout: Timeout = 300) -> Bins:
    """Create, rename or delete a project bin, or move items into it. A bin that holds items is deleted only
    with force, which removes its items and their clips from every sequence."""
    return await asyncio.to_thread(bins, action, name, parent, new_name, items, force, timeout)
