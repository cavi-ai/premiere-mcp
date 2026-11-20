"""Delivery checks: loudness of generated media, and render state and synthetic items against a stubbed DOM."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cavi_premiere_mcp import host, qc
from tests.test_failures import node_relay


def generate(path, level_db, video=False):
    """Five seconds of a 1 kHz tone, level_db below the generator's own level, with a picture when asked."""
    command = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=f=1000:d=5,volume={level_db}dB"]
    if video:
        command += ["-f", "lavfi", "-i", "testsrc=d=5:s=64x64:r=10", "-shortest", "-c:v", "libx264", "-c:a", "aac"]
    subprocess.run([*command, str(path)], check=True)
    return path


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
class LoudnessTest(unittest.TestCase):
    def test_a_tone_is_measured_and_judged_against_presets_and_explicit_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            tone = generate(Path(folder) / "tone.wav", 0)  # -21 dBFS RMS, -18 dBFS peak
            streaming = qc.loudness(str(tone), None, None, None, 1, None, False, 60)
            self.assertAlmostEqual(streaming["integrated_lufs"], -21.1, delta=0.5)
            self.assertAlmostEqual(streaming["true_peak_dbtp"], -18.0, delta=0.5)
            self.assertEqual((streaming["target_lufs"], streaming["max_true_peak"], streaming["passes"]),
                             (-14.0, -1.0, False))
            near = qc.loudness(str(tone), None, -21.5, None, 1, None, False, 60)
            self.assertEqual((near["max_true_peak"], near["passes"]), (-1.0, True))
            self.assertFalse(qc.loudness(str(tone), None, -21.5, None, 0.2, None, False, 60)["passes"])
            self.assertFalse(qc.loudness(str(tone), None, -21.5, -20, 1, None, False, 60)["passes"])
            self.assertFalse(qc.loudness(str(tone), "atsc_a85", None, None, 1, None, False, 60)["passes"])
            self.assertTrue(qc.loudness(str(tone), "ebu_r128", None, None, 2.5, None, False, 60)["passes"])

    def test_normalize_writes_a_copy_at_the_target_with_the_video_copied(self):
        with tempfile.TemporaryDirectory() as folder:
            master = generate(Path(folder) / "master.mp4", -20, video=True)
            copy = Path(folder) / "out" / "normalized.mp4"
            done = qc.loudness(str(master), "ebu_r128", None, None, 1, str(copy), False, 120)
            self.assertFalse(done["passes"])
            self.assertEqual(done["normalized"]["file"], str(copy))
            self.assertAlmostEqual(done["normalized"]["integrated_lufs"], -23, delta=0.7)
            self.assertTrue(done["normalized"]["passes"])
            codecs = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "json",
                                     str(copy)], capture_output=True, text=True, check=True).stdout
            self.assertEqual(sorted(s["codec_name"] for s in json.loads(codecs)["streams"]), ["aac", "h264"])
            with self.assertRaisesRegex(ValueError, "replace=true"):
                qc.loudness(str(master), "ebu_r128", None, None, 1, str(copy), False, 120)
            self.assertTrue(qc.loudness(str(master), "ebu_r128", None, None, 1, str(copy), True, 120)["normalized"]
                            ["passes"])

    def test_a_preset_and_an_explicit_target_together_are_refused(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            qc.loudness("/x.wav", "podcast", -20, None, 1, None, False, 60)


SEQUENCE = """
var fs = require("fs");
function Time() { this.ticks = "0"; }
function bin(name) { return {name: name, nodeId: "b-" + name, type: 2, children: {numItems: 0}}; }
var root = {name: "root", nodeId: "root", type: 2, children: {numItems: 0}};
function add(item) { root.children[root.children.numItems] = item; root.children.numItems += 1; }
var main = {name: "Main", sequenceID: "s1", timebase: "10160640000", frameSizeHorizontal: 1280,
    frameSizeVertical: 720, end: "0", videoTracks: {numTracks: 0}, audioTracks: {numTracks: 0}};
var ProjectItemType = {BIN: 2, ROOT: 3, CLIP: 1};
root.type = 3;
function made(name) {
    return {name: name, nodeId: "n" + root.children.numItems, type: 1, moveBin: function (to) { this.moved = to.name; }};
}
function create(label) {
    return function (w, h, fps) {
        fs.appendFileSync(LOG, label + " " + w + "x" + h + " " + fps + "\\n");
        if (!SILENT) { add(made(label)); }
        return true;
    };
}
var app = {enableQE: function () {}, project: {rootItem: root, activeSequence: main,
    sequences: {numSequences: 1, 0: main}, openSequence: function () {}}};
root.createBin = function (name) { var b = bin(name); add(b); return b; };
var qe = {project: {numItems: 0, newBlackVideo: create("Black Video"), newTransparentVideo: create("Transparent Video"),
    newBarsAndTone: create("HD Bars and Tone")}};
"""


@unittest.skipUnless(shutil.which("node"), "node is required")
class SyntheticItemTest(unittest.TestCase):
    def make(self, silent=False, **args):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "log.txt"
            stub = f"var LOG = {json.dumps(str(log))}, SILENT = {json.dumps(silent)};" + SEQUENCE
            with mock.patch.object(host, "relay", node_relay(stub)):
                done = qc.item_new(args.pop("kind"), args.pop("name", None), args.pop("bin", None),
                                   args.pop("width", None), args.pop("height", None), args.pop("fps", None), None, 60)
            return done, log.read_text()

    def test_size_and_rate_default_to_the_sequences_and_the_item_is_named_and_binned(self):
        done, log = self.make(kind="black_video", name="Slate", bin="Media")
        self.assertEqual(log, "Black Video 1280x720 25\n")
        self.assertEqual((done["name"], done["bin"], done["kind"]), ("Slate", "Media", "black_video"))

    def test_an_explicit_size_and_rate_win(self):
        _, log = self.make(kind="transparent_video", width=640, height=360, fps=29.97)
        self.assertEqual(log, "Transparent Video 640x360 29.97\n")

    def test_a_call_that_adds_nothing_is_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "did not add the item"):
            self.make(silent=True, kind="bars_and_tone")


if __name__ == "__main__":
    unittest.main()
