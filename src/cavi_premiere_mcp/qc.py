"""Delivery checks: loudness of a master and synthetic project items."""

import asyncio
import json
import re
from typing import Annotated, Literal

from cavi_mcp_core.contracts import Result
from cavi_mcp_core.proc import diagnostics, run_sync
from cavi_mcp_core.server import DESTRUCTIVE, WRITES
from pydantic import BaseModel, Field

from . import host
from .app import SequenceName, Timeout, mcp

# Integrated loudness in LUFS and maximum true peak in dBTP.
LOUDNESS_TARGETS = {"streaming": (-14.0, -1.0), "podcast": (-16.0, -1.0), "ebu_r128": (-23.0, -1.0),
                    "atsc_a85": (-24.0, -2.0)}
LoudnessTarget = Literal["streaming", "podcast", "ebu_r128", "atsc_a85"]


def measure(media, timeout):
    """Integrated loudness (LUFS), loudness range (LU) and true peak (dBTP) of a file's first audio stream
    from ffmpeg ebur128; None for a value ffmpeg reports as -inf."""
    result = run_sync([host.ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(media), "-vn", "-map",
                       "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"], timeout)
    if result.returncode:
        raise RuntimeError(f"ffmpeg could not read the audio of {media}: " + diagnostics(result))
    summary = result.stderr.rpartition("Summary:")[2]

    def value(label):
        found = re.search(rf"^\s*{label}:\s+(-?[0-9.]+|-inf)\b", summary, re.M)
        if not found:
            raise RuntimeError(f"ffmpeg ebur128 reported no {label} for {media}")
        return None if found[1] == "-inf" else float(found[1])

    return {"integrated_lufs": value("I"), "loudness_range_lu": value("LRA"), "true_peak_dbtp": value("Peak")}


def judge(measured, lufs, peak, tolerance):
    integrated, true_peak = measured["integrated_lufs"], measured["true_peak_dbtp"]
    return (integrated is not None and abs(integrated - lufs) <= tolerance
            and (true_peak is None or true_peak <= peak))


def normalize_copy(media, output, lufs, peak, replace, timeout):
    """A two-pass loudnorm copy of media at output with the video stream copied."""
    ffmpeg = host.ffmpeg_tool("ffmpeg")
    first = run_sync([ffmpeg, "-hide_banner", "-nostats", "-i", str(media), "-vn", "-map", "0:a:0", "-af",
                      f"loudnorm=I={lufs}:TP={peak}:LRA=11:print_format=json", "-f", "null", "-"], timeout)
    if first.returncode:
        raise RuntimeError(f"ffmpeg could not read the audio of {media}: " + diagnostics(first))
    found = json.loads(re.findall(r"\{[^{}]*\}", first.stderr)[-1])
    if "-inf" in (found["input_i"], found["input_tp"]):
        raise ValueError(f"{media} is silent and cannot be normalized")
    rate = run_sync([host.ffprobe(), "-v", "error", "-select_streams", "a:0", "-show_entries",
                     "stream=sample_rate", "-of", "csv=p=0", str(media)], 60).stdout.split()[0]
    filter_ = (f"loudnorm=I={lufs}:TP={peak}:LRA=11:measured_I={found['input_i']}:measured_TP={found['input_tp']}:"
               f"measured_LRA={found['input_lra']}:measured_thresh={found['input_thresh']}:"
               f"offset={found['target_offset']}:linear=true")
    second = run_sync([ffmpeg, "-hide_banner", "-nostats", "-y" if replace else "-n", "-i", str(media), "-map",
                       "0:v?", "-map", "0:a:0", "-c:v", "copy", "-af", filter_, "-ar", rate, str(output)], timeout)
    if second.returncode:
        raise RuntimeError(f"ffmpeg could not normalize {media}: " + diagnostics(second))


