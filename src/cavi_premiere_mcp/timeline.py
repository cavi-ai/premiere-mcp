"""Timeline organizing tools: marker edits, gaps, range removal and bins."""

import asyncio
from typing import Annotated, Literal

from cavi_mcp_core.contracts import Result
from cavi_mcp_core.server import DESTRUCTIVE
from pydantic import BaseModel, Field

from . import host
from .server import Seconds, Timeout, mcp


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
async def premiere_markers_edit(action: Literal["list", "update", "delete"], index: Annotated[int, Field(ge=0)] | None = None,
                                at: Seconds | None = None, all: bool = False, name: str | None = None,
                                comment: str | None = None, move_to: Seconds | None = None,
                                duration: Seconds | None = None, sequence: str | None = None,
                                timeout: Timeout = 300) -> MarkersEdited:
    """List sequence markers, or update or delete one (by time-order index or start time) or all of them.
    update sets name, comment, a new start (move_to) or a duration."""
    return await asyncio.to_thread(markers_edit, sequence, action, index, at, all, name, comment, move_to,
                                   duration, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_gaps(action: Literal["list", "close"] = "list", min_seconds: Seconds = 0, leading: bool = False,
                        sequence: str | None = None, timeout: Timeout = 300) -> Gaps:
    """List or close empty gaps: time ranges with no clip on any unlocked track. close moves every later clip
    left (last gap first) so tracks stay in sync; leading includes the space before the first clip."""
    return await asyncio.to_thread(gaps, sequence, action, min_seconds, leading, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_range_remove(start: Seconds, end: Seconds, mode: Literal["lift", "extract"] = "extract",
                                sequence: str | None = None, timeout: Timeout = 300) -> RangeRemoved:
    """Cut a time range out of every unlocked track: clips are split at both times and the ones inside are
    removed. extract also moves later clips left to close the hole; lift leaves it empty."""
    return await asyncio.to_thread(range_remove, sequence, start, end, mode, timeout)


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_bins(action: Literal["create", "rename", "move", "delete"], name: str | None = None,
                        parent: str | None = None, new_name: str | None = None, items: list[str] | None = None,
                        force: bool = False, timeout: Timeout = 300) -> Bins:
    """Organize project bins: create (inside parent, else the root), rename, move items (media path or name)
    into a bin, or delete a bin (refused when it holds items unless force)."""
    return await asyncio.to_thread(bins, action, name, parent, new_name, items, force, timeout)
