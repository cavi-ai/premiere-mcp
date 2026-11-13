"""The server object and the argument types every tool module shares."""

from typing import Annotated, Literal

from cavi_mcp_core.server import Server
from pydantic import Field

mcp = Server("cavi-premiere", package="cavi-premiere-mcp",
             instructions="Premiere Pro, driven through Adobe Bridge BridgeTalk. Paths are absolute.")
Seconds = Annotated[float, Field(ge=0)]
Timeout = Annotated[int, Field(ge=30, le=7200)]
Track = Annotated[int, Field(ge=0)]
Kind = Literal["video", "audio"]
Range = Literal["entire", "in_out", "work_area"]
