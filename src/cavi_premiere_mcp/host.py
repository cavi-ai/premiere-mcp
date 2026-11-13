"""Premiere Pro over a Photoshop BridgeTalk relay, the ProRes cut engine and frame checks."""

import json
import os
import plistlib
import re
import shutil
import tempfile
import time
from fractions import Fraction
from pathlib import Path

from cavi_mcp_core.proc import diagnostics, run_sync

JSX = Path(__file__).with_name("jsx")
CUT = JSX / "cut.jsx"
READY_TIMEOUT = 300
ENCODER_SETTLE = 40
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


def media_encoder():
    return newest("Adobe Media Encoder 20*/Adobe Media Encoder 20*.app")


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
                        "out_point": float(last / fps), "transition": TRANSITIONS.get(transition.get("kind"), transition.get("kind")),
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


def project(action, path, replace, save, close_others, timeout):
    """Open, create, save or close a Premiere project."""
    args = {"action": action, "path": None, "save": save, "close_others": close_others}
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


def transitions(timeout):
    """Every video and audio transition name Premiere offers, plus the short aliases for four of them."""
    found = invoke("transitions", {}, timeout)
    return {"video": found["video"], "audio": found["audio"], "aliases": TRANSITIONS}


def preset_roots(kind):
    """(source, folder) pairs holding .epr export or .sqpreset sequence presets."""
    home = Path.home() / "Documents/Adobe"
    if kind == "export":
        roots = [("premiere", premiere() / "Contents/MediaIO/systempresets")]
        roots += [("media_encoder", app / "Contents/MediaIO/systempresets")
                  for app in sorted(Path("/Applications").glob("Adobe Media Encoder 20*/Adobe Media Encoder 20*.app"))]
        roots += [("user", folder) for folder in sorted((home / "Adobe Media Encoder").glob("*/Presets"))]
    else:
        roots = [("premiere", premiere() / "Contents/Settings/SequencePresets")]
        roots += [("user", folder) for folder in sorted((home / "Premiere Pro").glob("*/Profile-*/Settings/Custom"))]
    return roots


def format_code(folder):
    """The format of a system preset folder such as 4E49434B_48323634 (its second half as ASCII)."""
    try:
        return bytes.fromhex(folder.split("_")[1]).decode("ascii").strip()
    except (IndexError, ValueError):
        return ""


def presets(kind):
    """Presets by name: {name, format, source, path}; a duplicated name is addressed as format/name."""
    suffix = ".epr" if kind == "export" else ".sqpreset"
    found = []
    for source, root in preset_roots(kind):
        for path in sorted(root.rglob(f"*{suffix}")):
            found.append({"name": path.stem, "format": "user" if source == "user" else format_code(path.parent.name) or path.parent.name,
                          "source": source, "path": str(path)})
    return found


def resolve_preset(kind, preset):
    """A preset by absolute path, by name, or as format/name when the name is not unique."""
    suffix = ".epr" if kind == "export" else ".sqpreset"
    preset = str(preset)
    if preset.startswith(("/", "~")):
        return str(existing(preset, suffix))
    matches = [p for p in presets(kind) if preset in (p["name"], f"{p['format']}/{p['name']}")]
    if not matches:
        raise ValueError(f"No {kind} preset named {preset}; list them with premiere_presets")
    if len({p["path"] for p in matches}) > 1:
        # User presets win, then Premiere's own, over Media Encoder's.
        for source in ("user", "premiere"):
            chosen = [p for p in matches if p["source"] == source]
            if len({p["path"] for p in chosen}) == 1:
                return chosen[0]["path"]
        raise ValueError(f"{preset} names several presets; use format/name: "
                         + ", ".join(sorted({f"{p['format']}/{p['name']}" for p in matches})))
    return matches[0]["path"]


def sequence_preset(preset):
    return resolve_preset("sequence", preset)


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
            "transition": TRANSITIONS.get(transition, transition), "frames": frames, "edge": edge, "alignment": alignment,
            "single_sided": single_sided}
    return invoke("transition_add", args, timeout)


