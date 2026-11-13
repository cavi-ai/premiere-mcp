import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from cavi_premiere_mcp import host

JSX = Path(host.__file__).with_name("jsx")
TOOLS = ["project", "inspect", "import", "sequence_new", "clip_place", "clip_props", "transition_add",
         "media_replace", "markers_add", "mogrt_add", "export"]


class BeatGridTest(unittest.TestCase):
    def test_one_marker_per_beat_with_downbeats(self):
        markers = host.beat_grid(120, 4, 1, 5)
        self.assertEqual([m["time"] for m in markers], [1 + 0.5 * n for n in range(8)])
        self.assertEqual([m["name"] for m in markers[:5]], ["1.1", "1.2", "1.3", "1.4", "2.1"])
        self.assertEqual([m["comment"] for m in markers[:5]], ["downbeat", "", "", "", "downbeat"])

    def test_grid_stops_before_end(self):
        self.assertEqual(len(host.beat_grid(90, 3, 0, 2)), 3)

    def test_empty_span_is_refused(self):
        with self.assertRaisesRegex(ValueError, "end must be after start"):
            host.beat_grid(120, 4, 2, 2)


class RefusalTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="premiere-refusal-"))
        self.addCleanup(shutil.rmtree, self.root)

    def test_new_project_keeps_an_existing_file(self):
        project = self.root / "a.prproj"
        project.write_text("kept")
        with self.assertRaisesRegex(ValueError, "pass replace=true"):
            host.project("new", project, False, False, 60)
        self.assertEqual(project.read_text(), "kept")

    def test_open_needs_an_existing_project(self):
        with self.assertRaisesRegex(ValueError, "No file at"):
            host.project("open", self.root / "missing.prproj", False, False, 60)

    def test_export_keeps_an_existing_master(self):
        master, preset = self.root / "m.mov", self.root / "p.epr"
        master.write_text("kept")
        preset.write_text("")
        with self.assertRaisesRegex(ValueError, "pass replace=true"):
            host.export(None, master, preset, "entire", False, 60)
        self.assertEqual(master.read_text(), "kept")

    def test_export_needs_an_epr_preset(self):
        with self.assertRaisesRegex(ValueError, "Expected a .epr file"):
            host.export(None, self.root / "m.mov", self.root / "p.xml", "entire", False, 60)

    def test_replacement_media_must_exist(self):
        with self.assertRaisesRegex(ValueError, "No file at"):
            host.media_replace("a.mov", self.root / "gone.mov", 60)

    def test_sequence_needs_one_source_of_settings(self):
        with self.assertRaisesRegex(ValueError, "exactly one of clip or preset"):
            host.sequence_new("S", None, None, None, 60)
        with self.assertRaisesRegex(ValueError, "exactly one of clip or preset"):
            host.sequence_new("S", "a.mov", "HD 1080p 25 fps", None, 60)

    def test_clip_is_addressed_by_time_or_position(self):
        with self.assertRaisesRegex(ValueError, "exactly one of at or position_index"):
            host.transition_add(None, "video", 0, None, None, "Cross Dissolve", 8, "start", 0.5, False, 60)
        with self.assertRaisesRegex(ValueError, "exactly one of at or position_index"):
            host.clip_props(None, "video", 0, 1.0, 0, {}, [], 60)

    def test_markers_need_content(self):
        with self.assertRaisesRegex(ValueError, "markers or a beat_grid"):
            host.markers_add(None, [], None, 60)


@unittest.skipUnless(shutil.which("node"), "node is required")
class ScriptTest(unittest.TestCase):
    def node(self, code):
        lib = (JSX / "lib.jsx").read_text()
        result = subprocess.run(["node", "-e", lib + code], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_report_text_survives_quotes_backslashes_and_control_characters(self):
        value = {"name": 'a "b" \\ c\n\td e é', "list": [1, 2.5, None, True], "n": {"x": 0}}
        out = self.node(f"process.stdout.write(stringify({json.dumps(value)}))")
        self.assertEqual(json.loads(out), value)

    def test_non_finite_numbers_become_null(self):
        self.assertEqual(json.loads(self.node("process.stdout.write(stringify({a: NaN, b: 1}))")),
                         {"a": None, "b": 1})

    def test_every_tool_script_is_valid_javascript(self):
        for tool in TOOLS:
            with tempfile.TemporaryDirectory() as folder:
                script = Path(folder) / f"{tool}.js"
                script.write_text("\n".join((JSX / name).read_text() for name in ("lib.jsx", f"{tool}.jsx",
                                                                                 "tail.jsx")))
                result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{tool}: {result.stderr}")


@unittest.skipUnless(shutil.which("lsof"), "lsof is required")
class FinishTest(unittest.TestCase):
    """finish judges a job by its report and the released master, whatever the relay answers."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="premiere-finish-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.master, self.report = self.root / "m.mov", self.root / "r.json"
        self.relay = host.relay
        self.addCleanup(setattr, host, "relay", self.relay)

    def writer(self, hold, errors):
        """A process that exports like Premiere: it holds the master, then releases it and writes the report."""
        code = textwrap.dedent(f"""
            import json, time
            with open({str(self.master)!r}, "wb") as f:
                f.write(b"x")
                time.sleep({hold})
            open({str(self.report)!r}, "w").write(json.dumps({{"errors": {errors!r}, "warnings": []}}))
        """)
        return subprocess.Popen([sys.executable, "-c", code])

    def test_timed_out_answer_still_waits_for_the_export(self):
        process = self.writer(3, [])
        self.addCleanup(process.wait)
        host.relay = lambda body, timeout: "timed out"
        started = time.monotonic()
        result = host.finish("", self.report, self.master, 60)
        self.assertEqual(result["errors"], [])
        self.assertGreaterEqual(time.monotonic() - started, 2)
        self.assertFalse(host.held(self.master))

    def test_missing_report_fails_after_the_deadline(self):
        host.relay = lambda body, timeout: "OK"
        with self.assertRaisesRegex(RuntimeError, "Premiere Pro job failed: OK"):
            host.finish("", self.report, self.master, 2)

    def test_script_errors_fail_at_once(self):
        process = self.writer(0, ["boom"])
        self.addCleanup(process.wait)
        host.relay = lambda body, timeout: "ERROR"
        with self.assertRaisesRegex(RuntimeError, "boom"):
            host.finish("", self.report, self.master, 60)


class PresetTest(unittest.TestCase):
    @unittest.skipUnless(sorted(Path("/Applications").glob("Adobe Premiere Pro 20*")), "Premiere Pro is required")
    def test_preset_name_resolves_to_its_file(self):
        found = Path(host.sequence_preset("HD 1080p 25 fps"))
        self.assertEqual((found.name, found.is_file()), ("HD 1080p 25 fps.sqpreset", True))


if __name__ == "__main__":
    unittest.main()
