"""The server object and the argument types every tool module shares."""

from typing import Annotated, Literal

from cavi_mcp_core.server import Server
from pydantic import Field

mcp = Server("cavi-premiere", package="cavi-premiere-mcp",
             instructions="Premiere Pro, driven through Adobe Bridge BridgeTalk. Paths are absolute.")
Seconds = Annotated[float, Field(ge=0)]
Timeout = Annotated[int, Field(ge=30, le=7200, description="Seconds to wait before the call fails.")]
Track = Annotated[int, Field(ge=0)]
Kind = Literal["video", "audio"]
Range = Literal["entire", "in_out", "work_area"]

# Parameters of the tools that act on one sequence or one placed clip.
SequenceName = Annotated[str | None, Field(description="Sequence name; the active one when omitted.")]
ClipKind = Annotated[Kind, Field(description="Track type of the clip.")]
ClipTrack = Annotated[Track, Field(description="0-based track of the clip; 0 is V1 or A1.")]
ClipAt = Annotated[Seconds | None, Field(description="The clip under this sequence time, in seconds.")]
ClipIndex = Annotated[Annotated[int, Field(ge=0)] | None, Field(description="The clip by 0-based order on the track.")]
