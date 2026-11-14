"""Drive the real server over stdio against Premiere Pro: the README first cut."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]).resolve()
CUT = json.loads((HERE / "cut.json").read_text())
STEPS = [
    ("premiere_cut", {"project": str(ROOT / "cut.prproj"), "master": str(ROOT / "master.mov"),
                      "clips": [{**clip, "file": str(HERE / clip["file"])} for clip in CUT["clips"]],
                      "audio": str(HERE / CUT["audio"]), "replace": True}),
    ("premiere_project", {"action": "open", "path": str(ROOT / "cut.prproj")}),
    ("premiere_inspect", {}),
    ("premiere_frame_export", {"times": [1.5, 3, 4.5, 7.5], "folder": str(ROOT / "frames")}),
    ("premiere_project", {"action": "close"}),
]


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "cavi_premiere_mcp.server"])
    async with stdio_client(params) as (r, w), ClientSession(r, w, read_timeout_seconds=1800) as client:
        await client.initialize()
        for name, arguments in STEPS:
            reply = await client.call_tool(name, arguments)
            body = reply.structured_content if not reply.is_error else reply.content[0].text
            print(name, "ERROR" if reply.is_error else "ok", json.dumps(body), flush=True)
            if reply.is_error:
                sys.exit(1)


asyncio.run(main())
