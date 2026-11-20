"""Premiere Pro over an Adobe Bridge BridgeTalk relay, the ProRes cut engine and frame checks."""

import json
import math
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from cavi_mcp_core import apps
from cavi_mcp_core.contracts import OperationRejected, OperationUnknown
from cavi_mcp_core.lock import FileLock
from cavi_mcp_core.proc import diagnostics, run_sync
from cavi_mcp_core.server import need, reject_foreign

JSX = Path(__file__).with_name("jsx")
READY_TIMEOUT = 300
BRIDGE_PING = 30
BRIDGE_LAUNCH = 60
# Seconds after Bridge starts during which a silent relay means Bridge is still loading its startup scripts.
BRIDGE_STARTUP = 240
RELAY = "cavi-bridge-relay.jsx"
RELAY_SOURCE = JSX / "bridge_relay.jsx"
MAILBOX = Path.home() / "Library/Application Support/cavi-bridge-relay"
APPROVAL = ("Adobe Bridge has not run the cavi-bridge-relay startup script: approve it in Bridge "
            "Settings > Startup Scripts, or run premiere_bridge_install")
PRESET = "*.app/Contents/MediaIO/systempresets/3F3F3F3F_4D6F6F56/Apple ProRes 422 HQ.epr"
TRANSITIONS = {"cross_dissolve": "Cross Dissolve", "film_dissolve": "Film Dissolve",
               "dip_to_white": "Dip to White", "dip_to_black": "Dip to Black"}
# The start of every answer that reports a failure instead of a script's value.
FAILED = "ERROR "
# A job takes at most 7200 s; mailbox files older than a day belong to calls that are gone.
MAILBOX_KEEP = 24 * 3600
# More markers than this in one call would make a script too large for Premiere to run.
MAX_MARKERS = 5000
MAX_PLACEMENTS = 500

# (name, bundle identifier, glob under /Applications, environment override). An identifier ending in a dot
# takes the major version after it (com.adobe.PremierePro.27), so every release is found.
PREMIERE = ("Adobe Premiere Pro", "com.adobe.PremierePro.",
            "Adobe Premiere Pro 20*/Adobe Premiere Pro 20*.app", "CAVI_PREMIERE_APP")
BRIDGE = ("Adobe Bridge", "com.adobe.bridge", "Adobe Bridge 20*/Adobe Bridge 20*.app", "CAVI_BRIDGE_APP")
MEDIA_ENCODER = ("Adobe Media Encoder", "com.adobe.ame.application.",
                 "Adobe Media Encoder 20*/Adobe Media Encoder 20*.app", "CAVI_MEDIA_ENCODER_APP")


class NotReady(OperationRejected):
    """Premiere Pro never answered the relay, so no job was sent."""

    def __init__(self, message, code="RELAY_NOT_APPROVED"):
        super().__init__(message, code)


# One call at a time drives Premiere, across every server process of this user.
ACCESS = FileLock(Path(tempfile.gettempdir()) / "cavi-premiere.lock", follow=False)
_call = threading.local()


@contextmanager
def exclusive(timeout):
    """Premiere for this call alone until it ends; yields the call's deadline. A call inside another keeps the
    outer deadline, and waiting for another call counts against the timeout."""
    outer = getattr(_call, "deadline", None)
    deadline = time.monotonic() + timeout if outer is None else min(outer, time.monotonic() + timeout)
    while not ACCESS.acquire(blocking=False):
        if time.monotonic() > deadline:
            raise OperationRejected(f"Premiere Pro was busy with another call for {timeout} s", "PREMIERE_BUSY")
        time.sleep(0.1)
    _call.deadline = deadline
    try:
        yield deadline
    finally:
        _call.deadline = outer
        ACCESS.release()


def left(deadline, least=0.0):
    return max(deadline - time.monotonic(), least)


def application(spec):
    """The installed .app of an Adobe application: the override, else the newest under /Applications, of the
    newest major version installed."""
    name, identifier, pattern, env = spec
    if identifier.endswith("."):
        override = os.environ.get(env)
        found = [Path(override).expanduser()] if override else apps.APPLICATIONS.glob(pattern)
        majors = [m for path in found if (m := re.fullmatch(re.escape(identifier) + r"(\d+)",
                                                             str(apps.bundle_info(path).get("CFBundleIdentifier"))))]
        if majors:
            identifier = max(majors, key=lambda m: int(m[1]))[0]
    return apps.bundle(name, identifier, pattern, env).path


def premiere():
    return application(PREMIERE)


def bridge():
    return application(BRIDGE)


