"""Premiere Pro over a Photoshop BridgeTalk relay, the ProRes cut engine and frame checks."""

import json
import os
import plistlib
import shutil
import time
from fractions import Fraction
from pathlib import Path

from cavi_mcp_core.proc import diagnostics, run_sync

CUT = Path(__file__).with_name("cut.jsx")
READY_TIMEOUT = 300
PRESET = "*.app/Contents/MediaIO/systempresets/3F3F3F3F_4D6F6F56/Apple ProRes 422 HQ.epr"
TRANSITIONS = {"cross_dissolve": "Cross Dissolve", "film_dissolve": "Film Dissolve",
               "dip_to_white": "Dip to White", "dip_to_black": "Dip to Black"}


def newest(pattern):
    found = sorted(Path("/Applications").glob(pattern))
    if not found:
        raise ValueError(f"No /Applications/{pattern}")
    return found[-1]


def premiere():
    return newest("Adobe Premiere Pro 20*/Adobe Premiere Pro 20*.app")


def photoshop():
    return newest("Adobe Photoshop 20*/Adobe Photoshop 20*.app")


def prores_preset():
    return newest("Adobe Premiere Pro 20*/" + PRESET)


def running(app):
    """Pids of the app's main executable; its helpers can outlive it."""
    command = f"{app.name}/Contents/MacOS/{app.stem}$"
    return [int(pid) for pid in run_sync(["pgrep", "-f", command], 10).stdout.split()]


def describe(app):
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    return {"app": str(app), "version": info.get("CFBundleShortVersionString", ""), "pids": running(app)}


def status():
    return {"premiere": describe(premiere()), "photoshop": describe(photoshop()),
            "prores_preset": str(prores_preset())}


def start(app):
    """Open an app in the background when it is not running."""
    if not running(app):
        result = run_sync(["open", "-g", "-a", str(app)], 60)
        if result.returncode:
            raise RuntimeError(f"{app.stem} did not launch: " + diagnostics(result))


def photoshop_script(code, timeout):
    """Run ExtendScript in Photoshop; do javascript answers the script's last value."""
    app = photoshop()
    start(app)
    result = run_sync(["osascript", "-e", "on run argv", "-e", f"with timeout of {timeout} seconds",
                       "-e", f'tell application "{app.stem}" to set answer to do javascript '
                       "(item 1 of argv)", "-e", "end timeout", "-e", "return answer", "-e", "end run",
                       code], timeout + 30)
    if result.returncode:
        raise RuntimeError("Photoshop script failed: " + diagnostics(result))
    return result.stdout.strip()


def relay(body, timeout):
    """Send ExtendScript to Premiere through Photoshop BridgeTalk once Premiere answers messages."""
    start(premiere())
    # A Premiere that is still starting refuses messages with "TARGET COULD NOT BE LAUNCHED".
    deadline = time.monotonic() + READY_TIMEOUT
    while (answer := send("'ready'", 15)) != "ready":
        if time.monotonic() > deadline:
            raise RuntimeError(f"Premiere Pro did not answer within {READY_TIMEOUT} s: {answer}")
        time.sleep(5)
    return send(body, timeout)


def send(body, timeout):
    """BridgeTalk send(timeout) in Photoshop is synchronous; it answers Premiere's last value."""
    code = ("(function () { var target = BridgeTalk.getSpecifier('premierepro');"
            "if (!target) { return 'Premiere Pro is not installed'; }"
            "var talk = new BridgeTalk(), answer = 'no answer';"
            f"talk.target = target; talk.body = {json.dumps(body)};"
            "talk.onResult = function (m) { answer = m.body; };"
            "talk.onError = function (m) { answer = 'ERROR ' + m.body; };"
            "talk.onTimeout = function () { answer = 'timed out'; };"
            f"talk.send({timeout}); return answer; }})();")
    return photoshop_script(code, timeout + 60)


def absolute(path, suffix=None):
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"Use an absolute path: {path}")
    if suffix and path.suffix.lower() != suffix:
        raise ValueError(f"Expected a {suffix} file: {path}")
    return path


