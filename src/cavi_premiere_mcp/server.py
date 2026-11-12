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


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
