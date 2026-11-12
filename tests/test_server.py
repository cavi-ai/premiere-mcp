import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = {"premiere_status", "premiere_script", "premiere_cut"}


class ProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_and_refused_relative_paths(self):
        params = StdioServerParameters(command=sys.executable, args=["-m", "cavi_premiere_mcp.server"])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as client:
            await client.initialize()
            catalog = {tool.name: tool for tool in (await client.list_tools()).tools}
            self.assertEqual(set(catalog), TOOLS)
            for tool in catalog.values():
                self.assertTrue(tool.output_schema["required"], tool.name)
            reply = await client.call_tool("premiere_cut", {
                "project": "cut.prproj", "master": "/m.mov",
                "clips": [{"file": "/a.mov", "start": 0, "in_point": 0, "out_point": 1}]})
            self.assertTrue(reply.is_error)
            self.assertIn("absolute path", reply.content[0].text)
            reply = await client.call_tool("premiere_cut", {
                "project": "/cut.prproj", "master": "/m.mov",
                "clips": [{"file": "/a.mov", "start": 0, "in_point": 0, "out_point": 1, "speed": 2}]})
            self.assertTrue(reply.is_error)


if __name__ == "__main__":
    unittest.main()
