"""Failures that used to crash a call, hang it or return a wrong success, each shown through the real code."""

import json
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

from cavi_premiere_mcp import clip_tools, host

JSX = Path(host.__file__).with_name("jsx")


def reached_the_app(*args, **kwargs):
    raise AssertionError("the call reached Premiere")


NODE_FILES = """
var fs = require("fs");
function File(path) { this.fsName = path; this.name = path.split("/").pop(); this.exists = true; this.text = ""; }
File.prototype.open = function () { return true; };
File.prototype.write = function (text) { this.text += text; };
File.prototype.close = function () { fs.writeFileSync(this.fsName, this.text); };
"""

TWO_SEQUENCES = """
var ProjectItemType = {BIN: 1, ROOT: 2, CLIP: 3};
var item = {name: "a.mp4", type: 3, nodeId: "m", getMediaPath: function () { return "/m/a.mp4"; },
    getColorLabel: function () { return 0; }, isOffline: function () { return false; },
    getProjectMetadata: function () { return ""; },
    getInPoint: function () { return {seconds: 0}; }, getOutPoint: function () { return {seconds: 3}; },
    setInPoint: function () {}, setOutPoint: function () {}};
function placed(source, at) {
    return {name: source.name, start: {seconds: at}, end: {seconds: at + 3}, inPoint: {seconds: 0},
        outPoint: {seconds: 3}, projectItem: source};
}
function sequence(name, id) {
    var lane = {name: "V1", transitions: {numItems: 0}, clips: {numItems: 1, 0: placed(item, 0)},
        overwriteClip: function (source, at) { this.clips[this.clips.numItems++] = placed(source, at); }};
    return {name: name, sequenceID: id, projectItem: {nodeId: "s" + id}, timebase: "10160640000", end: "0",
        frameSizeHorizontal: 1920, frameSizeVertical: 1080, markers: {getFirstMarker: function () { return null; }},
        videoTracks: {numTracks: 1, 0: lane}, audioTracks: {numTracks: 0}};
}
var first = sequence("First", "1"), active = sequence("Active", "2");
var app = {project: {path: "/p.prproj", rootItem: {type: 2, children: {numItems: 1, 0: item}},
    sequences: {numSequences: 2, 0: first, 1: active}, activeSequence: active,
    openSequence: function (id) { this.activeSequence = id === "1" ? first : active; }}};
"""


def node_relay(stub):
    """A relay that runs each job in node against a stubbed Premiere and answers as the Bridge relay does."""
    def relay(body, timeout):
        script = NODE_FILES + stub + f"\nprocess.stdout.write(String(eval({json.dumps(body)})));"
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout
    return relay


