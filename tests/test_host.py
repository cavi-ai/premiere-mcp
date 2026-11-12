import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from cavi_premiere_mcp import host


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="premiere-plan-"))
        self.addCleanup(shutil.rmtree, self.root)
        for name in ("a.mov", "b.mov"):
            (self.root / name).write_bytes(b"")

    def clip(self, name, start, first, last, transition=None):
        return {"file": str(self.root / name), "start": start, "in_point": first, "out_point": last,
                "transition": transition}

    def test_clips_snap_to_the_frame_grid(self):
        planned, end = host.plan([self.clip("a.mov", 0, 0.51, 2.49),
                                  self.clip("b.mov", 2.01, 0, 1, {"kind": "dip_to_black", "frames": 12})], 30)
        self.assertEqual([(c["start"], c["in_point"], c["out_point"]) for c in planned],
                         [(0.0, 0.5, 2.5), (2.0, 0.0, 1.0)])
        self.assertEqual((planned[0]["transition"], planned[1]["transition"]), (None, "Dip to Black"))
        self.assertEqual((planned[1]["frames"], end), (12, 90))

    def test_ntsc_rate_keeps_whole_frames(self):
        planned, end = host.plan([self.clip("a.mov", 0, 0, 1.001)], Fraction(30000, 1001))
        self.assertEqual((planned[0]["out_point"], end), (1.001, 30))

    def test_overlapping_clip_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Clip 2: starts before clip 1 ends"):
            host.plan([self.clip("a.mov", 0, 0, 2), self.clip("b.mov", 1, 0, 1)], 30)

    def test_empty_clip_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Clip 1: out_point"):
            host.plan([self.clip("a.mov", 0, 1, 1.01)], 30)

    def test_two_files_with_one_name_are_refused(self):
        (self.root / "other").mkdir()
        (self.root / "other" / "a.mov").write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "also named a.mov"):
            host.plan([self.clip("a.mov", 0, 0, 1), self.clip("other/a.mov", 1, 0, 1)], 30)

    def test_existing_outputs_are_kept_without_replace(self):
        project = self.root / "cut.prproj"
        project.write_text("kept")
        with self.assertRaisesRegex(ValueError, "pass replace=true"):
            host.cut(project, self.root / "master.mov", [self.clip("a.mov", 0, 0, 1)], None, False, 60)
        self.assertEqual(project.read_text(), "kept")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg is required")
class ProbeTest(unittest.TestCase):
    def test_movie_with_a_timecode_track_reports_its_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            movie = Path(folder) / "master.mov"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            "testsrc=s=320x180:r=25:d=2", "-c:v", "prores_ks", "-profile:v", "3",
                            "-timecode", "00:00:00:00", str(movie)], check=True)
            self.assertEqual(host.probe(movie, "nb_frames"), "50")
            self.assertEqual(Fraction(host.probe(movie, "r_frame_rate")), 25)


if __name__ == "__main__":
    unittest.main()
