import json
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import zlib
from pathlib import Path

from cavi_premiere_mcp import host

JSX = Path(host.__file__).with_name("jsx")
TOOLS = ["project", "inspect", "import", "sequence_new", "clip_place", "clip_props", "transition_add",
         "media_replace", "markers_add", "mogrt_add", "export", "transitions", "clip_edit", "razor", "clip_speed",
         "sequence_set", "tracks", "frame_export", "encode", "auto_reframe", "interchange", "captions", "effects", "effect_add", "effect_set",
         "clip_fit", "items", "cut", "markers_edit", "gaps", "range_remove", "bins", "clip_slip"]


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
            host.project("new", project, False, False, False, 60)
        self.assertEqual(project.read_text(), "kept")

    def test_open_needs_an_existing_project(self):
        with self.assertRaisesRegex(ValueError, "No file at"):
            host.project("open", self.root / "missing.prproj", False, False, False, 60)

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

    def test_clip_edit_needs_one_address_and_one_kind_of_edit(self):
        with self.assertRaisesRegex(ValueError, "exactly one of at, position_index or name"):
            host.clip_edit(None, "video", 0, 1.0, 0, None, {"enabled": False}, 60)
        with self.assertRaisesRegex(ValueError, "at least one edit"):
            host.clip_edit(None, "video", 0, None, 0, None, {"enabled": None}, 60)
        with self.assertRaisesRegex(ValueError, "remove cannot be combined"):
            host.clip_edit(None, "video", 0, None, 0, None, {"remove": "lift", "enabled": False}, 60)
        with self.assertRaisesRegex(ValueError, "trim_end must be after trim_start"):
            host.clip_edit(None, "video", 0, None, 0, None, {"trim_start": 3, "trim_end": 2}, 60)

    def test_razor_on_one_track_needs_its_kind(self):
        with self.assertRaisesRegex(ValueError, "kind video or audio"):
            host.razor(None, [1], "all", 0, 60)

    def test_speed_is_given_as_percent_or_duration(self):
        for speed, duration in ((None, None), (200, 1.0)):
            with self.assertRaisesRegex(ValueError, "exactly one of speed or duration"):
                host.clip_speed(None, "video", 0, None, 0, speed, duration, False, True, False, 60)
        with self.assertRaisesRegex(ValueError, "exactly one of at, position_index or name"):
            host.clip_speed(None, "video", 0, None, None, 200, None, False, True, False, 60)

    def test_sequence_change_is_not_empty_and_delete_stands_alone(self):
        with self.assertRaisesRegex(ValueError, "at least one change"):
            host.sequence_set(None, {"settings": None, "remove": False}, 60)
        with self.assertRaisesRegex(ValueError, "remove cannot be combined"):
            host.sequence_set(None, {"remove": True, "new_name": "x"}, 60)

    def test_reframe_ratio_is_width_colon_height(self):
        for ratio in ("9x16", "0:16", "9:"):
            with self.assertRaisesRegex(ValueError, "width:height"):
                host.auto_reframe(None, ratio, "default", None, False, 60)

    def test_interchange_keeps_an_existing_file_and_imports_only_xml(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "a.aaf"
            target.write_text("kept")
            with self.assertRaisesRegex(ValueError, "pass replace=true"):
                host.interchange(None, "aaf", target, False, 48000, 16, 60)
            self.assertEqual(target.read_text(), "kept")
            with self.assertRaisesRegex(ValueError, "Expected a .xml file"):
                host.interchange(None, "import_xml", target, False, 48000, 16, 60)
            with self.assertRaisesRegex(ValueError, "Expected a .omf file"):
                host.interchange(None, "omf", Path(folder) / "a.aaf", True, 48000, 16, 60)

    def test_encode_keeps_an_existing_master(self):
        with tempfile.TemporaryDirectory() as folder:
            master, preset = Path(folder) / "m.mov", Path(folder) / "p.epr"
            master.write_text("kept")
            preset.write_text("")
            with self.assertRaisesRegex(ValueError, "pass replace=true"):
                host.render("encode", None, master, preset, "in_out", False, 60)
            self.assertEqual(master.read_text(), "kept")

    def test_captions_need_an_srt_and_are_counted_from_it(self):
        with tempfile.TemporaryDirectory() as folder:
            srt = Path(folder) / "c.srt"
            srt.write_text("1\r\n00:00:00,500 --> 00:00:02,500\r\nOne\r\n\r\n2\r\n00:00:03,000 --> 00:00:05,000\r\nTwo\r\n")
            self.assertEqual(host.srt_count(srt), 2)
            with self.assertRaisesRegex(ValueError, "Expected a .srt file"):
                host.captions(None, Path(folder) / "c.vtt", 0, "subtitle", 60)

    def test_effect_parameters_are_checked_before_premiere_is_asked(self):
        def call(component, params, list_=False, at=None, index=0):
            return host.effect_set(None, "video", 0, at, index, component, 0, list_, params, 60)

        with self.assertRaisesRegex(ValueError, "exactly one of at, position_index or name"):
            call("Crop", [{"name": "Left", "value": 1}], at=1.0)
        with self.assertRaisesRegex(ValueError, "params to set or list=true"):
            call("Crop", [])
        with self.assertRaisesRegex(ValueError, "component the parameters belong to"):
            call(None, [{"name": "Left", "value": 1}])
        with self.assertRaisesRegex(ValueError, "exactly one of value or color"):
            call("Crop", [{"name": "Left"}])
        with self.assertRaisesRegex(ValueError, "either a value or keyframes"):
            call("Crop", [{"name": "Left", "value": 1, "keyframes": [{"time": 0, "value": 2}]}])

    def test_caption_preset_copies_go_to_the_given_folder_only(self):
        package = Path(host.__file__).parent
        listing = sorted(str(p) for p in package.rglob("*") if "__pycache__" not in p.parts)
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as out:
            on = Path(folder) / "has.epr"
            on.write_text("<A>\n\t<DoAudio>true</DoAudio>\n\t<DoCaptions>true</DoCaptions>\n</A>")
            bare = Path(folder) / "bare.epr"
            bare.write_text("<A>\n\t<DoAudio>true</DoAudio>\n</A>")
            off, added = host.caption_preset(on, False, out), host.caption_preset(bare, True, out)
            self.assertEqual({off.parent, added.parent}, {Path(out)})
            self.assertIn("<DoCaptions>false</DoCaptions>", off.read_text())
            self.assertIn("<DoCaptions>true</DoCaptions>", added.read_text())
            self.assertIn("<DoCaptions>true</DoCaptions>", on.read_text())
            self.assertNotIn("DoCaptions", bare.read_text())
        self.assertEqual(sorted(str(p) for p in package.rglob("*") if "__pycache__" not in p.parts), listing)

    def test_encode_refuses_bad_input_before_media_encoder_is_started(self):
        def launch(app):
            raise RuntimeError("Media Encoder launched")

        self.addCleanup(setattr, host, "start", host.start)
        host.start = launch
        with tempfile.TemporaryDirectory() as folder:
            master = Path(folder) / "m.mov"
            master.write_text("kept")
            for args, message in (((master, None, "in_out", False), "Already exists"),
                                  ((master, None, "bogus", True), "range is entire, in_out or work_area"),
                                  ((Path("rel.mov"), None, "entire", True), "Use an absolute path"),
                                  ((Path(folder) / "n.mov", Path(folder) / "p.xml", "entire", True),
                                   "Expected a .epr file")):
                with self.assertRaisesRegex(ValueError, message):
                    host.encode(None, *args, 60)

    def test_item_changes_are_checked_before_premiere_is_asked(self):
        with self.assertRaisesRegex(ValueError, "at least one change"):
            host.items("a.mov", {"rename": None, "remove": False}, 60)
        with self.assertRaisesRegex(ValueError, "remove cannot be combined"):
            host.items("a.mov", {"remove": True, "label": 3}, 60)
        with self.assertRaisesRegex(ValueError, "out_point must be after in_point"):
            host.items("a.mov", {"subclip": {"name": "s", "in_point": 2, "out_point": 1}}, 60)
        with self.assertRaisesRegex(ValueError, "No file at"):
            host.items("a.mov", {"proxy": {"path": "/no/such/proxy.mov"}}, 60)

    def test_scene_detect_needs_one_clip_address(self):
        with self.assertRaisesRegex(ValueError, "exactly one of at, position_index or name"):
            host.scene_detect(None, 0, None, None, 0.3, "report", False, 60)

    def test_tracks_need_something_to_do(self):
        with self.assertRaisesRegex(ValueError, "tracks to add or track states"):
            host.tracks(None, 0, 0, [], 60)

    def test_frames_are_exported_to_an_absolute_folder(self):
        with self.assertRaisesRegex(ValueError, "absolute path"):
            host.frame_export(None, [1.0], "frames", "f", 60)


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

    def test_timecodes_use_the_frame_grid_and_carry_over_minutes_and_hours(self):
        out = self.node("process.stdout.write(JSON.stringify([tcOf(2, 25), tcOf(0.52, 25), tcOf(61.5, 25), "
                        "tcOf(3725, 30), tcOf(1 / 30, 30)]))")
        self.assertEqual(json.loads(out), ["00:00:02:00", "00:00:00:13", "00:01:01:13", "01:02:05:00", "00:00:00:01"])

    def test_every_tool_script_is_valid_javascript(self):
        for tool in TOOLS:
            with tempfile.TemporaryDirectory() as folder:
                script = Path(folder) / f"{tool}.js"
                script.write_text("\n".join((JSX / name).read_text() for name in ("lib.jsx", f"{tool}.jsx",
                                                                                 "tail.jsx")))
                result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{tool}: {result.stderr}")


PREMIERE_STUB = """
var ProjectItemType = {BIN: 1, ROOT: 2, CLIP: 3};
function File(path) { this.fsName = path; this.exists = true; }
var item = {name: "a.mp4", type: 3, getMediaPath: function () { return "/m/a.mp4"; },
    getInPoint: function () { return {seconds: 0}; }, getOutPoint: function () { return {seconds: 3}; },
    setInPoint: function () {}, setOutPoint: function () {}};
var lane = {clips: {numItems: 0}, overwriteClip: function (source, at) {
    this.clips[this.clips.numItems++] = {name: source.name, start: {seconds: at}, end: {seconds: at + 3},
        inPoint: {seconds: 0}, outPoint: {seconds: 3}, projectItem: source};
}};
var sequence = {name: "S", videoTracks: {numTracks: 1, 0: lane}, audioTracks: {numTracks: 0}};
var app = {project: {rootItem: {type: 2, children: {numItems: 1, 0: item}}, activeSequence: sequence}};
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class PlacedClipTest(unittest.TestCase):
    def test_a_placed_clip_report_is_a_valid_tool_result(self):
        from cavi_premiere_mcp.models import Placed

        script = "\n".join((PREMIERE_STUB, (JSX / "lib.jsx").read_text(), (JSX / "clip_place.jsx").read_text(), """
var report = {warnings: [], errors: []};
run({sequence: null, item: "/m/a.mp4", kind: "video", track: 0, at: 1, in_point: null, out_point: null,
    mode: "overwrite"}, report);
process.stdout.write(stringify(report));"""))
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        placed = Placed.model_validate(json.loads(result.stdout))
        self.assertEqual((placed.clip.name, placed.clip.start, placed.clip.media_path), ("a.mp4", 1, "/m/a.mp4"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is required")
class SceneTest(unittest.TestCase):
    def test_hard_cuts_are_found_at_their_source_times(self):
        with tempfile.TemporaryDirectory() as folder:
            movie = Path(folder) / "cuts.mov"
            colors = [f"color=c={c}:s=160x90:r=25:d=1" for c in ("red", "blue", "green")]
            subprocess.run(["ffmpeg", "-loglevel", "error", *sum((["-f", "lavfi", "-i", c] for c in colors), []),
                            "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0", str(movie)], check=True)
            self.assertEqual([round(t, 2) for t in host.scene_times(movie, 0.3)], [1.0, 2.0])
            self.assertEqual(host.scene_times(movie, 0.99), [])


class StillTest(unittest.TestCase):
    def test_png_size_is_read_from_the_header(self):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 640, 360, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(b"\x00" + b"\x00\x00\x00" * 640) * 1) + chunk(b"IEND", b""))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "f.png"
            path.write_bytes(png)
            self.assertEqual(host.png_size(path), (640, 360))
            path.write_bytes(b"not a png at all, just text bytes")
            with self.assertRaisesRegex(RuntimeError, "Not a PNG"):
                host.png_size(path)


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


class TransitionNameTest(unittest.TestCase):
    def test_cut_takes_aliases_and_any_listed_name(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("a.mov", "b.mov"):
                (Path(folder) / name).write_bytes(b"")
            clips = [{"file": f"{folder}/a.mov", "start": 0, "in_point": 0, "out_point": 1,
                      "transition": {"kind": "dip_to_black", "frames": 4}},
                     {"file": f"{folder}/b.mov", "start": 1, "in_point": 0, "out_point": 1,
                      "transition": {"kind": "Cross Zoom", "frames": 4}}]
            planned, _ = host.plan(clips, 25)
        self.assertEqual([c["transition"] for c in planned], ["Dip to Black", "Cross Zoom"])


class PresetLookupTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="premiere-presets-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.roots = host.preset_roots
        self.addCleanup(setattr, host, "preset_roots", self.roots)
        for source, folder, name in [("premiere", "4E49434B_48323634", "Match High"),
                                     ("media_encoder", "4E49434B_48323634", "Match High"),
                                     ("premiere", "4A454646_48455643", "Match High"),
                                     ("user", "user", "Match Low"), ("premiere", "4E49434B_48323634", "Match Low")]:
            path = self.root / source / folder / f"{name}.epr"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        host.preset_roots = lambda kind: [(s, self.root / s) for s in ("premiere", "media_encoder", "user")]

    def test_listing_names_format_and_source(self):
        found = {(p["source"], p["format"], p["name"]) for p in host.presets("export")}
        self.assertIn(("premiere", "H264", "Match High"), found)
        self.assertIn(("user", "user", "Match Low"), found)

    def test_format_prefix_picks_among_equal_names(self):
        path = host.resolve_preset("export", "H264/Match High")
        self.assertEqual(Path(path), self.root / "premiere/4E49434B_48323634/Match High.epr")

    def test_equal_names_in_several_formats_need_a_prefix(self):
        with self.assertRaisesRegex(ValueError, "several presets"):
            host.resolve_preset("export", "Match High")

    def test_user_preset_wins_over_a_system_preset_of_the_same_name(self):
        self.assertEqual(Path(host.resolve_preset("export", "Match Low")), self.root / "user/user/Match Low.epr")

    def test_unknown_name_points_to_the_listing(self):
        with self.assertRaisesRegex(ValueError, "premiere_presets"):
            host.resolve_preset("export", "nope")


class PresetTest(unittest.TestCase):
    @unittest.skipUnless(sorted(Path("/Applications").glob("Adobe Premiere Pro 20*")), "Premiere Pro is required")
    def test_installed_presets_are_found_by_name(self):
        names = {(p["format"], p["name"]) for p in host.presets("export")}
        self.assertIn(("MooV", "Apple ProRes 422 HQ"), names)
        self.assertTrue(host.resolve_preset("export", "H264/00 - Match Source - High bitrate").endswith(".epr"))

    @unittest.skipUnless(sorted(Path("/Applications").glob("Adobe Premiere Pro 20*")), "Premiere Pro is required")
    def test_preset_name_resolves_to_its_file(self):
        found = Path(host.sequence_preset("HD 1080p 25 fps"))
        self.assertEqual((found.name, found.is_file()), ("HD 1080p 25 fps.sqpreset", True))


class MailboxTest(unittest.TestCase):
    def serve(self, box, reply):
        import threading

        def bridge():
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                for job in box.glob("*.job"):
                    target, _, body = job.read_text().partition("\n")
                    answer = reply(target, body)
                    job.unlink()
                    (box / (job.stem + ".part")).write_text(answer)
                    (box / (job.stem + ".part")).rename(box / (job.stem + ".reply"))
                    return
                time.sleep(0.01)

        thread = threading.Thread(target=bridge)
        thread.start()
        self.addCleanup(thread.join)

    def test_round_trip_returns_the_relay_answer_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            box = Path(folder)
            self.serve(box, lambda target, body: f"ok\n{target}|{body}")
            self.assertEqual(host.mailbox_send("premierepro", "1+1", 5, box=box), (True, "premierepro|1+1"))
            self.assertEqual(list(box.iterdir()), [])

    def test_relay_error_is_returned_as_an_error(self):
        with tempfile.TemporaryDirectory() as folder:
            box = Path(folder)
            self.serve(box, lambda target, body: "error\nTARGET COULD NOT BE LAUNCHED")
            self.assertEqual(host.mailbox_send("premierepro", "x", 5, box=box), (False, "TARGET COULD NOT BE LAUNCHED"))

    def test_no_reply_raises_the_approval_message(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(host.NotReady, "approve it in Bridge Settings > Startup Scripts"):
                host.mailbox_send("premierepro", "'ready'", 5, wait=0.2, box=Path(folder))
            self.assertEqual(list(Path(folder).iterdir()), [])


class TimelineRefusalTest(unittest.TestCase):
    def test_bad_input_is_refused_before_premiere_is_called(self):
        from cavi_premiere_mcp import timeline

        def launch(app):
            raise RuntimeError("an app was launched")

        self.addCleanup(setattr, host, "start", host.start)
        host.start = launch
        cases = (
            (lambda: timeline.range_remove(None, 5, 5, "extract", 60), "end must be after start"),
            (lambda: timeline.markers_edit(None, "delete", None, None, False, None, None, None, None, 60),
             "exactly one of index, at or all"),
            (lambda: timeline.markers_edit(None, "update", 0, None, False, None, None, None, None, 60),
             "Give name, comment, move_to or duration"),
            (lambda: timeline.markers_edit(None, "update", None, None, True, "x", None, 2.0, None, 60),
             "move_to needs one marker"),
            (lambda: timeline.bins("create", None, None, None, None, False, 60), "new bin's name"),
            (lambda: timeline.bins("rename", "A", None, None, None, False, 60), "Give new_name"),
            (lambda: timeline.bins("move", "A", None, None, [], False, 60), "Give items to move"),
        )
        for call, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                call()


class ClipToolsTest(unittest.TestCase):
    def test_fade_keyframes_run_from_silent_to_full_and_back(self):
        from cavi_premiere_mcp import clip_tools as clips

        self.assertEqual(clips.fade_keys("video", 4, 1, 0.5),
                         [{"time": 0, "opacity": 0}, {"time": 1, "opacity": 100},
                          {"time": 3.5, "opacity": 100}, {"time": 4, "opacity": 0}])
        self.assertEqual(clips.fade_keys("audio", 2, 0, 1), [{"time": 1, "volume_db": 0},
                                                             {"time": 2, "volume_db": -96}])
        with self.assertRaisesRegex(ValueError, "longer than the clip"):
            clips.fade_keys("video", 1, 0.8, 0.8)
        with self.assertRaisesRegex(ValueError, "Give fade_in or fade_out"):
            clips.fade_keys("video", 1, 0, 0)

    def test_search_finds_items_by_name_and_reports_offline_and_unused(self):
        from cavi_premiere_mcp import clip_tools as clips

        listed = {"items": [
            {"name": "a.mov", "bin": "", "kind": "clip", "media_path": "/m/a.mov", "offline": False},
            {"name": "b.mov", "bin": "Takes", "kind": "clip", "media_path": "/m/b.mov", "offline": True},
            {"name": "main", "bin": "", "kind": "sequence", "media_path": None, "offline": None}],
            "sequences": [{"name": "main", "video": [{"clips": [
                {"name": "a.mov", "start": 0, "end": 2, "media_path": "/m/a.mov"}]}], "audio": []}]}
        everything = clips.search(listed, None, "A.MOV", "both", False, False)
        self.assertEqual([i["name"] for i in everything["items"]], ["a.mov"])
        self.assertEqual([c["start"] for c in everything["clips"]], [0])
        self.assertTrue(everything["items"][0]["used"])
        offline = clips.search(listed, None, "", "both", True, False)
        self.assertEqual([i["name"] for i in offline["items"]], ["b.mov"])
        self.assertEqual(offline["clips"], [])
        unused = clips.search(listed, None, "", "items", False, True)
        self.assertEqual([i["name"] for i in unused["items"]], ["b.mov"])

    def test_bad_input_is_refused_before_premiere_is_called(self):
        from cavi_premiere_mcp import clip_tools as clips

        def launch(app):
            raise RuntimeError("an app was launched")

        self.addCleanup(setattr, host, "start", host.start)
        host.start = launch
        with self.assertRaisesRegex(ValueError, "exactly one of at or position_index"):
            clips.fade(None, "video", 0, None, None, 1, 0, 60)
        with self.assertRaisesRegex(ValueError, "exactly one of at or position_index"):
            clips.copy(None, "video", 0, 1.0, 0, 5.0, None, 60)
        with self.assertRaisesRegex(ValueError, "exactly one of offset or in_point"):
            clips.slip(None, "video", 0, 1.0, None, 1.0, 2.0, True, 60)
        with self.assertRaisesRegex(ValueError, "in_point cannot be negative"):
            clips.slip(None, "video", 0, 1.0, None, None, -1.0, True, 60)


if __name__ == "__main__":
    unittest.main()
