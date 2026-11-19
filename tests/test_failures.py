"""Failures that used to crash a call, hang it or return a wrong success, each shown through the real code."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from cavi_mcp_core.contracts import failure
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError

from cavi_premiere_mcp import clip_tools, host
from cavi_premiere_mcp.server import mcp

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


def refusal(name, arguments):
    """The error the server sends for a call that fails before it reaches Premiere, and its message."""
    try:
        asyncio.run(mcp.call_tool(name, arguments))
    except ToolError as error:
        return failure(name, error).structured_content["error"], str(error)
    raise AssertionError(f"{name} succeeded")


class ContractTest(unittest.TestCase):
    """Arguments, missing inputs and an unapproved relay reach the caller as the error contract says."""

    real_relay = staticmethod(host.relay)

    def setUp(self):
        patch = mock.patch.object(host, "relay", reached_the_app)
        patch.start()
        self.addCleanup(patch.stop)

    def test_an_argument_the_call_does_not_use_is_refused(self):
        for name, arguments, text in [
            ("premiere_project", {"action": "save", "close_others": True}, "Not valid for action=save: close_others"),
            ("premiere_project", {"action": "save", "replace": True}, "replace needs path"),
            ("premiere_project", {"action": "close", "close_others": True}, "Not valid for action=close: close_others"),
            ("premiere_project", {"action": "open", "path": "/x.prproj", "replace": True},
             "Not valid for action=open: replace"),
            ("premiere_interchange", {"action": "xml", "path": "/a.xml", "bits": 24}, "Not valid for action=xml: bits"),
            ("premiere_interchange", {"action": "import_xml", "path": "/a.xml", "replace": True},
             "Not valid for action=import_xml: replace"),
            ("premiere_markers_edit", {"action": "list", "index": 0}, "Not valid for action=list: index"),
            ("premiere_markers_edit", {"action": "delete", "all": True, "name": "x"}, "Not valid for action=delete: name"),
            ("premiere_bins", {"action": "create", "name": "B", "items": ["a"]}, "Not valid for action=create: items"),
            ("premiere_bins", {"action": "rename", "name": "B", "new_name": "C", "force": True},
             "Not valid for action=rename: force"),
            ("premiere_clip_edit", {"position_index": 0, "enabled": False, "keep_linked": True},
             "keep_linked needs remove"),
            ("premiere_scene_detect", {"position_index": 0, "include_audio": True}, "include_audio needs apply=cuts"),
            ("premiere_effect_set", {"position_index": 0, "component": "Opacity", "list": True,
                                     "params": [{"name": "Opacity", "value": 50}]}, "list=true, not both"),
            ("premiere_effect_set", {"position_index": 0, "component": "Gaussian Blur", "remove": True, "list": True},
             "remove takes no params or list"),
            ("premiere_transition_add", {"position_index": 0, "remove": True, "frames": 8},
             "Not valid for action=remove: frames"),
            ("premiere_markers_edit", {"action": "update", "index": 0, "url": "https://x.test"},
             "type weblink needs url"),
            ("premiere_markers_edit", {"action": "update", "index": 0, "type": "weblink"}, "type weblink needs url"),
            ("premiere_clip_props", {"position_index": 0, "pan": 20}, "pan is for audio clips"),
            ("premiere_tracks", {"tracks": [{"kind": "video", "track": 0, "volume_db": -6}]},
             "volume_db is for audio tracks"),
        ]:
            with self.subTest(name=name, arguments=arguments):
                error, message = refusal(name, arguments)
                self.assertIn(text, message)
                self.assertEqual((error["code"], error["outcome"]), ("INVALID_ARGUMENT", "rejected"))

    def test_static_opacity_and_volume_take_the_keyframe_ranges(self):
        for arguments in ({"opacity": 150}, {"opacity": -1}, {"volume_db": 40}, {"volume_db": -200}):
            with self.subTest(arguments=arguments):
                error, message = refusal("premiere_clip_props", {"position_index": 0, **arguments})
                self.assertIn(next(iter(arguments)), message)
                self.assertEqual((error["code"], error["outcome"]), ("INVALID_ARGUMENT", "rejected"))

    def test_a_missing_input_file_is_not_found(self):
        for name, arguments in [("premiere_media_replace", {"item": "a", "path": "/nonexistent/x.mov"}),
                                ("premiere_project", {"action": "open", "path": "/nonexistent/p.prproj"}),
                                ("premiere_captions", {"file": "/nonexistent/c.srt"})]:
            with self.subTest(name=name):
                error, message = refusal(name, arguments)
                self.assertIn("/nonexistent/", message)
                self.assertEqual((error["code"], error["outcome"]), ("INPUT_NOT_FOUND", "rejected"))

    def test_a_relay_bridge_never_ran_is_rejected_as_not_approved(self):
        with tempfile.TemporaryDirectory() as box:
            patches = [mock.patch.object(host, name, value) for name, value in (
                ("relay", self.real_relay), ("MAILBOX", Path(box)), ("BRIDGE_PING", 0.2), ("bridge", lambda: Path("/b.app")),
                ("premiere", lambda: Path("/p.app")), ("running", lambda app: [1]), ("start", lambda app: None),
                ("bridge_age", lambda app: 900))]
            for patch in patches:
                patch.start()
                self.addCleanup(patch.stop)
            error, message = refusal("premiere_inspect", {})
        self.assertIn("approve it in Bridge", message)
        self.assertEqual((error["code"], error["outcome"]), ("RELAY_NOT_APPROVED", "rejected"))

    def test_result_fields_a_tool_did_not_set_stay_off_the_wire(self):
        with tempfile.TemporaryDirectory() as folder:
            placed = Path(folder) / "placed.txt"
            stub = f"var PLACED = {json.dumps(str(placed))};" + SHARED_NAMES
            with mock.patch.object(host, "relay", node_relay(stub)):
                reply = asyncio.run(mcp.call_tool("premiere_clip_place", {"item": "i1", "at": 0, "sequence": "s1"}))
        self.assertFalse(reply.is_error)
        self.assertEqual(reply.structured_content["clip"]["name"], "a.mp4")
        self.assertNotIn("clips", reply.structured_content)


@unittest.skipUnless(shutil.which("node"), "node is required")
class OneCallAtATimeTest(unittest.TestCase):
    def test_two_copies_at_once_never_interleave_their_jobs(self):
        relay, jobs = node_relay(TWO_SEQUENCES), []

        def slow(body, timeout):
            args = json.loads(body.split("\n", 1)[0].removeprefix("var CAVI_ARGS = ").removesuffix(";"))
            jobs.append(("place" if "clips" in args else "inspect", args["sequence"]))
            time.sleep(0.3)
            return relay(body, timeout)

        start = threading.Barrier(2)

        def copy(sequence):
            start.wait()
            clip_tools.copy(sequence, "video", 0, 1.0, None, 5.0, None, 60)

        with mock.patch.object(host, "relay", slow):
            workers = [threading.Thread(target=copy, args=(s,)) for s in ("1", "2")]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
        self.assertEqual(len(jobs), 4)
        self.assertEqual((jobs[0][1], jobs[2][1]), (jobs[1][1], jobs[3][1]), jobs)


RIPPLE = """
function Time() { this.ticks = "0"; }
function lane(name, clips) {
    var made = {name: name, items: [], isLocked: function () { return false; }};
    Object.defineProperty(made, "clips", {get: function () {
        var list = {numItems: made.items.length}, i;
        for (i = 0; i < made.items.length; i++) { list[i] = made.items[i]; }
        return list;
    }});
    clips.forEach(function (c) {
        made.items.push({name: c[0], nodeId: c[0], start: {seconds: c[1]}, end: {seconds: c[2]},
            inPoint: {seconds: 0}, outPoint: {seconds: c[2] - c[1]}, disabled: false,
            getLinkedItems: function () { return null; },
            remove: function () {
                require("fs").appendFileSync(EDITS, "remove " + this.name + "\\n");
                made.items.splice(made.items.indexOf(this), 1);
            },
            move: function (t) {
                var by = Number(t.ticks) / 254016000000;
                require("fs").appendFileSync(EDITS, "move " + this.name + " " + by + "\\n");
                this.start = {seconds: this.start.seconds + by};
                this.end = {seconds: this.end.seconds + by};
            }});
    });
    return made;
}
var main = {name: "Main", sequenceID: "s1", projectItem: {nodeId: "p1"}, timebase: "10160640000", end: "0",
    videoTracks: {numTracks: 2, 0: lane("V1", [["A", 0, 2], ["B", 2, 4], ["C", 4, 6]]), 1: lane("V2", V2)},
    audioTracks: {numTracks: 0}};