def loudness(file, target, target_lufs, max_true_peak, tolerance, normalize, replace, timeout):
    """The loudness of a file against a preset or explicit target; optionally a normalized copy, measured too."""
    if target and (target_lufs is not None or max_true_peak is not None):
        raise ValueError("Give target, or target_lufs and max_true_peak, not both")
    if target_lufs is None:
        lufs, peak = LOUDNESS_TARGETS[target or "streaming"]
    else:
        lufs, peak = target_lufs, -1.0 if max_true_peak is None else max_true_peak
    media = host.existing(file)
    output = host.absolute(normalize) if normalize else None
    if output:
        if output == media:
            raise ValueError("normalize must differ from file")
        if output.exists() and not replace:
            raise ValueError(f"Already exists (pass replace=true): {output}")
    measured = measure(media, timeout)
    result = {"file": str(media), **measured, "target_lufs": lufs, "max_true_peak": peak, "tolerance": tolerance,
              "passes": judge(measured, lufs, peak, tolerance)}
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        normalize_copy(media, output, lufs, peak, replace, timeout)
        copy = measure(output, timeout)
        result["normalized"] = {"file": str(output), **copy, "passes": judge(copy, lufs, peak, tolerance)}
    return result


class Normalized(BaseModel):
    file: str
    integrated_lufs: float | None
    loudness_range_lu: float | None
    true_peak_dbtp: float | None
    passes: bool


class Loudness(Result):
    file: str
    integrated_lufs: float | None
    loudness_range_lu: float | None
    true_peak_dbtp: float | None
    target_lufs: float
    max_true_peak: float
    tolerance: float
    passes: bool
    normalized: Normalized | None = None


@mcp.tool(annotations=DESTRUCTIVE)
async def premiere_loudness(
        file: Annotated[str, Field(description="Absolute path of the master or media to measure.")],
        target: Annotated[LoudnessTarget | None,
                          Field(description="Preset: streaming -14 LUFS / -1 dBTP, podcast -16 / -1, ebu_r128 "
                                            "-23 / -1, atsc_a85 -24 / -2. streaming when no target is "
                                            "given.")] = None,
        target_lufs: Annotated[float | None, Field(ge=-70, le=-5, description="Explicit integrated loudness "
                                                                               "target, in LUFS.")] = None,
        max_true_peak: Annotated[float | None, Field(ge=-9, le=0, description="Explicit true peak ceiling in "
                                                                              "dBTP; -1 with target_lufs.")] = None,
        tolerance: Annotated[float, Field(ge=0, le=12, description="Allowed distance from the target, in "
                                                                   "LU.")] = 1,
        normalize: Annotated[str | None, Field(description="Absolute path of a normalized copy to write, with "
                                                           "the video copied.")] = None,
        replace: Annotated[bool, Field(description="Overwrite an existing normalize file.")] = False,
        timeout: Timeout = 600) -> Loudness:
    """Measure integrated loudness, loudness range and true peak of a file's first audio stream (ffmpeg
    ebur128) against a target. normalize also writes a two-pass loudnorm copy and measures it; read-only
    otherwise."""
    return await asyncio.to_thread(loudness, file, target, target_lufs, max_true_peak, tolerance, normalize, replace,
                                   timeout)


def item_new(kind, name, bin_, width, height, fps, sequence, timeout):
    """A synthetic project item sized like the sequence unless a size and rate are given."""
    return host.invoke("item_new", {"kind": kind, "name": name, "bin": bin_, "width": width, "height": height,
                                    "fps": fps, "sequence": sequence}, timeout)


class NewItem(Result):
    name: str
    id: str
    kind: str
    bin: str | None = None


@mcp.tool(annotations=WRITES)
async def premiere_item_new(
        kind: Annotated[Literal["bars_and_tone", "black_video", "transparent_video"],
                        Field(description="The synthetic item to create.")],
        name: Annotated[str | None, Field(description="Name of the new item.")] = None,
        bin: Annotated[str | None, Field(description="Bin to move it into; created when missing.")] = None,
        width: Annotated[int | None, Field(ge=16, le=16384, description="Frame width; the sequence's when "
                                                                        "omitted.")] = None,
        height: Annotated[int | None, Field(ge=16, le=16384, description="Frame height; the sequence's when "
                                                                         "omitted.")] = None,
        fps: Annotated[float | None, Field(gt=0, le=240, description="Frame rate; the sequence's when "
                                                                    "omitted.")] = None,
        sequence: SequenceName = None, timeout: Timeout = 300) -> NewItem:
    """Create a project item through Premiere's QE project: bars and tone, black video or transparent video."""
    return await asyncio.to_thread(item_new, kind, name, bin, width, height, fps, sequence, timeout)