def media_encoder():
    return application(MEDIA_ENCODER)


def startup_folder():
    found = sorted((Path.home() / "Library/Application Support/Adobe").glob("Bridge 20*"))
    if not found:
        raise ValueError("Adobe Bridge has no user folder; start Bridge once")
    return found[-1] / "Startup Scripts"


def relay_state():
    try:
        installed = startup_folder() / RELAY
    except ValueError:
        return "no"
    if not installed.exists():
        return "no"
    return "yes" if installed.read_bytes() == RELAY_SOURCE.read_bytes() else "differs"


def bridge_install():
    bridge()
    folder = startup_folder()
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RELAY_SOURCE, folder / RELAY)
    return {"path": str(folder / RELAY), "matches": relay_state() == "yes",
            "next": "Restart Adobe Bridge, then approve cavi-bridge-relay in Bridge Settings > Startup Scripts once"}


def prores_preset():
    found = sorted(premiere().parent.glob(PRESET))
    if not found:
        raise ValueError("This Premiere Pro has no Apple ProRes 422 HQ export preset")
    return found[-1]


def running(app):
    """Pids of the app's main executable; its helpers can outlive it."""
    executable = apps.bundle_executable(app)
    return [] if executable is None else [process.pid for process in apps.processes(executable)]


def describe(spec):
    """An installed application's path, version and pids, or why it is not available."""
    try:
        app = application(spec)
    except (ValueError, OSError) as failure:
        return {"app": None, "version": "", "pids": [], "error": str(failure)}
    return {"app": str(app), "version": apps.bundle_info(app).get("CFBundleShortVersionString", ""),
            "pids": running(app)}


def status():
    """What is installed and running; a missing application is reported in its entry, never raised."""
    try:
        preset = str(prores_preset())
    except (ValueError, OSError):
        preset = None
    return {"premiere": describe(PREMIERE), "bridge": describe(BRIDGE), "media_encoder": describe(MEDIA_ENCODER),
            "relay": relay_state(), "mailbox": str(MAILBOX), "prores_preset": preset}


def literal(value):
    """JSON text of a value for a script global; NaN and infinity are not JSON and are refused."""
    try:
        return json.dumps(value, allow_nan=False)
    except ValueError:
        raise ValueError("Every number must be finite") from None


def start(app):
    """Open an app in the background when it is not running."""
    if not running(app):
        result = run_sync(["open", "-g", "-a", str(app)], 60)
        if result.returncode:
            raise RuntimeError(f"{app.stem} did not launch: " + diagnostics(result))


def sweep(box, age=MAILBOX_KEEP):
    """Remove mailbox files left by calls that gave up before their job finished."""
    for leftover in box.iterdir():
        if leftover.suffix not in (".job", ".part", ".reply"):
            continue
        try:
            stale = time.time() - leftover.stat().st_mtime > age
        except FileNotFoundError:  # another call removed it
            continue
        if stale:
            leftover.unlink(missing_ok=True)


def mailbox_send(target, body, timeout, wait=None, box=None):
    """Hand a job to the Bridge relay and wait for its reply: (ok, result). wait is how long to wait
    for the relay to pick the job up before raising the approval message."""
    box = box or MAILBOX
    box.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Bridge creates the folder with the default mode; jobs are scripts Premiere runs.
    if box.stat().st_mode & 0o777 != 0o700:
        box.chmod(0o700)
    sweep(box)
    name = uuid.uuid4().hex
    job, reply = box / f"{name}.job", box / f"{name}.reply"
    part = box / f"{name}.part"
    part.write_text(f"{target}\n{body}", encoding="utf-8")
    part.rename(job)
    deadline = time.monotonic() + (timeout if wait is None else min(wait, timeout))
    try:
        while not reply.exists():
            if time.monotonic() > deadline:
                if wait is not None:
                    raise NotReady(APPROVAL)
                raise TimeoutError(f"No answer from {target} within {timeout} s; the job may still be running in it")
            time.sleep(0.05)
        head, _, result = reply.read_text(encoding="utf-8").partition("\n")
        return head == "ok", result
    finally:
        for leftover in (job, part, reply):
            leftover.unlink(missing_ok=True)


def bridge_age(app):
    """Seconds since the oldest Bridge process started; infinite when none runs."""
    executable = apps.bundle_executable(app)
    # ps prints local start times such as "Fri Nov 13 14:46:02 2026".
    started = [time.mktime(time.strptime(process.started))
               for process in (apps.processes(executable) if executable else [])]
    return time.time() - min(started) if started else math.inf