var app = {project: {path: "/p.prproj", rootItem: {type: 2, children: {numItems: 0}},
    sequences: {numSequences: 1, 0: main}, activeSequence: main, openSequence: function () {}}};
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class RippleTest(unittest.TestCase):
    """A ripple remove shifts the later clips of every unlocked track by the removed clip's length."""

    def remove_b(self, v2):
        with tempfile.TemporaryDirectory() as folder:
            edits = Path(folder) / "edits.txt"
            edits.write_text("")
            stub = f"var EDITS = {json.dumps(str(edits))}, V2 = {json.dumps(v2)};" + RIPPLE
            with mock.patch.object(host, "relay", node_relay(stub)):
                try:
                    return host.clip_edit("s1", "video", 0, None, None, "B", {"remove": "ripple"}, 60), \
                        edits.read_text().splitlines()
                except RuntimeError as error:
                    return str(error), edits.read_text().splitlines()

    def test_a_ripple_that_would_overlap_a_clip_on_another_track_is_refused(self):
        refused, edits = self.remove_b([["X", 0, 5], ["Y", 5, 8]])
        self.assertIn("would move Y onto X", refused)
        self.assertEqual(edits, [])

    def test_a_ripple_with_room_on_every_track_moves_the_later_clips(self):
        done, edits = self.remove_b([["X", 0, 3], ["Y", 6, 8]])
        self.assertEqual(done["removed"]["name"], "B")
        self.assertEqual(edits, ["remove B", "move C -2", "move Y -2"])


