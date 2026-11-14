"""Failures that used to crash a call, hang it or return a wrong success, each shown through the real code."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cavi_premiere_mcp import host

JSX = Path(host.__file__).with_name("jsx")


def reached_the_app(*args, **kwargs):
    raise AssertionError("the call reached Premiere")


class ProtocolFailureTest(unittest.IsolatedAsyncioTestCase):
    async def test_open_without_a_path_names_the_missing_argument(self):
        params = StdioServerParameters(command=sys.executable, args=["-m", "cavi_premiere_mcp.server"],
                                       env=dict(os.environ))
        async with stdio_client(params) as (r, w), ClientSession(r, w) as client:
            await client.initialize()
            for action in ("open", "new"):
                reply = await client.call_tool("premiere_project", {"action": action})
                self.assertTrue(reply.is_error)
                self.assertIn(f"path is required for action={action}", reply.content[0].text)


class RefusedBeforeAppTest(unittest.TestCase):
    def test_infinite_and_nan_numbers_never_reach_the_script(self):
        with mock.patch.object(host, "relay", reached_the_app):
            for value in (float("inf"), float("nan")):
                with self.assertRaisesRegex(ValueError, "finite"):
                    host.invoke("razor", {"times": [value]})

    def test_a_frame_prefix_cannot_leave_the_folder(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(host, "relay", reached_the_app):
            for prefix in ("../x", "a/b", "", ".."):
                with self.assertRaisesRegex(ValueError, "prefix"):
                    host.frame_export(None, [1.0], folder, prefix, 60)

    def test_a_beat_grid_too_large_for_premiere_is_refused(self):
        with self.assertRaisesRegex(ValueError, "limit is 5000"):
            host.beat_grid(1000, 4, 0, 3600)
        with mock.patch.object(host, "relay", reached_the_app):
            with self.assertRaisesRegex(ValueError, "limit is 5000"):
                host.markers_add(None, [{"time": 0}] * 5001, None, 60)


class StatusTest(unittest.TestCase):
    def test_a_missing_application_is_reported_not_raised(self):
        gone = {"CAVI_PREMIERE_APP": "/nonexistent/Premiere.app", "CAVI_BRIDGE_APP": "/nonexistent/Bridge.app",
                "CAVI_MEDIA_ENCODER_APP": "/nonexistent/Encoder.app"}
        with mock.patch.dict(os.environ, gone):
            found = host.status()
        for name in ("premiere", "bridge", "media_encoder"):
            self.assertIsNone(found[name]["app"])
            self.assertIn("not an application", found[name]["error"])
        self.assertIsNone(found["prores_preset"])

    def test_presets_are_listed_without_premiere(self):
        with mock.patch.dict(os.environ, {"CAVI_PREMIERE_APP": "/nonexistent/Premiere.app"}):
            found = host.all_presets()
        self.assertEqual(set(found), {"export", "sequence"})
        self.assertEqual([p for kind in found.values() for p in kind if p["source"] == "premiere"], [])


class SceneDetectTest(unittest.TestCase):
    def inspected(self, sequences):
        return mock.patch.object(host, "inspect", lambda sequence, timeout: {"sequences": sequences})

    def test_an_empty_project_is_a_clear_error(self):
        with self.inspected([]):
            with self.assertRaisesRegex(ValueError, "no sequence"):
                host.scene_detect(None, 0, 1.0, None, 0.3, "report", False, 60)

    def test_a_missing_track_or_position_is_a_clear_error(self):
        lane = {"index": 0, "name": "V1", "clips": [], "transitions": []}
        with self.inspected([{"name": "S", "video": [lane], "audio": []}]):
            with self.assertRaisesRegex(ValueError, "No video track 3"):
                host.scene_detect(None, 3, 1.0, None, 0.3, "report", False, 60)
            with self.assertRaisesRegex(ValueError, "No clip at position 2"):
                host.scene_detect(None, 0, None, 2, 0.3, "report", False, 60)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_an_unreadable_movie_is_an_error_not_an_empty_list(self):
        with tempfile.TemporaryDirectory() as folder:
            movie = Path(folder) / "broken.mov"
            movie.write_text("not a movie")
            with self.assertRaisesRegex(RuntimeError, "ffmpeg could not read"):
                host.scene_times(movie, 0.3)


class RelayFailureTest(unittest.TestCase):
    def test_a_job_that_cannot_start_fails_at_once_with_its_cause(self):
        def cannot_start(body, timeout):
            raise RuntimeError("Adobe Bridge did not launch: no such application")

        with mock.patch.object(host, "relay", cannot_start):
            started = time.monotonic()
            with self.assertRaisesRegex(RuntimeError, "did not launch"):
                host.finish("", Path(tempfile.gettempdir()) / "no-report.json", Path("/nonexistent/m.mov"), 5)
            self.assertLess(time.monotonic() - started, 2)

    def test_a_script_that_throws_is_a_tool_error(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "throws.jsx"
            script.write_text("throw new Error('boom');")
            with mock.patch.object(host, "relay", lambda body, timeout: host.FAILED + "Error: boom"):
                with self.assertRaisesRegex(RuntimeError, "Premiere script failed: Error: boom"):
                    host.run_script(script, {}, None, 60)

    def test_mailbox_files_of_calls_that_are_gone_are_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            box = Path(folder)
            stale, fresh = box / "old.reply", box / "new.reply"
            stale.write_text("ok\nlate answer")
            fresh.write_text("ok\nanswer for a running call")
            week = time.time() - 7 * 24 * 3600
            os.utime(stale, (week, week))
            with self.assertRaises(host.NotReady):
                host.mailbox_send("premierepro", "'ready'", 5, wait=0.1, box=box)
            self.assertFalse(stale.exists())
            self.assertTrue(fresh.exists())


@unittest.skipUnless(shutil.which("node"), "node is required")
class ReportWriterTest(unittest.TestCase):
    def run_tool(self, writable):
        """tail.jsx on a File whose open() succeeds or fails, as ExtendScript's does."""
        harness = f"""
        var written = null;
        function File(path) {{
            this.path = path;
            this.open = function () {{ return {str(writable).lower()}; }};
            this.write = function (text) {{ written = text; return true; }};
            this.close = function () {{ return true; }};
        }}
        var CAVI_ARGS = {{report: "/report.json"}};
        function run(A, report) {{}}
        """
        text = harness + (JSX / "lib.jsx").read_text() + (JSX / "tail.jsx").read_text()
        result = subprocess.run(["node", "-e", f"process.stdout.write(String(eval({text!r})))"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_a_report_that_cannot_be_written_is_an_error_answer(self):
        self.assertEqual(self.run_tool(True), "OK")
        self.assertRegex(self.run_tool(False), "^ERROR Cannot write the report")


class SlowBridgeTest(unittest.TestCase):
    """A Bridge that started moments ago is loading, not missing its approval."""

    def relay_after(self, age, answers):
        sends = iter(answers)

        def send(body, timeout, target="premierepro", wait=None):
            answer = next(sends)
            if isinstance(answer, Exception):
                raise answer
            return answer

        patches = [mock.patch.object(host, name, value) for name, value in (
            ("bridge", lambda: Path("/b.app")), ("premiere", lambda: Path("/p.app")), ("running", lambda app: [1]),
            ("start", lambda app: None), ("bridge_age", lambda app: age), ("send", send),
            ("send_file", lambda body, timeout, target: "done"), ("sleep", None))
            if name != "sleep"]
        with mock.patch.object(host.time, "sleep", lambda seconds: None):
            for patch in patches:
                patch.start()
                self.addCleanup(patch.stop)
            return host.relay("1", 30)

    def test_a_young_bridge_is_waited_for(self):
        self.assertEqual(self.relay_after(20, [host.NotReady(host.APPROVAL), "ready"]), "done")

    def test_an_old_bridge_that_stays_silent_asks_for_approval(self):
        with self.assertRaisesRegex(host.NotReady, "approve it in Bridge"):
            self.relay_after(900, [host.NotReady(host.APPROVAL)])