def one_clip(at, position_index, name=None):
    if sum(value is not None for value in (at, position_index, name)) != 1:
        raise ValueError("Give exactly one of at, position_index or name")


def clip_edit(sequence, kind, track, at, position_index, name, edit, timeout):
    """Trim, move, enable, rename, link, unlink or remove one placed clip."""
    one_clip(at, position_index, name)
    if edit.get("remove") and any(v is not None and k not in ("remove", "keep_linked") for k, v in edit.items()):
        raise ValueError("remove cannot be combined with other edits")
    if all(v is None for v in edit.values()):
        raise ValueError("Give at least one edit")
    start, end = edit.get("trim_start"), edit.get("trim_end")
    if start is not None and end is not None and end <= start:
        raise ValueError("trim_end must be after trim_start")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "name": name, **edit}
    return invoke("clip_edit", args, timeout)


def razor(sequence, times, kind, track, timeout):
    if track is not None and kind == "all":
        raise ValueError("Give kind video or audio with a track")
    return invoke("razor", {"sequence": sequence, "times": sorted(set(times)), "kind": kind, "track": track}, timeout)


def clip_speed(sequence, kind, track, at, position_index, speed, duration, reverse, maintain_pitch, ripple, timeout):
    one_clip(at, position_index)
    if (speed is None) == (duration is None):
        raise ValueError("Give exactly one of speed or duration")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "speed": speed, "duration": duration, "reverse": reverse, "maintain_pitch": maintain_pitch,
            "ripple": ripple}
    return invoke("clip_speed", args, timeout)


def sequence_set(sequence, change, timeout):
    """Settings, in/out points, nest, duplicate, rename or delete a sequence."""
    if all(v is None or v is False for v in change.values()):
        raise ValueError("Give at least one change")
    if change.get("remove") and any(v is not None and v is not False for k, v in change.items() if k != "remove"):
        raise ValueError("remove cannot be combined with other changes")
    return invoke("sequence_set", {"sequence": sequence, **change}, timeout)


def tracks(sequence, add_video, add_audio, states, timeout):
    if not (add_video or add_audio or states):
        raise ValueError("Give tracks to add or track states to set")
    return invoke("tracks", {"sequence": sequence, "add_video": add_video, "add_audio": add_audio,
                             "tracks": states}, timeout)


def png_size(path):
    with open(path, "rb") as file:
        head = file.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"Not a PNG: {path}")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def frame_export(sequence, times, folder, prefix, timeout):
    """PNG stills of a sequence at the given seconds; every file is checked on disk."""
    folder = absolute(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = [str(folder / f"{prefix}_{i + 1:03d}_{time:.3f}s") for i, time in enumerate(times)]
    result = invoke("frame_export", {"sequence": sequence, "times": list(times), "paths": paths}, timeout)
    for frame in result["frames"]:
        path = Path(frame["path"])
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Premiere wrote no frame at {path}")
        frame["width"], frame["height"] = png_size(path)
    return result


def effects(filter_, timeout):
    return invoke("effects", {"filter": filter_}, timeout)


def effect_add(sequence, kind, track, at, position_index, effect, timeout):
    one_clip(at, position_index)
    return invoke("effect_add", {"sequence": sequence, "kind": kind, "track": track, "at": at,
                                 "position_index": position_index, "effect": effect}, timeout)


def effect_set(sequence, kind, track, at, position_index, component, component_index, list_, params, timeout):
    """Set or list the parameters of a clip's component, by display names."""
    one_clip(at, position_index)
    if not list_ and not params:
        raise ValueError("Give params to set or list=true")
    if params and not component:
        raise ValueError("Give the component the parameters belong to")
    for spec in params:
        if spec.get("keyframes"):
            if spec.get("value") is not None or spec.get("color"):
                raise ValueError(f"{spec['name']}: give either a value or keyframes")
        elif (spec.get("value") is None) == (spec.get("color") is None):
            raise ValueError(f"{spec['name']}: give exactly one of value or color")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "component": component, "component_index": component_index, "list": list_, "params": params}
    return invoke("effect_set", args, timeout)


