import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = {"premiere_status", "premiere_bridge_install", "premiere_script", "premiere_cut", "premiere_project", "premiere_inspect",
         "premiere_import", "premiere_sequence_new", "premiere_clip_place", "premiere_clip_props",
         "premiere_transition_add", "premiere_media_replace", "premiere_markers_add", "premiere_mogrt_add",
         "premiere_export", "premiere_transitions", "premiere_presets", "premiere_clip_edit", "premiere_razor",
         "premiere_clip_speed", "premiere_sequence_set", "premiere_tracks", "premiere_frame_export", "premiere_encode",
         "premiere_auto_reframe", "premiere_interchange", "premiere_captions", "premiere_effects",
         "premiere_effect_add", "premiere_effect_set", "premiere_clip_fit", "premiere_items",
         "premiere_scene_detect", "premiere_markers_edit", "premiere_gaps", "premiere_range_remove",
         "premiere_bins", "premiere_fade", "premiere_find", "premiere_clip_copy",
         "premiere_color", "premiere_clip_slip"}


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

    async def test_every_tool_explains_its_inputs(self):
        params = StdioServerParameters(command=sys.executable, args=["-m", "cavi_premiere_mcp.server"])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as client:
            await client.initialize()
            for tool in (await client.list_tools()).tools:
                self.assertGreaterEqual(len(tool.description.strip()), 40, tool.name)
                for name, schema in tool.input_schema.get("properties", {}).items():
                    with self.subTest(tool=tool.name, parameter=name):
                        self.assertTrue(schema.get("description", "").strip())

    async def test_new_tools_refuse_bad_input_before_touching_premiere(self):
        params = StdioServerParameters(command=sys.executable, args=["-m", "cavi_premiere_mcp.server"])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as client:
            await client.initialize()
            for name, args, text in [
                ("premiere_export", {"master": "m.mov", "preset": "/p.epr"}, "absolute path"),
                ("premiere_project", {"action": "new", "path": "p.prproj"}, "absolute path"),
                ("premiere_sequence_new", {"name": "S"}, "exactly one of clip or preset"),
                ("premiere_markers_add", {}, "markers or a beat_grid"),
                ("premiere_clip_props", {"scale": 50}, "exactly one of at or position_index"),
                ("premiere_clip_edit", {"enabled": False}, "exactly one of at, position_index or name"),
                ("premiere_clip_edit", {"position_index": 0}, "at least one edit"),
                ("premiere_clip_speed", {"position_index": 0}, "exactly one of speed or duration"),
                ("premiere_sequence_set", {}, "at least one change"),
                ("premiere_auto_reframe", {"ratio": "square"}, "width:height"),
                ("premiere_interchange", {"action": "aaf", "path": "a.aaf"}, "absolute path"),
                ("premiere_encode", {"master": "m.mov"}, "absolute path"),
                ("premiere_captions", {"file": "c.srt"}, "absolute path"),
                ("premiere_effect_set", {"position_index": 0, "list": False}, "params to set or list=true"),
                ("premiere_effect_add", {"effect": "Crop"}, "exactly one of at, position_index or name"),
                ("premiere_clip_fit", {}, "exactly one of at, position_index or name"),
                ("premiere_items", {"item": "a.mov"}, "at least one change"),
                ("premiere_scene_detect", {}, "exactly one of at, position_index or name"),
                ("premiere_tracks", {}, "tracks to add or track states"),
                ("premiere_frame_export", {"times": [1], "folder": "frames"}, "absolute path"),
            ]:
                reply = await client.call_tool(name, args)
                self.assertTrue(reply.is_error, name)
                self.assertIn(text, reply.content[0].text, name)
            reply = await client.call_tool("premiere_transition_add", {"at": 1, "frames": 0})
            self.assertTrue(reply.is_error)


if __name__ == "__main__":
    unittest.main()