MARKERS = """
function log(line) { require("fs").appendFileSync(EDITS, line + "\\n"); }
function Marker(time) {
    var end = {seconds: time};
    this.name = ""; this.comments = ""; this.start = {seconds: time}; this.type = "Comment"; this.color = 0;
    this.link = "";
    Object.defineProperty(this, "end", {get: function () { return end; },
        set: function (value) { end = {seconds: Number(value)}; }});
}
Marker.prototype.setColorByIndex = function (i) { this.color = i; log("color " + i); };
Marker.prototype.getColorByIndex = function () { return this.color; };
Marker.prototype.setTypeAsComment = function () { this.type = "Comment"; log("type Comment"); };
Marker.prototype.setTypeAsChapter = function () { this.type = "Chapter"; log("type Chapter"); };
Marker.prototype.setTypeAsSegmentation = function () { this.type = "Segmentation"; log("type Segmentation"); };
Marker.prototype.setTypeAsWebLink = function (url) { this.type = "WebLink"; this.link = url; log("type WebLink " + url); };
Marker.prototype.getWebLinkURL = function () { return this.link; };
var list = SEED.map(function (s) {
    var m = new Marker(s.t);
    m.color = s.color || 0; m.type = s.type || "Comment"; m.link = s.link || "";
    return m;
});
var markers = {
    createMarker: function (time) {
        var m = new Marker(time);
        list.push(m);
        list.sort(function (a, b) { return a.start.seconds - b.start.seconds; });
        return m;
    },
    deleteMarker: function (m) { list.splice(list.indexOf(m), 1); },
    getFirstMarker: function () { return list[0] || null; },
    getNextMarker: function (m) { return list[list.indexOf(m) + 1] || null; }};
Object.defineProperty(markers, "numMarkers", {get: function () { return list.length; }});
var main = {name: "Main", sequenceID: "s1", projectItem: {nodeId: "p1"}, timebase: "10160640000", end: "0",
    markers: markers, videoTracks: {numTracks: 0}, audioTracks: {numTracks: 0}};
var app = {project: {path: "/p.prproj", rootItem: {type: 2, children: {numItems: 0}},
    sequences: {numSequences: 1, 0: main}, activeSequence: main, openSequence: function () {}}};
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class MarkerStyleTest(unittest.TestCase):
    """Markers take a color and a type, list them, and keep them when moved."""

    def run_markers(self, seed, call):
        with tempfile.TemporaryDirectory() as folder:
            edits = Path(folder) / "edits.txt"
            edits.write_text("")
            stub = f"var EDITS = {json.dumps(str(edits))}, SEED = {json.dumps(seed)};" + MARKERS
            with mock.patch.object(host, "relay", node_relay(stub)):
                return call(), edits.read_text().splitlines()

    def test_added_markers_take_their_color_and_type(self):
        _, edits = self.run_markers([], lambda: host.markers_add("s1", [
            {"time": 1, "color": 3, "type": "chapter"}, {"time": 2, "type": "weblink", "url": "https://x.test"}],
            None, 60))
        self.assertEqual(edits, ["color 3", "type Chapter", "type WebLink https://x.test"])

    def test_listed_markers_show_color_type_and_link(self):
        reply, _ = self.run_markers([{"t": 1, "color": 5, "type": "Chapter"},
                                     {"t": 2, "type": "WebLink", "link": "https://x.test"}],
                                    lambda: asyncio.run(mcp.call_tool("premiere_markers_edit",
                                                                      {"action": "list", "sequence": "s1"})))
        rows = [(m["color"], m["type"], m.get("url")) for m in reply.structured_content["markers"]]
        self.assertEqual(rows, [(5, "chapter", None), (0, "weblink", "https://x.test")])

    def test_a_moved_marker_keeps_its_color_and_type(self):
        reply, _ = self.run_markers([{"t": 1, "color": 5, "type": "Chapter"}],
                                    lambda: asyncio.run(mcp.call_tool("premiere_markers_edit", {
                                        "action": "update", "index": 0, "move_to": 4, "sequence": "s1"})))
        moved = reply.structured_content["updated"][0]
        self.assertEqual((moved["start"], moved["color"], moved["type"]), (4, 5, "chapter"))


SAVE_AS = """
function File(path) {
    this.fsName = path; this.name = path.split("/").pop(); this.exists = require("fs").existsSync(path); this.text = "";
}
File.prototype.remove = function () { require("fs").unlinkSync(this.fsName); return true; };
function project(path) {
    return {path: path, name: path.split("/").pop(), sequences: {numSequences: 0},
        saveAs: function (to) {
            require("fs").appendFileSync(EDITS, "saveAs " + to + "\\n");
            app.project = app.projects[0] = project(to);
            return true;
        }};
}
var app = {projects: {numProjects: 1}};
app.project = app.projects[0] = project(OLD);
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class SaveAsTest(unittest.TestCase):
    """save with a path saves the active project as that file, which then stays open in its place."""

    def save_as(self, target, replace=False):
        old = self.folder / "old.prproj"
        old.write_text("old")
        stub = f"var EDITS = {json.dumps(str(self.edits))}, OLD = {json.dumps(str(old))};" + SAVE_AS
        with mock.patch.object(host, "relay", node_relay(stub)):
            return host.project("save", str(target), replace, False, False, 60)

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.edits = self.folder / "edits.txt"
        self.edits.write_text("")

    def test_save_as_a_new_file_keeps_that_file_open(self):
        target = self.folder / "new" / "copy.prproj"
        done = self.save_as(target)
        self.assertEqual((done["project"], done["saved_from"]), (str(target), str(self.folder / "old.prproj")))
        self.assertEqual(self.edits.read_text().splitlines(), [f"saveAs {target}"])

    def test_an_existing_file_is_kept_unless_replace(self):
        target = self.folder / "taken.prproj"
        target.write_text("keep")
        with self.assertRaisesRegex(ValueError, "Already exists"):
            self.save_as(target)
        self.assertEqual(target.read_text(), "keep")
        done = self.save_as(target, replace=True)
        self.assertEqual(done["project"], str(target))
        self.assertFalse(target.exists())

    def test_saving_as_the_active_project_path_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "save without path"):
            self.save_as(self.folder / "old.prproj", replace=True)
        self.assertEqual(self.edits.read_text(), "")