def relay(body, timeout, target="premierepro"):
    """Send ExtendScript to an Adobe app through Bridge BridgeTalk once the app answers messages. The call ends
    by its timeout, the wait for Premiere and for other calls included."""
    with exclusive(timeout) as deadline:
        app = bridge()
        launched = not running(app)
        start(app)
        start(premiere())
        # A Premiere that is still starting refuses messages with "TARGET COULD NOT BE LAUNCHED".
        began = time.monotonic()
        ready_by = min(deadline, began + READY_TIMEOUT)
        wait = BRIDGE_PING + (BRIDGE_LAUNCH if launched else 0)
        while True:
            try:
                answer = send("'ready'", min(15, left(ready_by, 1)), target, wait)
            except NotReady:
                # A Bridge that started moments ago has not run its startup scripts yet; that is not a missing
                # approval.
                if bridge_age(app) >= BRIDGE_STARTUP:
                    raise
                answer = "Adobe Bridge is still starting"
            except TimeoutError as failure:  # Premiere is busy or frozen; no job has been sent yet
                answer = str(failure)
            if answer == "ready":
                break
            wait = None
            if time.monotonic() >= ready_by:
                raise NotReady(f"Premiere Pro did not answer within {round(time.monotonic() - began)} s: {answer}",
                               "PREMIERE_NOT_READY")
            time.sleep(min(5, left(ready_by)))
        return send_file(body, left(deadline, 1), target)


def send_file(body, timeout, target="premierepro"):
    """Send a script as a UTF-8 file for Premiere to evaluate; BridgeTalk doubles backslashes in bodies."""
    with tempfile.TemporaryDirectory(prefix="premiere-relay-") as folder:
        script = Path(folder) / "body.jsx"
        script.write_text(body, encoding="utf-8")
        load = (f"(function (p) {{ var f = new File(p); f.encoding = 'UTF-8'; f.open('r'); var t = f.read();"
                f"f.close(); return eval(t); }})({json.dumps(str(script))});")
        return send(load, timeout, target)


def send(body, timeout, target="premierepro", wait=None):
    """The target's last value, or FAILED followed by the message; the relay answers through the mailbox."""
    ok, result = mailbox_send(target, body, timeout, wait)
    return result if ok else FAILED + result


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
    body = (f"var CAVI_ARGS = {literal(args)};\nvar CAVI_REPORT = {literal(report and str(report))};\n"
            + script.read_text(encoding="utf-8"))
    answer = relay(body, timeout)
    if answer.startswith(FAILED):
        raise RuntimeError(f"Premiere script failed: {answer.removeprefix(FAILED)}")
    result = {"answer": answer}
    if report:
        if fingerprint(report) in (None, before):
            raise RuntimeError(f"Premiere script wrote no report to {report}; answer: {answer}")
        result["report"] = read_report(report)
    return result