def fingerprint(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size, stat.st_ino


def run_script(script, args, report, timeout):
    """Run a .jsx file's text in Premiere with CAVI_ARGS and CAVI_REPORT; return its answer and report."""
    script = absolute(script, ".jsx")
    report = absolute(report, ".json") if report else None
    before = fingerprint(report) if report else None
    body = (f"var CAVI_ARGS = {json.dumps(args)};\nvar CAVI_REPORT = {json.dumps(report and str(report))};\n"
            + script.read_text())
    answer = relay(body, timeout)
    result = {"answer": answer}
    if report:
        if fingerprint(report) in (None, before):
            raise RuntimeError(f"Premiere script wrote no report to {report}; answer: {answer}")
        result["report"] = json.loads(report.read_text())
    return result


def ffprobe():
    found = shutil.which("ffprobe", path=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    if not found:
        raise ValueError("Install ffprobe (FFmpeg) to read frame rates and verify masters")
    return found


def probe(path, entries):
    result = run_sync([ffprobe(), "-v", "error", "-select_streams", "v:0", "-show_entries",
                       f"stream={entries}", "-of", "csv=p=0", str(path)], 60)
    if result.returncode or not result.stdout.split():
        raise RuntimeError(f"ffprobe could not read {path}: " + diagnostics(result))
    # A movie with a timecode track lists its video stream twice; the first line is the stream's.
    return result.stdout.split()[0]


def plan(clips, fps):
    """Clips snapped to the frame grid, in timeline order, without overlaps; and the cut's end frame."""
    names, planned, end = {}, [], 0
    for number, clip in enumerate(clips, 1):
        file = absolute(clip["file"])
        if not file.is_file():
            raise ValueError(f"Clip {number}: no file at {file}")
        if names.setdefault(file.name, file) != file:
            raise ValueError(f"Clip {number}: another clip file is also named {file.name}")
        start, first, last = (round(clip[key] * fps) for key in ("start", "in_point", "out_point"))
        if last <= first:
            raise ValueError(f"Clip {number}: out_point must be at least one frame after in_point")
        if start < end:
            raise ValueError(f"Clip {number}: starts before clip {number - 1} ends; order clips by start")
        transition = clip.get("transition") or {}
        planned.append({"file": str(file), "start": float(start / fps), "in_point": float(first / fps),
                        "out_point": float(last / fps), "transition": TRANSITIONS.get(transition.get("kind")),
                        "frames": transition.get("frames", 0)})
        end = start + last - first
    return planned, end


def cut(project, master, clips, audio, replace, timeout):
    """Cut clips into a new Premiere project, export a ProRes 422 HQ master and check it."""
    project, master = absolute(project, ".prproj"), absolute(master, ".mov")
    audio = absolute(audio) if audio else None
    if audio and not audio.is_file():
        raise ValueError(f"No audio file at {audio}")
    report = project.with_suffix(".report.json")
    existing = [path for path in (project, master, report) if path.exists()]
    if existing and not replace:
        raise ValueError("Already exists (pass replace=true): " + ", ".join(map(str, existing)))
    rate = Fraction(probe(absolute(clips[0]["file"]), "r_frame_rate"))
    planned, end = plan(clips, rate)
    for path in existing:
        path.unlink()
    project.parent.mkdir(parents=True, exist_ok=True)
    master.parent.mkdir(parents=True, exist_ok=True)
    args = {"project": str(project), "clips": planned, "audio": audio and str(audio), "master": str(master),
            "preset": str(prores_preset()), "fps": round(rate), "report": str(report)}
    body = f"var CAVI_ARGS = {json.dumps(args)};\n" + CUT.read_text()
    answer = relay(body, timeout)
    result = json.loads(report.read_text()) if report.is_file() else None
    if answer != "OK" or not result or result["errors"] or not master.is_file():
        raise RuntimeError(f"Premiere Pro cut failed: {answer}; {result}")
    return {"project": str(project), "master": str(master), "fps": str(rate),
            "frames": int(probe(master, "nb_frames")), "cut_frames": end,
            "transitions": result["transitions"], "warnings": result["warnings"]}
