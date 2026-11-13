"""Premiere Pro over a Photoshop BridgeTalk relay, the ProRes cut engine and frame checks."""

import json
import os
import plistlib
import shutil
import tempfile
import time
from fractions import Fraction
from pathlib import Path

from cavi_mcp_core.proc import diagnostics, run_sync

JSX = Path(__file__).with_name("jsx")
CUT = JSX / "cut.jsx"
READY_TIMEOUT = 300
PRESET = "*.app/Contents/MediaIO/systempresets/3F3F3F3F_4D6F6F56/Apple ProRes 422 HQ.epr"
TRANSITIONS = {"cross_dissolve": "Cross Dissolve", "film_dissolve": "Film Dissolve",
               "dip_to_white": "Dip to White", "dip_to_black": "Dip to Black"}


class NotReady(RuntimeError):
    """Premiere Pro never answered the relay."""


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
            raise NotReady(f"Premiere Pro did not answer within {READY_TIMEOUT} s: {answer}")
        time.sleep(5)
    return send_file(body, timeout)


def send_file(body, timeout):
    """Send a script as a UTF-8 file for Premiere to evaluate; BridgeTalk doubles backslashes in bodies."""
    with tempfile.TemporaryDirectory(prefix="premiere-relay-") as folder:
        script = Path(folder) / "body.jsx"
        script.write_text(body, encoding="utf-8")
        load = (f"(function (p) {{ var f = new File(p); f.encoding = 'UTF-8'; f.open('r'); var t = f.read();"
                f"f.close(); return eval(t); }})({json.dumps(str(script))});")
        return send(load, timeout)


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


def held(path):
    """Whether any process has the file open."""
    return run_sync(["lsof", "-t", "--", str(path)], 30).stdout.strip() != ""


def written(report, before):
    """The job's report, once it was written after `before`."""
    if fingerprint(report) in (None, before):
        return None
    try:
        return json.loads(report.read_text())
    except ValueError:  # still being written
        return None


def finish(body, report, master, timeout):
    """Run a job that writes a master and a report, and judge it by those files.

    The relay can answer "timed out" while Premiere keeps exporting, so its answer only starts the wait:
    the job is done when its report exists and no process holds the master open.
    """
    before = fingerprint(report)
    try:
        answer = relay(body, timeout)
    except NotReady:
        raise
    except Exception as failure:  # the relay or osascript gave up; the export may still run
        answer = f"{type(failure).__name__}: {failure}"
    deadline = time.monotonic() + timeout
    while True:
        result = written(report, before)
        if result and (result["errors"] or (master.is_file() and not held(master))):
            break
        if time.monotonic() > deadline:
            break
        time.sleep(2)
    if not result or result["errors"] or not master.is_file() or held(master):
        raise RuntimeError(f"Premiere Pro job failed: {answer}; {result}")
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
    result = finish(body, report, master, timeout)
    return {"project": str(project), "master": str(master), "fps": str(rate),
            "frames": int(probe(master, "nb_frames")), "cut_frames": end,
            "transitions": result["transitions"], "warnings": result["warnings"]}


def invoke(tool, args, timeout=300):
    """Run jsx/<tool>.jsx in Premiere with the shared helpers and return its report."""
    with tempfile.TemporaryDirectory(prefix="premiere-report-") as folder:
        report = Path(folder) / "report.json"
        body = (f"var CAVI_ARGS = {json.dumps({**args, 'report': str(report)})};\n"
                + "\n".join((JSX / name).read_text() for name in ("lib.jsx", f"{tool}.jsx", "tail.jsx")))
        answer = relay(body, timeout)
        if not report.is_file():
            raise RuntimeError(f"Premiere {tool} wrote no report; answer: {answer}")
        result = json.loads(report.read_text())
    if answer != "OK" or result["errors"]:
        raise RuntimeError(f"Premiere {tool} failed: " + "; ".join(result["errors"] or [answer]))
    return result


def existing(path, suffix=None):
    path = absolute(path, suffix)
    if not path.is_file():
        raise ValueError(f"No file at {path}")
    return path


def item_ref(ref):
    """A project item is named by its media path (absolute) or its name."""
    return str(absolute(ref)) if ref.startswith(("/", "~")) else ref