@unittest.skipUnless(shutil.which("node"), "node is required")
class ActiveSequenceTest(unittest.TestCase):
    def test_a_copy_without_a_sequence_goes_to_the_active_one(self):
        with mock.patch.object(host, "relay", node_relay(TWO_SEQUENCES)):
            copied = clip_tools.copy(None, "video", 0, 1.0, None, 5.0, None, 60)
        self.assertEqual((copied["sequence"], copied["clip"]["start"]), ("Active", 5))

    def test_a_cut_closes_only_a_project_open_at_its_path(self):
        script = NODE_FILES + """
var closed = [];
function project(path) { return {path: path, closeDocument: function () { closed.push(path); }}; }
var app = {projects: {numProjects: 2, 0: project("/work/edit.prproj"), 1: project("/cuts/cut.prproj")},
    newProject: function () { return false; }};
""" + (JSX / "lib.jsx").read_text() + (JSX / "cut.jsx").read_text() + """
try { run({project: "/cuts/cut.prproj", clips: []}, {warnings: [], errors: []}); } catch (error) {}
process.stdout.write(JSON.stringify(closed));"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["/cuts/cut.prproj"])


SHARED_NAMES = """
var ProjectItemType = {BIN: 1, ROOT: 2, CLIP: 3};
function item(name, id, path) {
    return {name: name, type: 3, nodeId: id, getMediaPath: function () { return path; },
        getColorLabel: function () { return 0; }, isOffline: function () { return false; },
        getProjectMetadata: function () { return ""; },
        getInPoint: function () { return {seconds: 0}; }, getOutPoint: function () { return {seconds: 3}; },
        setInPoint: function () {}, setOutPoint: function () {}};
}
var a = item("a.mp4", "i1", "/m/a.mp4"), b = item("b.mp4", "i2", "/m/b.mp4"), copy = item("b take", "i3", "/m/b.mp4");
function sequence(name, id) {
    var lane = {name: "V1", transitions: {numItems: 0}, clips: {numItems: 0},
        overwriteClip: function (source, at) {
            require("fs").appendFileSync(PLACED, name + " " + source.name + " " + at + "\\n");
            this.clips[this.clips.numItems++] = {name: source.name, start: {seconds: at}, end: {seconds: at + 3},
                inPoint: {seconds: 0}, outPoint: {seconds: 3}, projectItem: source};
        }};
    return {name: name, sequenceID: id, projectItem: {nodeId: "p" + id}, timebase: "10160640000", end: "0",
        frameSizeHorizontal: 1920, frameSizeVertical: 1080, markers: {getFirstMarker: function () { return null; }},
        videoTracks: {numTracks: 1, 0: lane}, audioTracks: {numTracks: 0}};
}
var main = sequence("Main", "s1"), dup = sequence("Dup", "s2"), other = sequence("Dup", "s3");
var app = {project: {path: "/p.prproj", rootItem: {type: 2, children: {numItems: 3, 0: a, 1: b, 2: copy}},
    sequences: {numSequences: 3, 0: main, 1: dup, 2: other}, activeSequence: main,
    openSequence: function (id) { this.activeSequence = {s1: main, s2: dup, s3: other}[id]; }}};
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class AddressingTest(unittest.TestCase):
    """Sequences and project items are found by id or by a reference only one of them answers to."""

    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="premiere-addressing-"))
        self.addCleanup(shutil.rmtree, folder)
        self.placed = folder / "placed.txt"
        self.placed.write_text("")
        self.jobs = 0
        relay = node_relay(f"var PLACED = {json.dumps(str(self.placed))};" + SHARED_NAMES)

        def counted(body, timeout):
            self.jobs += 1
            return relay(body, timeout)

        patch = mock.patch.object(host, "relay", counted)
        patch.start()
        self.addCleanup(patch.stop)

    def placements(self):
        return self.placed.read_text().splitlines()

    def test_a_sequence_is_found_by_its_id(self):
        self.assertEqual([s["id"] for s in host.inspect("s3", 60)["sequences"]], ["s3"])
        host.clip_place("s3", "/m/a.mp4", "video", 0, 2.0, None, None, "overwrite", 60)
        self.assertEqual(self.placements(), ["Dup a.mp4 2"])

    def test_a_name_two_sequences_share_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "2 sequences match Dup; give one of their ids: s2, s3"):
            host.clip_place("Dup", "/m/a.mp4", "video", 0, 2.0, None, None, "overwrite", 60)
        with self.assertRaisesRegex(ValueError, "2 sequences match Dup; give one of their ids: s2, s3"):
            clip_tools.fade("Dup", "video", 0, 1.0, None, 1, 0, 60)
        self.assertEqual(self.placements(), [])

    def test_a_project_item_is_found_by_its_id(self):
        listed = host.inspect(None, 60)
        self.assertEqual([(i["name"], i["id"]) for i in listed["items"]],
                         [("a.mp4", "i1"), ("b.mp4", "i2"), ("b take", "i3")])
        placed = host.clip_place(None, "i3", "video", 0, 4.0, None, None, "overwrite", 60)
        self.assertEqual(placed["clip"]["name"], "b take")
        self.assertEqual(self.placements(), ["Main b take 4"])

    def test_a_media_path_two_items_share_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "2 project items match /m/b.mp4; give one of their ids: i2, i3"):
            host.clip_place(None, "/m/b.mp4", "video", 0, 0.0, None, None, "overwrite", 60)
        self.assertEqual(self.placements(), [])

    def test_many_clips_are_placed_in_one_job(self):
        placed = host.clips_place("s1", [
            {"item": "/m/a.mp4", "at": 0.0, "kind": "video", "track": 0, "in_point": None, "out_point": None,
             "mode": "overwrite"},
            {"item": "i2", "at": 3.0, "kind": "video", "track": 0, "in_point": 0.5, "out_point": 2.0,
             "mode": "overwrite"}], 60)
        self.assertEqual(self.jobs, 1)
        self.assertEqual((placed["sequence"], [c["start"] for c in placed["clips"]]), ("Main", [0, 3]))
        self.assertEqual(self.placements(), ["Main a.mp4 0", "Main b.mp4 3"])

    def test_a_batch_with_a_missing_track_places_nothing(self):
        with self.assertRaisesRegex(RuntimeError, "No video track 2"):
            host.clips_place(None, [
                {"item": "i1", "at": 0.0, "kind": "video", "track": 0, "in_point": None, "out_point": None,
                 "mode": "overwrite"},
                {"item": "i1", "at": 3.0, "kind": "video", "track": 2, "in_point": None, "out_point": None,
                 "mode": "overwrite"}], 60)
        self.assertEqual(self.placements(), [])

    def test_clip_place_with_clips_takes_missing_fields_from_the_call(self):
        def entry(item, at, track=None):
            return {"item": item, "at": at, "kind": None, "track": track, "in_point": None, "out_point": None,
                    "mode": None}

        with self.assertRaisesRegex(RuntimeError, "No video track 2"):
            host.place("s1", None, None, "video", 2, None, None, "overwrite", [entry("i1", 0.0)], 60)
        placed = host.place("s1", None, None, "video", 2, None, None, "overwrite",
                            [entry("i1", 0.0, 0), entry("i2", 3.0, 0)], 60)
        self.assertEqual((self.jobs, [c["name"] for c in placed["clips"]]), (2, ["a.mp4", "b.mp4"]))
        self.assertEqual(self.placements(), ["Main a.mp4 0", "Main b.mp4 3"])
        with self.assertRaisesRegex(ValueError, "Give item and at, or clips"):
            host.place(None, "i1", None, "video", 0, None, None, "overwrite", [], 60)

    def test_a_copy_places_the_clips_own_item_when_its_file_is_imported_twice(self):
        placed_take = ("main.videoTracks[0].clips = {numItems: 1, 0: {name: 'b take', start: {seconds: 0}, "
                       "end: {seconds: 3}, inPoint: {seconds: 0}, outPoint: {seconds: 3}, projectItem: copy}};")
        stub = f"var PLACED = {json.dumps(str(self.placed))};" + SHARED_NAMES + placed_take
        with mock.patch.object(host, "relay", node_relay(stub)):
            copied = clip_tools.copy("s1", "video", 0, 1.0, None, 5.0, None, 60)
        self.assertEqual((copied["clip"]["name"], copied["clip"]["item_id"]), ("b take", "i3"))
        self.assertEqual(self.placements(), ["Main b take 5"])

    def test_a_clip_placed_off_the_frame_grid_is_found_on_the_frame_it_landed(self):
        snapped = ("var overwrite = main.videoTracks[0].overwriteClip; main.videoTracks[0].overwriteClip = "
                   "function (source, at) { overwrite.call(this, source, Math.round(at * 25) / 25); };")
        stub = f"var PLACED = {json.dumps(str(self.placed))};" + SHARED_NAMES + snapped
        with mock.patch.object(host, "relay", node_relay(stub)):
            placed = host.clip_place("s1", "i1", "video", 0, 5.015, None, None, "overwrite", 60)
        self.assertEqual((placed["clip"]["name"], placed["clip"]["start"]), ("a.mp4", 5.0))
        self.assertEqual(self.placements(), ["Main a.mp4 5"])

    def test_sequence_open_makes_the_sequence_active(self):
        self.assertEqual(host.sequence_open("s2", 60)["id"], "s2")

    def test_inspect_can_leave_out_items_and_tracks(self):
        listed = host.inspect(None, 60, items=False, tracks=False)
        self.assertEqual(listed["items"], [])
        self.assertEqual([(s["id"], s["active"], s["video"]) for s in listed["sequences"]],
                         [("s1", True, []), ("s2", False, []), ("s3", False, [])])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is required")