def read_report(path):
    """A job's JSON report; a half-written one is an error naming the file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as failure:
        raise RuntimeError(f"Premiere left an unreadable report at {path}: {failure}") from None


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


def finish(body, report, master, timeout, failure=None):
    """Run a job that writes a master and a report, and judge it by those files.

    The relay can answer "timed out" while Premiere keeps exporting, so its answer only starts the wait:
    the job is done when its report exists and no process holds the master open. A job that writes the
    failure file has failed, and the wait ends.
    """
    deadline = time.monotonic() + timeout
    before = fingerprint(report)
    try:
        answer = relay(body, left(deadline, 1))
    except TimeoutError as timed_out:  # the job's answer never came; the export may still run
        answer = f"{type(timed_out).__name__}: {timed_out}"
    while True:
        if failure and failure.is_file():
            raise RuntimeError(f"Media Encoder could not encode {master}: {failure.read_text(encoding='utf-8')}")
        result = written(report, before)
        if result and (result["errors"] or (master.is_file() and not held(master))):
            break
        if time.monotonic() > deadline:
            break
        time.sleep(min(2, left(deadline, 0.05)))
    if not result or result["errors"] or not master.is_file() or held(master):
        raise RuntimeError(f"Premiere Pro job failed: {answer}; {result}")
    return result


def ffmpeg_tool(name):
    """An FFmpeg command-line tool from PATH or the usual Homebrew folders."""
    found = shutil.which(name, path=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    if not found:
        raise ValueError(f"Install {name} (FFmpeg) to read frame rates, find scene cuts and verify masters")
    return found


def ffprobe():
    return ffmpeg_tool("ffprobe")


def probe(path, entries):
    result = run_sync([ffprobe(), "-v", "error", "-select_streams", "v:0", "-show_entries",
                       f"stream={entries}", "-of", "csv=p=0", str(path)], 60)
    if result.returncode or not result.stdout.split():
        raise RuntimeError(f"ffprobe could not read {path}: " + diagnostics(result))
    # A movie with a timecode track lists its video stream twice; the first line is the stream's.
    return result.stdout.split()[0]


def streams(path, *options):
    result = run_sync([ffprobe(), "-v", "error", *options, "-show_entries",
                       "stream=codec_type,nb_frames,nb_read_packets,duration", "-of", "json", str(path)], 60)
    if result.returncode:
        raise RuntimeError(f"ffprobe could not read {path}: " + diagnostics(result))
    return json.loads(result.stdout).get("streams", [])


def master_frames(master, fps):
    """Video frames of a written master, from its packets when the container keeps no count; for a master
    without video, the frames at fps its audio lasts. A master that cannot be counted leaves the outcome
    unknown: the job has run."""
    try:
        found = streams(master)
        video = [s for s in found if s.get("codec_type") == "video"]
        if video and video[0].get("nb_frames", "").isdigit():
            return int(video[0]["nb_frames"])
        if video:
            return int(streams(master, "-count_packets", "-select_streams", "v:0")[0]["nb_read_packets"])
        audio = [s for s in found if s.get("codec_type") == "audio" and "duration" in s]
        if not audio:
            raise RuntimeError("no video or audio stream")
        return round(Fraction(audio[0]["duration"]) * Fraction(fps))
    except (ValueError, LookupError, RuntimeError) as error:
        raise OperationUnknown(f"{master} was written but its frames could not be counted: {error}") from error


def plan(clips, fps):
    """Clips snapped to the frame grid, in timeline order, without overlaps; and the cut's end frame."""
    names, planned, end = {}, [], 0
    for number, clip in enumerate(clips, 1):
        file = absolute(clip["file"])
        if not file.is_file():
            raise FileNotFoundError(f"Clip {number}: no file at {file}")
        if names.setdefault(file.name, file) != file:
            raise ValueError(f"Clip {number}: another clip file is also named {file.name}")
        # Half a frame rounds up, as Math.round does in the scripts.
        start, first, last = (math.floor(Fraction(clip[key]) * fps + Fraction(1, 2))
                              for key in ("start", "in_point", "out_point"))
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
        raise FileNotFoundError(f"No audio file at {audio}")
    report = project.with_suffix(".report.json")
    present = [path for path in (project, master, report) if path.exists()]
    if present and not replace:
        raise ValueError("Already exists (pass replace=true): " + ", ".join(map(str, present)))
    rate = Fraction(probe(absolute(clips[0]["file"]), "r_frame_rate"))
    planned, end = plan(clips, rate)
    preset = prores_preset()
    for path in present:
        path.unlink()
    project.parent.mkdir(parents=True, exist_ok=True)
    master.parent.mkdir(parents=True, exist_ok=True)
    args = {"project": str(project), "clips": planned, "audio": audio and str(audio), "master": str(master),
            "preset": str(preset), "fps": round(rate), "report": str(report)}
    result = finish(tool_script("cut", args), report, master, timeout)
    return {"project": str(project), "master": str(master), "fps": str(rate),
            "frames": master_frames(master, rate), "cut_frames": end,
            "transitions": result["transitions"], "warnings": result["warnings"]}


def tool_script(tool, args):
    """The text of jsx/<tool>.jsx between the shared helpers and the report writer, with its arguments."""
    parts = [(JSX / name).read_text(encoding="utf-8") for name in ("lib.jsx", f"{tool}.jsx", "tail.jsx")]
    return f"var CAVI_ARGS = {literal(args)};\n" + "\n".join(parts)


def invoke(tool, args, timeout=300):
    """Run jsx/<tool>.jsx in Premiere with the shared helpers and return its report."""
    with tempfile.TemporaryDirectory(prefix="premiere-report-") as folder:
        report = Path(folder) / "report.json"
        answer = relay(tool_script(tool, {**args, "report": str(report)}), timeout)
        if not report.is_file():
            raise RuntimeError(f"Premiere {tool} wrote no report; answer: {answer}")
        result = read_report(report)
    if answer != "OK" or result["errors"]:
        raise RuntimeError(f"Premiere {tool} failed: " + "; ".join(result["errors"] or [answer]))
    return result


def existing(path, suffix=None):
    path = absolute(path, suffix)
    if not path.is_file():
        raise FileNotFoundError(f"No file at {path}")
    return path