def project(action, path, replace, save, timeout):
    """Open, create, save or close a Premiere project."""
    args = {"action": action, "path": None, "save": save}
    if action == "open":
        args["path"] = str(existing(path, ".prproj"))
    elif action == "new":
        target = absolute(path, ".prproj")
        if target.exists() and not replace:
            raise ValueError(f"Already exists (pass replace=true): {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        args["path"] = str(target)
    return invoke("project", args, timeout)


def inspect(sequence, timeout):
    return invoke("inspect", {"sequence": sequence}, timeout)


def import_files(files, bin, timeout):
    paths = [str(existing(file)) for file in files]
    return invoke("import", {"files": paths, "bin": bin}, timeout)


def sequence_preset(preset):
    """A .sqpreset by absolute path or by its file name in Premiere's own presets."""
    if preset.startswith(("/", "~")):
        return str(existing(preset, ".sqpreset"))
    found = sorted((premiere() / "Contents/Settings/SequencePresets").rglob(f"{preset}.sqpreset"))
    if not found:
        raise ValueError(f"No sequence preset named {preset}")
    return str(found[0])


def sequence_new(name, clip, preset, bin, timeout):
    if (clip is None) == (preset is None):
        raise ValueError("Give exactly one of clip or preset")
    args = {"name": name, "bin": bin, "clip": clip and item_ref(clip), "preset": preset and sequence_preset(preset)}
    return invoke("sequence_new", args, timeout)


def clip_place(sequence, item, kind, track, at, in_point, out_point, mode, timeout):
    if in_point is not None and out_point is not None and out_point <= in_point:
        raise ValueError("out_point must be after in_point")
    args = {"sequence": sequence, "item": item_ref(item), "kind": kind, "track": track, "at": at,
            "in_point": in_point, "out_point": out_point, "mode": mode}
    return invoke("clip_place", args, timeout)


def clip_props(sequence, kind, track, at, position_index, props, keyframes, timeout):
    """Motion, opacity and volume values on a placed clip; props and keyframes are keyed by property."""
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "keyframes": keyframes, **props}
    return invoke("clip_props", args, timeout)


def transition_add(sequence, kind, track, at, position_index, transition, frames, edge, alignment, single_sided,
                   timeout):
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "transition": transition, "frames": frames, "edge": edge, "alignment": alignment,
            "single_sided": single_sided}
    return invoke("transition_add", args, timeout)


def media_replace(item, path, timeout):
    """Relink a project item to a new file, then confirm through inspect that the project points at it."""
    target = existing(path)
    changed = invoke("media_replace", {"item": item_ref(item), "path": str(target)}, timeout)
    listed = inspect(None, timeout)
    seen = [clip for lane in (lane for s in listed["sequences"] for lane in s["video"] + s["audio"])
            for clip in lane["clips"] if clip["media_path"] and Path(clip["media_path"]) == target]
    entry = [i for i in listed["items"] if i["media_path"] and Path(i["media_path"]) == target]
    changed["verified"] = bool(entry) and not entry[0]["offline"]
    changed["sequence_clips"] = len(seen)
    if not changed["verified"]:
        raise RuntimeError(f"Premiere did not point {item} at {target}: {changed}")
    return changed


def beat_grid(bpm, beats_per_bar, start, end):
    """One marker per beat from start up to end; the first beat of each bar is the downbeat."""
    if end <= start:
        raise ValueError("end must be after start")
    markers, beat = [], 0
    while (time_s := start + beat * 60 / bpm) < end - 1e-9:
        bar, number = divmod(beat, beats_per_bar)
        markers.append({"time": round(time_s, 6), "name": f"{bar + 1}.{number + 1}",
                        "comment": "downbeat" if number == 0 else "", "duration": 0})
        beat += 1
    return markers


def markers_add(sequence, markers, grid, timeout):
    found = [dict(m) for m in markers]
    if grid:
        found += beat_grid(grid["bpm"], grid["beats_per_bar"], grid["start"], grid["end"])
    if not found:
        raise ValueError("Give markers or a beat_grid")
    return invoke("markers_add", {"sequence": sequence, "markers": found}, timeout)


def mogrt_add(sequence, mogrt, at, video_track, audio_track, duration, text, timeout):
    args = {"sequence": sequence, "mogrt": str(existing(mogrt, ".mogrt")), "at": at, "video_track": video_track,
            "audio_track": audio_track, "duration": duration, "text": text}
    return invoke("mogrt_add", args, timeout)


def export(sequence, master, preset, work_area, replace, timeout):
    """Export a sequence with an .epr preset; judged by the report, the released file and ffprobe frames."""
    master, preset = absolute(master), existing(preset, ".epr")
    if master.exists() and not replace:
        raise ValueError(f"Already exists (pass replace=true): {master}")
    master.parent.mkdir(parents=True, exist_ok=True)
    if master.exists():
        master.unlink()
    with tempfile.TemporaryDirectory(prefix="premiere-report-") as folder:
        report = Path(folder) / "report.json"
        args = {"sequence": sequence, "master": str(master), "preset": str(preset), "work_area": work_area,
                "report": str(report)}
        body = (f"var CAVI_ARGS = {json.dumps(args)};\n"
                + "\n".join((JSX / name).read_text() for name in ("lib.jsx", "export.jsx", "tail.jsx")))
        result = finish(body, report, master, timeout)
    frames = int(probe(master, "nb_frames"))
    expected = round(result["sequence_end"] * result["fps"]) if work_area == "entire" else None
    return {"sequence": result["sequence"], "master": str(master), "fps": result["fps"], "frames": frames,
            "expected_frames": expected, "complete": expected is None or frames == expected,
            "warnings": result["warnings"]}