@unittest.skipUnless(shutil.which("lsof"), "lsof is required")
class KeptUntilCheckedTest(unittest.TestCase):
    """Old outputs stay until every check that can refuse the call has passed; a written master is counted."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="premiere-kept-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.preset = self.root / "p.epr"
        self.preset.write_text("")

    def movie(self, name, source):
        path = self.root / name
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", source, str(path)], check=True)
        return path

    def exported(self, made):
        """A relay that writes the master and the report as export.jsx does: one second at 25 fps."""
        def relay(body, timeout):
            args = json.loads(body.split("\n", 1)[0].removeprefix("var CAVI_ARGS = ").removesuffix(";"))
            shutil.copyfile(made, args["master"])
            Path(args["report"]).write_text(json.dumps({"errors": [], "warnings": [], "sequence": "S", "span": 1,
                                                        "fps": 25}))
            return "OK"
        return relay

    def test_cut_keeps_the_old_project_and_master_without_a_prores_preset(self):
        clip = self.movie("a.mov", "color=c=red:s=64x36:r=25:d=1")
        old = [self.root / name for name in ("cut.prproj", "cut.mov", "cut.report.json")]
        for path in old:
            path.write_text("kept")
        gone = {"CAVI_PREMIERE_APP": "/nonexistent/Premiere.app"}
        with mock.patch.dict(os.environ, gone), mock.patch.object(host, "relay", reached_the_app):
            with self.assertRaisesRegex(ValueError, "not an application"):
                host.cut(old[0], old[1], [{"file": str(clip), "start": 0, "in_point": 0, "out_point": 1}], None,
                         True, 60)
        self.assertEqual([path.read_text() for path in old], ["kept"] * 3)

    def test_encode_keeps_the_old_master_without_media_encoder(self):
        master = self.root / "m.mov"
        master.write_text("kept")
        gone = {"CAVI_MEDIA_ENCODER_APP": "/nonexistent/Encoder.app"}
        with mock.patch.dict(os.environ, gone), mock.patch.object(host, "relay", reached_the_app):
            with self.assertRaisesRegex(ValueError, "not an application"):
                host.encode(None, master, self.preset, "entire", True, 60)
        self.assertEqual(master.read_text(), "kept")

    def test_a_master_whose_container_keeps_no_frame_count_is_counted(self):
        with mock.patch.object(host, "relay", self.exported(self.movie("made.mkv", "color=c=red:s=64x36:r=25:d=1"))):
            result = host.export(None, self.root / "m.mkv", self.preset, "entire", False, 60)
        self.assertEqual((result["frames"], result["expected_frames"], result["complete"]), (25, 25, True))

    def test_a_master_without_video_is_judged_by_its_audio(self):
        with mock.patch.object(host, "relay", self.exported(self.movie("made.wav", "sine=d=1:r=48000"))):
            result = host.export(None, self.root / "m.wav", self.preset, "entire", False, 60)
        self.assertEqual((result["frames"], result["expected_frames"], result["complete"]), (25, 25, True))


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