def clip_fit(sequence, track, at, position_index, mode, timeout):
    one_clip(at, position_index)
    return invoke("clip_fit", {"sequence": sequence, "track": track, "at": at,
                               "position_index": position_index, "mode": mode}, timeout)


def items(item, change, timeout):
    """Rename, move, label, subclip, interpret, attach a proxy to, set metadata on or delete a project item."""
    if all(v is None or v is False for v in change.values()):
        raise ValueError("Give at least one change")
    if change.get("remove") and any(v is not None and v is not False for k, v in change.items() if k != "remove"):
        raise ValueError("remove cannot be combined with other changes")
    if change.get("proxy"):
        change = {**change, "proxy": {"path": str(existing(change["proxy"]["path"]))}}
    sub = change.get("subclip")
    if sub and sub["out_point"] <= sub["in_point"]:
        raise ValueError("out_point must be after in_point")
    result = invoke("items", {"item": item_ref(item), **change}, timeout)
    result.setdefault("item", None)
    return result


def scene_times(media, threshold):
    """Source times of hard cuts in a movie, from ffmpeg's scene score."""
    result = run_sync([ffprobe().replace("ffprobe", "ffmpeg"), "-hide_banner", "-i", str(media), "-an", "-vf",
                       f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], 3600)
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def scene_detect(sequence, track, at, position_index, threshold, apply, include_audio, timeout):
    """Cut times inside a placed clip, as timeline seconds; optionally razor or mark them."""
    one_clip(at, position_index)
    listed = inspect(sequence, timeout)["sequences"]
    if sequence is None and len(listed) > 1:
        raise ValueError("Give the sequence by name")
    lane = listed[0]["video"][track]
    clips = lane["clips"]
    clip = clips[position_index] if position_index is not None else next(
        (c for c in clips if c["start"] - 0.0005 <= at < c["end"] - 0.0005), None)
    if clip is None or not clip["media_path"]:
        raise ValueError("No clip with media at that place")
    times = [clip["start"] + t - clip["in_point"] for t in scene_times(clip["media_path"], threshold)
             if clip["in_point"] < t < clip["out_point"]]
    times = [round(t, 3) for t in times]
    result = {"clip": clip["name"], "cuts": times, "applied": apply}
    if times and apply == "cuts":
        host_razor = razor(sequence, times, "all" if include_audio else "video", None if include_audio else track,
                           timeout)
        result["clips_after"] = host_razor["clips_after"]
    elif times and apply == "markers":
        result["markers"] = markers_add(sequence, [{"time": t, "name": "cut", "comment": "", "duration": 0}
                                                    for t in times], None, timeout)["total"]
    return result


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


def caption_preset(preset, on, folder):
    """A copy of an .epr preset in `folder` with DoCaptions set to on."""
    value = "true" if on else "false"
    text = Path(preset).read_text(encoding="utf-8")
    if "<DoCaptions>" in text:
        text = re.sub(r"<DoCaptions>(true|false)</DoCaptions>", f"<DoCaptions>{value}</DoCaptions>", text)
    elif "<DoAudio>" in text:
        text = text.replace("<DoAudio>true</DoAudio>", f"<DoAudio>true</DoAudio>\n\t<DoCaptions>{value}</DoCaptions>", 1)
    else:
        raise ValueError(f"Cannot add captions to preset {preset}")
    copy = Path(folder) / f"{Path(preset).stem} captions.epr"
    copy.write_text(text, encoding="utf-8")
    return copy


def launch_encoder():
    """Start Media Encoder when it is not running and give it time to accept jobs."""
    app = media_encoder()
    if not running(app):
        start(app)
        deadline = time.monotonic() + 120
        while not running(app) and time.monotonic() < deadline:
            time.sleep(2)
        time.sleep(ENCODER_SETTLE)