# One clip from source IN to OUT at SPEED: as in Premiere, its inPoint and outPoint read as source times divided
# by the speed. A 480 x 270 source with 2:1 pixels on a 640 x 360 square-pixel sequence.
RETIMED = """
function log(line) { require("fs").appendFileSync(EDITS, line + "\\n"); }
function Time() { this.ticks = "0"; }
Object.defineProperty(Time.prototype, "seconds", {get: function () { return Number(this.ticks) / 254016000000; }});
function at(seconds) { return {seconds: seconds}; }
function param(name) {
    var value = 0;
    return {displayName: name, setValue: function (v) { value = v; log("set " + name + " " + JSON.stringify(v)); },
        getValue: function () { return value; }, setTimeVarying: function () {},
        addKey: function (t) { log("key " + name + " " + t); }, setValueAtKey: function () {},
        getValueAtTime: function () { return value; }};
}
var ProjectItemType = {BIN: 1, ROOT: 2, CLIP: 3};
var item = {name: "m.mov", type: 3, nodeId: "m", range: [0, 6], getMediaPath: function () { return MEDIA; },
    getProjectMetadata: function () {
        return "<Column.Intrinsic.VideoInfo>480 x 270 (2.0)</Column.Intrinsic.VideoInfo>";
    },
    getInPoint: function () { return at(this.range[0]); }, getOutPoint: function () { return at(this.range[1]); },
    setInPoint: function (t) { this.range[0] = t; log("item in " + t); },
    setOutPoint: function (t) { this.range[1] = t; log("item out " + t); }};
function placed(start, from, to, speed) {
    return {name: "m.mov", nodeId: "c" + start, mediaType: "Video", projectItem: item, disabled: false,
        speed: speed, start: at(start), end: at(start + (to - from) / speed), inPoint: at(from / speed),
        outPoint: at(to / speed), getSpeed: function () { return this.speed; },
        isSpeedReversed: function () { return REVERSED; }, getLinkedItems: function () { return null; },
        components: {numItems: 2, 0: {displayName: "Opacity", properties: {numItems: 1, 0: param("Opacity")}},
            1: {displayName: "Motion", properties: {numItems: 2, 0: param("Scale"), 1: param("Position")}}}};
}
var items = [placed(0, IN, OUT, SPEED)];
var lane = {name: "V1", transitions: {numItems: 0}, isLocked: function () { return false; },
    overwriteClip: function (source, start) {
        log("place " + start);
        items.push(placed(start, source.range[0], source.range[1], 1));
    }};
Object.defineProperty(lane, "clips", {get: function () {
    var list = {numItems: items.length}, i;
    for (i = 0; i < items.length; i++) { list[i] = items[i]; }
    return list;
}});
var sequence = {name: "S", sequenceID: "s1", projectItem: {nodeId: "p1"}, timebase: "10160640000", end: "0",
    frameSizeHorizontal: 640, frameSizeVertical: 360, markers: {getFirstMarker: function () { return null; }},
    getSettings: function () { return {videoPixelAspectRatio: "1:1", videoDisplayFormat: 100}; },
    videoTracks: {numTracks: 1, 0: lane}, audioTracks: {numTracks: 0}};
var app = {project: {path: "/p.prproj", rootItem: {type: 2, children: {numItems: 1, 0: item}},
    sequences: {numSequences: 1, 0: sequence}, activeSequence: sequence, openSequence: function () {}},
    enableQE: function () {}};
var qe = {project: {getActiveSequence: function () {
    return {getVideoTrackAt: function () {
        return {numItems: items.length, getItemAt: function (i) {
            var dom = items[i];
            return {type: "Clip", speed: dom.speed, setSpeed: function (ratio, code, reverse, pitch, ripple) {
                var from = dom.inPoint.seconds * dom.speed, length = dom.end.seconds - dom.start.seconds;
                log("setSpeed " + ratio + " " + code + " " + reverse + " " + ripple);
                dom.speed = ratio;
                dom.inPoint = at(from / ratio);
                dom.outPoint = at((from + length * ratio) / ratio);
                return true;
            }};
        }};
    }};
}}};
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class RetimedClipTest(unittest.TestCase):
    """A clip at 200% plays two source seconds per timeline second; keys, cuts, copies and slips follow that."""

    def stub(self, source_in=2, source_out=6, speed=2, reversed_=False, media="/m.mov"):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.edits = Path(folder.name) / "edits.txt"
        self.edits.write_text("")
        stub = (f"var EDITS = {json.dumps(str(self.edits))}, MEDIA = {json.dumps(media)}, IN = {source_in}, "
                f"OUT = {source_out}, SPEED = {speed}, REVERSED = {json.dumps(reversed_)};" + RETIMED)
        patch = mock.patch.object(host, "relay", node_relay(stub))
        patch.start()
        self.addCleanup(patch.stop)

    def lines(self, prefix):
        return [line for line in self.edits.read_text().splitlines() if line.startswith(prefix)]

    def test_keyframes_land_at_the_source_time_of_their_timeline_offset(self):
        self.stub()
        host.clip_props("s1", "video", 0, None, 0, {}, [{"time": 0, "opacity": 0}, {"time": 1, "opacity": 100}], 60)
        self.assertEqual(self.lines("key"), ["key Opacity 2", "key Opacity 4"])

    def test_keyframes_on_a_reversed_clip_are_refused(self):
        self.stub(reversed_=True)
        with self.assertRaisesRegex(RuntimeError, "reversed"):
            host.clip_props("s1", "video", 0, None, 0, {}, [{"time": 0, "opacity": 0}], 60)
        self.assertEqual(self.lines("key"), [])

    def test_inspect_reports_the_source_range_and_the_speed(self):
        self.stub()
        clip = host.inspect("s1", 60, items=False)["sequences"][0]["video"][0]["clips"][0]
        self.assertEqual((clip["in_point"], clip["out_point"], clip["speed"], clip["reversed"]), (2, 6, 200, False))

    def test_a_copy_keeps_the_source_range_and_the_speed(self):
        self.stub()
        clip = clip_tools.copy("s1", "video", 0, None, 0, 10.0, None, 60)["clip"]
        self.assertEqual(self.lines("item")[:2], ["item in 2", "item out 4"])
        self.assertEqual(self.lines("place"), ["place 10"])
        self.assertEqual(self.lines("setSpeed"), ["setSpeed 2 00:00:02:00 false false"])
        self.assertEqual((clip["start"], clip["end"], clip["in_point"], clip["out_point"], clip["speed"]),
                         (10, 12, 2, 6, 200))

    def test_a_slip_moves_the_source_by_source_seconds(self):
        self.stub(source_in=1, source_out=3)
        done = clip_tools.slip("s1", "video", 0, None, 0, 1.0, None, False, 60)
        self.assertEqual((done["before"], done["after"]),
                         ({"in_point": 1, "out_point": 3}, {"in_point": 2, "out_point": 4}))

    def test_a_fit_counts_the_source_pixel_aspect(self):
        self.stub()
        done = host.clip_fit("s1", 0, None, 0, "fit", 60)
        self.assertEqual((done["scale"], done["pixel_aspect"]), (66.67, 2))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_scene_cuts_follow_the_speed_and_direction(self):
        with tempfile.TemporaryDirectory() as folder:
            movie = Path(folder) / "six.mov"
            colors = [f"color=c={c}:s=160x90:r=25:d=1" for c in ("red", "blue", "green") * 2]
            subprocess.run(["ffmpeg", "-loglevel", "error", *sum((["-f", "lavfi", "-i", c] for c in colors), []),
                            "-filter_complex", "".join(f"[{i}]" for i in range(6)) + "concat=n=6:v=1:a=0",
                            str(movie)], check=True)
            # Cuts at source 1, 2, 4 and 5 s; the clip plays 1.5 to 5.5 s.
            for reversed_, cuts in ((False, [0.25, 1.25, 1.75]), (True, [0.25, 0.75, 1.75])):
                with self.subTest(reversed=reversed_):
                    self.stub(source_in=1.5, source_out=5.5, reversed_=reversed_, media=str(movie))
                    self.assertEqual(host.scene_detect("s1", 0, None, 0, 0.3, "report", False, 60)["cuts"], cuts)


class MailboxTest(unittest.TestCase):
    def test_the_mailbox_is_private_to_its_user(self):
        with tempfile.TemporaryDirectory() as folder:
            for box in (Path(folder) / "new", Path(folder) / "shared"):
                if box.name == "shared":
                    box.mkdir()
                    os.chmod(box, 0o755)
                with self.assertRaises(TimeoutError):
                    host.mailbox_send("premierepro", "1", 0.1, box=box)
                self.assertEqual(box.stat().st_mode & 0o777, 0o700, box.name)


class TimeoutTest(unittest.TestCase):
    """timeout bounds the whole call, not each wait inside it."""

    def test_an_export_that_never_reports_fails_by_its_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            def answer_late(body, timeout):
                time.sleep(1)
                return "timed out"

            began = time.monotonic()
            with mock.patch.object(host, "relay", answer_late), self.assertRaisesRegex(RuntimeError, "job failed"):
                host.finish("1", Path(folder) / "r.json", Path(folder) / "m.mov", 1.5)
        self.assertLess(time.monotonic() - began, 2.2)

    def test_a_premiere_that_never_answers_fails_by_the_call_timeout(self):
        patches = [mock.patch.object(host, name, value) for name, value in (
            ("bridge", lambda: Path("/b.app")), ("premiere", lambda: Path("/p.app")), ("running", lambda app: [1]),
            ("start", lambda app: None), ("bridge_age", lambda app: 900), ("READY_TIMEOUT", 4),
            ("send", lambda body, timeout, target="premierepro", wait=None: "busy"))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        began = time.monotonic()
        with self.assertRaises(host.NotReady):
            host.relay("1", 1)
        self.assertLess(time.monotonic() - began, 1.7)


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