def item_ref(ref):
    """A project item is named by its media path (absolute) or its name."""
    return str(absolute(ref)) if ref.startswith(("/", "~")) else ref


PROJECT_USES = {"open": {"path", "close_others"}, "new": {"path", "replace", "close_others"},
                "save": {"path", "replace"}, "close": {"save"}}


def project(action, path, replace, save, close_others, timeout):
    """Open, create, save or close a Premiere project."""
    reject_foreign(action, {"path": path, "replace": replace or None, "save": save or None,
                            "close_others": close_others or None}, PROJECT_USES[action])
    args = {"action": action, "path": None, "save": save, "close_others": close_others}
    if action == "open":
        args["path"] = str(existing(need(path, "path", action), ".prproj"))
    elif action == "new":
        target = absolute(need(path, "path", action), ".prproj")
        if target.exists() and not replace:
            raise ValueError(f"Already exists (pass replace=true): {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        args["path"] = str(target)
    elif action == "save" and path:
        # The JSX removes a replaced file, after it has checked that no open project is at that path.
        target = absolute(path, ".prproj")
        if target.exists() and not replace:
            raise ValueError(f"Already exists (pass replace=true): {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        args["path"], args["replace"] = str(target), replace
    elif action == "save" and replace:
        raise ValueError("replace needs path")
    return invoke("project", args, timeout)


def inspect(sequence, timeout, active=False, items=True, tracks=True):
    """The project; with active and no sequence given, only the active sequence, the one scripts act on.
    items and tracks false leave out the project items and each sequence's tracks and markers."""
    return invoke("inspect", {"sequence": sequence, "active": active, "items": items, "tracks": tracks}, timeout)


def single_sequence(listed, sequence):
    """The one sequence inspect listed for a name or id; a name several sequences share is refused, as the
    scripts refuse it."""
    if len(listed) > 1:
        raise ValueError(f"{len(listed)} sequences match {sequence}; give one of their ids: "
                         + ", ".join(info["id"] for info in listed))
    return listed[0]


def acted_on(sequence, timeout):
    """The sequence the scripts act on, with its tracks in seconds: the one named, else the active one."""
    listed = inspect(sequence, timeout, active=True, items=False)["sequences"]
    if not listed:
        raise ValueError(f"No sequence {sequence}" if sequence else "No active sequence")
    return single_sequence(listed, sequence)


def sequence_open(sequence, timeout):
    return invoke("sequence_open", {"sequence": sequence}, timeout)


def import_files(files, bin, timeout):
    paths = [str(existing(file)) for file in files]
    return invoke("import", {"files": paths, "bin": bin}, timeout)


def transitions(timeout):
    """Every video and audio transition name Premiere offers, plus the short aliases for four of them."""
    found = invoke("transitions", {}, timeout)
    return {"video": found["video"], "audio": found["audio"], "aliases": TRANSITIONS}


def preset_roots(kind):
    """(source, folder) pairs holding .epr export or .sqpreset sequence presets; Premiere's own when it is found."""
    home = Path.home() / "Documents/Adobe"
    try:
        installed = premiere()
    except apps.AppUnavailable:
        installed = None
    own = "Contents/MediaIO/systempresets" if kind == "export" else "Contents/Settings/SequencePresets"
    roots = [("premiere", installed / own)] if installed else []
    if kind == "export":
        roots += [("media_encoder", app / "Contents/MediaIO/systempresets")
                  for app in sorted(Path("/Applications").glob("Adobe Media Encoder 20*/Adobe Media Encoder 20*.app"))]
        roots += [("user", folder) for folder in sorted((home / "Adobe Media Encoder").glob("*/Presets"))]
    else:
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


def all_presets():
    return {"export": presets("export"), "sequence": presets("sequence")}


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


def clips_place(sequence, clips, timeout):
    """Place project items on one sequence in one job, in list order; clips are {item, at, kind, track,
    in_point, out_point, mode}."""
    for clip in clips:
        if clip["in_point"] is not None and clip["out_point"] is not None and clip["out_point"] <= clip["in_point"]:
            raise ValueError(f"out_point must be after in_point ({clip['item']} at {clip['at']} s)")
    return invoke("clip_place", {"sequence": sequence,
                                 "clips": [{**clip, "item": item_ref(clip["item"])} for clip in clips]}, timeout)


def clip_place(sequence, item, kind, track, at, in_point, out_point, mode, timeout, speed=None, reversed_=False):
    """One placement; speed (percent) and reversed_ retime it to play in_point to out_point of the source."""
    result = clips_place(sequence, [{"item": item, "at": at, "kind": kind, "track": track, "in_point": in_point,
                                     "out_point": out_point, "mode": mode, "speed": speed,
                                     "reversed": reversed_}], timeout)
    result["clip"] = result.pop("clips")[0]
    return result


def place(sequence, item, at, kind, track, in_point, out_point, mode, clips, timeout):
    """One clip from item and at, or every entry of clips in one job; an entry's missing kind, track, in_point,
    out_point and mode are the call's own."""
    if clips:
        if item is not None or at is not None:
            raise ValueError("Give item and at, or clips, not both")
        shared = {"kind": kind, "track": track, "in_point": in_point, "out_point": out_point, "mode": mode}
        return clips_place(sequence, [{**shared, **{k: v for k, v in clip.items() if v is not None}}
                                      for clip in clips], timeout)
    if item is None or at is None:
        raise ValueError("Give item and at, or clips")
    return clip_place(sequence, item, kind, track, at, in_point, out_point, mode, timeout)


def clip_props(sequence, kind, track, at, position_index, props, keyframes, timeout):
    """Motion, opacity, volume and pan values on a placed clip; props and keyframes are keyed by property."""
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    if props.get("pan") is not None and kind != "audio":
        raise ValueError("pan is for audio clips: give kind=audio")
    args ={"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "keyframes": keyframes, **props}
    return invoke("clip_props", args, timeout)


def transition_add(sequence, kind, track, at, position_index, transition, frames, edge, alignment, single_sided,
                   timeout, remove=False):
    """Add a transition at a clip edge, or with remove delete the one there."""
    if (at is None) == (position_index is None):
        raise ValueError("Give exactly one of at or position_index")
    if remove:
        reject_foreign("remove", {"transition": transition, "frames": frames, "alignment": alignment,
                                  "single_sided": single_sided or None}, set())
    else:
        transition = transition or "Cross Dissolve"
        frames, alignment = frames or 12, 0.5 if alignment is None else alignment
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "transition": transition and TRANSITIONS.get(transition, transition), "frames": frames, "edge": edge,
            "alignment": alignment, "single_sided": single_sided, "remove": remove}
    return invoke("transition_add", args, timeout)


def one_clip(at, position_index, name=None):
    if sum(value is not None for value in (at, position_index, name)) != 1:
        raise ValueError("Give exactly one of at, position_index or name")


def clip_edit(sequence, kind, track, at, position_index, name, edit, timeout):
    """Trim, move, enable, rename, link, unlink or remove one placed clip."""
    one_clip(at, position_index, name)
    if edit.get("keep_linked") and not edit.get("remove"):
        raise ValueError("keep_linked needs remove")
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
    for state in states:
        if state.get("volume_db") is not None and state["kind"] != "audio":
            raise ValueError("volume_db is for audio tracks: give kind=audio")
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
    if prefix in ("", ".", "..") or Path(prefix).name != prefix:
        raise ValueError(f"prefix is a file name start, not a path: {prefix}")
    folder.mkdir(parents=True, exist_ok=True)
    paths = [str(folder / f"{prefix}_{i + 1:03d}_{seconds:.3f}s") for i, seconds in enumerate(times)]
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


def effect_set(sequence, kind, track, at, position_index, component, component_index, list_, params, timeout,
               remove=False):
    """Set or list the parameters of a clip's component, by display names, or remove the component."""
    one_clip(at, position_index)
    if remove:
        if list_ or params:
            raise ValueError("remove takes no params or list")
        if not component:
            raise ValueError("Give the component to remove")
    elif bool(list_) == bool(params):
        raise ValueError("Give params to set or list=true, not both")
    if params and not component:
        raise ValueError("Give the component the parameters belong to")
    for spec in params:
        if spec.get("keyframes"):
            if spec.get("value") is not None or spec.get("color"):
                raise ValueError(f"{spec['name']}: give either a value or keyframes")
        elif (spec.get("value") is None) == (spec.get("color") is None):
            raise ValueError(f"{spec['name']}: give exactly one of value or color")
    args = {"sequence": sequence, "kind": kind, "track": track, "at": at, "position_index": position_index,
            "component": component, "component_index": component_index, "list": list_, "params": params,
            "remove": remove}
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


def scene_times(media, threshold, timeout=3600, start=None, end=None):
    """Source times of hard cuts in a movie, from ffmpeg's scene score; only start to end when given."""
    window = ([] if start is None else ["-ss", str(start), "-copyts"], [] if end is None else ["-to", str(end)])
    result = run_sync([ffmpeg_tool("ffmpeg"), "-hide_banner", *window[0], "-i", str(media), *window[1], "-an", "-vf",
                       f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], timeout)
    if result.returncode:
        raise RuntimeError(f"ffmpeg could not read {media}: " + diagnostics(result))
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def silence_ranges(media, noise_db, min_seconds, timeout, start, end):
    """Source ranges of silence in a file's first audio stream from ffmpeg silencedetect, start to end only; a
    silence still open at end ends there."""
    result = run_sync([ffmpeg_tool("ffmpeg"), "-hide_banner", "-ss", str(start), "-copyts", "-i", str(media),
                       "-to", str(end), "-vn", "-map", "0:a:0", "-af",
                       f"silencedetect=noise={noise_db}dB:d={min_seconds}", "-f", "null", "-"], timeout)
    if result.returncode:
        raise RuntimeError(f"ffmpeg could not read the audio of {media}: " + diagnostics(result))
    starts = [float(m) for m in re.findall(r"silence_start: (-?[0-9.]+)", result.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: (-?[0-9.]+)", result.stderr)]
    return [(max(a, start), min(b, end)) for a, b in zip(starts, ends + [end] * (len(starts) - len(ends)))]


WHISPER_MODELS = ("tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large",
                  "large-v1", "large-v2", "large-v3", "large-v3-turbo", "turbo")


def speech_tool(model):
    """The whisper command for a model name, or the mlx-audio command for a model folder."""
    command = "mlx_audio.stt.generate" if isinstance(model, Path) else "whisper"
    found = shutil.which(command, path=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    if not found:
        raise ValueError("Install mlx-audio to transcribe with a local model folder" if isinstance(model, Path)
                         else "Install whisper (openai-whisper) to transcribe")
    return found


def speech_model(model):
    """A model name from CAVI_WHISPER_MODEL or base, or an existing local model folder as a Path."""
    model = model or os.environ.get("CAVI_WHISPER_MODEL") or "base"
    if model.startswith(("/", "~")):
        folder = absolute(model)
        if not folder.is_dir():
            raise FileNotFoundError(f"No model folder at {folder}")
        return folder
    if model not in WHISPER_MODELS:
        raise ValueError(f"Unknown whisper model {model}; use one of {', '.join(WHISPER_MODELS)} or an absolute "
                         "path to a model folder")
    return model


def transcribe(media, start, end, model, language, timeout):
    """Whisper's JSON for the first audio stream of a file from start to end; times in it count from start.
    model is a name for the whisper command or a Path of a model folder for mlx-audio."""
    tool = speech_tool(model)
    with tempfile.TemporaryDirectory() as folder:
        wav = Path(folder) / "audio.wav"
        cut = run_sync([ffmpeg_tool("ffmpeg"), "-hide_banner", "-ss", str(start), "-i", str(media), "-t",
                        str(end - start), "-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav)], timeout)
        if cut.returncode or not wav.is_file():
            raise RuntimeError(f"ffmpeg could not read the audio of {media}: " + diagnostics(cut))
        env = {**os.environ, "PATH": os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin"}
        if isinstance(model, Path):
            out = Path(folder) / "t.json"
            command = [tool, "--model", str(model), "--audio", str(wav), "--output-path", str(out.with_suffix("")),
                       "--format", "json", "--gen-kwargs", '{"word_timestamps": true}']
            # Homebrew numpy's OpenBLAS and torch each load libomp, and mlx-audio aborts at import without this.
            env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        else:
            out = Path(folder) / "audio.json"
            command = [tool, str(wav), "--model", model, "--word_timestamps", "True", "--output_format", "json",
                       "--output_dir", folder, "--fp16", "False"]
        if language:
            command += ["--language", language]
        result = run_sync(command, timeout, env=env)
        if result.returncode or not out.is_file():
            raise RuntimeError("Transcription failed: " + diagnostics(result))
        return json.loads(out.read_text(encoding="utf-8"))


def video_clip(listed, sequence, track, at, position_index, kind="video"):
    """The clip of a video (or audio) track at a time or position in the first of the inspected sequences, or a
    ValueError."""
    if not listed:
        raise ValueError(f"No sequence named {sequence}" if sequence else "The project has no sequence")
    if sequence is None and len(listed) > 1:
        raise ValueError("Give the sequence by name or id")
    lanes = single_sequence(listed, sequence)[kind]
    if track >= len(lanes):
        raise ValueError(f"No {kind} track {track} (the sequence has {len(lanes)})")
    clips = lanes[track]["clips"]
    if position_index is not None:
        if position_index >= len(clips):
            raise ValueError(f"No clip at position {position_index} on {kind} track {track} ({len(clips)} clips)")
        clip = clips[position_index]
    else:
        clip = next((c for c in clips if c["start"] - 0.0005 <= at < c["end"] - 0.0005), None)
    if clip is None or not clip["media_path"]:
        raise ValueError("No clip with media at that place")
    return clip


def scene_detect(sequence, track, at, position_index, threshold, apply, include_audio, timeout):
    """Cut times inside a placed clip, as timeline seconds; optionally razor or mark them."""
    one_clip(at, position_index)
    if include_audio and apply != "cuts":
        raise ValueError("include_audio needs apply=cuts")
    with exclusive(timeout):
        clip = video_clip(inspect(sequence, timeout, items=False)["sequences"], sequence, track, at, position_index)
        first, last, ratio = clip["in_point"], clip["out_point"], clip["speed"] / 100
        # Source times map through the speed, from the out point when the clip plays backwards.
        times = sorted(round(clip["start"] + ((last - t) if clip["reversed"] else (t - first)) / ratio, 3)
                       for t in scene_times(clip["media_path"], threshold, timeout, first, last) if first < t < last)
        result = {"clip": clip["name"], "cuts": times, "applied": apply}
        if times and apply == "cuts":
            host_razor = razor(sequence, times, "all" if include_audio else "video",
                               None if include_audio else track, timeout)
            result["clips_after"] = host_razor["clips_after"]
        elif times and apply == "markers":
            result["markers"] = markers_add(sequence, [{"time": t, "name": "cut", "comment": "", "duration": 0}
                                                        for t in times], None, timeout)["total"]
        return result


def media_replace(item, path, timeout):
    """Relink a project item to a new file, then confirm through inspect that the project points at it."""
    target = existing(path)
    with exclusive(timeout):
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
    if (beats := math.ceil((end - start) * bpm / 60)) > MAX_MARKERS:
        raise ValueError(f"beat_grid would add {beats} markers; the limit is {MAX_MARKERS}")
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
    if len(found) > MAX_MARKERS:
        raise ValueError(f"{len(found)} markers in one call; the limit is {MAX_MARKERS}")
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


def launch_encoder(timeout):
    """Start Media Encoder when it is not running and wait until it answers scripts; a job queued before that
    is not accepted."""
    app = media_encoder()
    if not running(app):
        start(app)
        relay("'ready'", timeout, target="ame")


def render(tool, sequence, master, preset, range_, replace, timeout, burn_captions=None):
    """Run export.jsx or encode.jsx; judged by the report, the released file and ffprobe frames.

    Every input is checked before Premiere or Media Encoder is touched, and an existing master is deleted
    only once nothing is left that can refuse the call.
    """
    deadline = time.monotonic() + timeout
    if range_ not in ("entire", "in_out", "work_area"):
        raise ValueError(f"range is entire, in_out or work_area: {range_}")
    master = absolute(master)
    if master.exists() and not replace:
        raise ValueError(f"Already exists (pass replace=true): {master}")
    preset = Path(resolve_preset("export", preset) if preset else prores_preset())
    ffprobe()
    if tool == "encode":
        launch_encoder(timeout)
    with tempfile.TemporaryDirectory(prefix="premiere-render-") as folder:
        if burn_captions is not None:
            preset = caption_preset(preset, burn_captions, folder)
        master.parent.mkdir(parents=True, exist_ok=True)
        if master.exists():
            master.unlink()
        report, failure = Path(folder) / "report.json", Path(folder) / "failure.txt"
        args = {"sequence": sequence, "master": str(master), "preset": str(preset), "range": range_,
                "report": str(report), "failure": str(failure)}
        result = finish(tool_script(tool, args), report, master, left(deadline, 1), failure)
    frames = master_frames(master, result["fps"])
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


INTERCHANGE_USES = {"xml": {"sequence", "replace"}, "aaf": {"sequence", "replace", "audio_rate", "bits"},
                    "omf": {"sequence", "replace", "audio_rate", "bits"}, "import_xml": set()}


def interchange(sequence, action, path, replace, audio_rate, bits, timeout):
    """Export a sequence as FCP XML, AAF or OMF, or import an FCP XML; the file or the new sequence is checked.
    AAF and OMF audio is 48000 Hz and 16 bits unless audio_rate and bits are given."""
    reject_foreign(action, {"sequence": sequence, "replace": replace or None, "audio_rate": audio_rate,
                            "bits": bits}, INTERCHANGE_USES[action])
    audio_rate, bits = audio_rate or 48000, bits or 16
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