def render(tool, sequence, master, preset, range_, replace, timeout, burn_captions=None):
    """Run export.jsx or encode.jsx; judged by the report, the released file and ffprobe frames.

    Every input is checked before Premiere or Media Encoder is touched.
    """
    if range_ not in ("entire", "in_out", "work_area"):
        raise ValueError(f"range is entire, in_out or work_area: {range_}")
    master, preset = absolute(master), Path(resolve_preset("export", preset) if preset else prores_preset())
    if master.exists() and not replace:
        raise ValueError(f"Already exists (pass replace=true): {master}")
    with tempfile.TemporaryDirectory(prefix="premiere-render-") as folder:
        if burn_captions is not None:
            preset = caption_preset(preset, burn_captions, folder)
        master.parent.mkdir(parents=True, exist_ok=True)
        if master.exists():
            master.unlink()
        if tool == "encode":
            launch_encoder()
        report = Path(folder) / "report.json"
        args = {"sequence": sequence, "master": str(master), "preset": str(preset), "range": range_,
                "report": str(report)}
        body = (f"var CAVI_ARGS = {json.dumps(args)};\n"
                + "\n".join((JSX / name).read_text() for name in ("lib.jsx", f"{tool}.jsx", "tail.jsx")))
        result = finish(body, report, master, timeout)
    frames = int(probe(master, "nb_frames"))
    expected = round(result["span"] * result["fps"])
    return {"sequence": result["sequence"], "master": str(master), "fps": result["fps"], "frames": frames,
            "expected_frames": expected, "complete": frames == expected, "warnings": result["warnings"]}


def export(sequence, master, preset, range_, replace, timeout, burn_captions=None):
    """Export a sequence with an .epr preset."""
    return render("export", sequence, master, preset, range_, replace, timeout, burn_captions)


def encode(sequence, master, preset, range_, replace, timeout):
    """Queue a sequence in Media Encoder and start the batch; the file is the proof."""
    return render("encode", sequence, master, preset, range_, replace, timeout)


def auto_reframe(sequence, ratio, motion, name, nest, timeout):
    """A new sequence at another aspect ratio, given as "9:16"."""
    try:
        numerator, denominator = (int(part) for part in ratio.split(":"))
    except ValueError:
        raise ValueError(f"Give the ratio as width:height, such as 9:16: {ratio}") from None
    if numerator < 1 or denominator < 1:
        raise ValueError(f"Give the ratio as width:height, such as 9:16: {ratio}")
    args = {"sequence": sequence, "numerator": numerator, "denominator": denominator, "motion": motion,
            "name": name or f"{ratio.replace(':', 'x')}", "nest": nest}
    return invoke("auto_reframe", args, timeout)


def interchange(sequence, action, path, replace, audio_rate, bits, timeout):
    """Export a sequence as FCP XML, AAF or OMF, or import an FCP XML; the file or the new sequence is checked."""
    suffix = {"xml": ".xml", "aaf": ".aaf", "omf": ".omf", "import_xml": ".xml"}[action]
    if action == "import_xml":
        target = existing(path, suffix)
    else:
        target = absolute(path, suffix)
        if target.exists() and not replace:
            raise ValueError(f"Already exists (pass replace=true): {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
    result = invoke("interchange", {"sequence": sequence, "action": action, "path": str(target),
                                    "audio_rate": audio_rate, "bits": bits}, timeout)
    if action == "import_xml":
        added = [n for n in result["sequences_after"] if n not in result["sequences_before"]]
        result["imported"] = added or result["sequences_after"][len(result["sequences_before"]):]
        if len(result["sequences_after"]) <= len(result["sequences_before"]):
            raise RuntimeError(f"Premiere imported no sequence from {target}")
        return {"action": action, "path": str(target), "size": target.stat().st_size,
                "imported": result["imported"], "warnings": result["warnings"]}
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"Premiere wrote no {action} file at {target}")
    return {"action": action, "path": str(target), "size": target.stat().st_size,
            "sequence": result["sequence"], "warnings": result["warnings"]}


def srt_count(path):
    """The number of cues in an .srt file."""
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return len([block for block in text.split("\n\n") if "-->" in block])


def captions(sequence, file, start, format_, timeout):
    """A caption track from an .srt file; the caption count is read from the file."""
    source = existing(file, ".srt")
    count = srt_count(source)
    result = invoke("captions", {"sequence": sequence, "file": str(source), "start": start, "format": format_},
                    timeout)
    result["captions"] = count
    return result


