// Premiere's scene edit detection on one video clip, in two jobs because the detection acts on the selection
// and CreateMarkers finishes after the job that started it returns. Input: {sequence, track, at |
// position_index, action (ApplyCuts | CreateMarkers), mode}.
// run: select only the clip, start the detection and leave the clip selected; reports the clip's range, the
// source markers it had and the ids of the clips selected before.
// finish: report the cuts found (split points for ApplyCuts, new source markers as timeline seconds for
// CreateMarkers), and put the earlier selection back when A.restore is true.
// ApplyCuts splits the clip; CreateMarkers adds markers to the clip's project item at source times.
function sourceMarkers(item) {
    var list = [], markers = item.getMarkers(), marker;
    for (marker = markers ? markers.getFirstMarker() : null; marker; marker = markers.getNextMarker(marker)) {
        list.push(secs(marker.start));
    }
    return list;
}

function has(list, value) {
    var i;
    for (i = 0; i < list.length; i++) {
        if (Math.abs(list[i] - value) < 0.0005) {
            return true;
        }
    }
    return false;
}

function startDetection(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, "video", A.track, A.at, A.position_index),
        only = {}, before;
    only[clip.nodeId] = true;
    report.clip = clip.name;
    report.start = secs(clip.start);
    report.end = secs(clip.end);
    report.first = sourceIn(clip);
    report.last = sourceOut(clip);
    report.ratio = speedOf(clip);
    report.reversed = reversedOf(clip);
    report.markers_before = sourceMarkers(clip.projectItem);
    before = setSelection(sequence, only);
    report.selection = [];
    for (var id in before) {
        if (before.hasOwnProperty(id)) {
            report.selection.push(id);
        }
    }
    if (!sequence.performSceneEditDetectionOnSelection(A.action)) {
        setSelection(sequence, before);
        fail("Premiere did not run scene edit detection on " + clip.name);
    }
}

function finishDetection(A, report) {
    var sequence = findSequence(A.sequence), lane = track(sequence, "video", A.track), cuts = [], total = 0, back = {},
        i, found, low, high;
    report.clip = A.clip.name;
    if (A.action === "ApplyCuts") {
        each(lane.clips, function (candidate) {
            if (secs(candidate.start) >= A.clip.start - 0.0005 && secs(candidate.end) <= A.clip.end + 0.0005) {
                total++;
                if (secs(candidate.start) > A.clip.start + 0.0005) {
                    cuts.push(Math.round(secs(candidate.start) * 1000) / 1000);
                }
            }
        });
        report.clips_after = total;
    } else {
        found = sourceMarkers(findClip(sequence, "video", A.track, A.clip.start, null).projectItem);
        low = Math.min(A.clip.first, A.clip.last);
        high = Math.max(A.clip.first, A.clip.last);
        for (i = 0; i < found.length; i++) {
            if (!has(A.clip.markers_before, found[i]) && found[i] > low && found[i] < high) {
                cuts.push(Math.round((A.clip.start + (A.clip.reversed ? A.clip.last - found[i]
                    : found[i] - A.clip.first) / A.clip.ratio) * 1000) / 1000);
            }
        }
        report.markers = cuts.length;
    }
    cuts.sort(function (a, b) {
        return a - b;
    });
    report.cuts = cuts;
    if (A.restore) {
        for (i = 0; i < A.clip.selection.length; i++) {
            back[A.clip.selection[i]] = true;
        }
        setSelection(sequence, back);
    }
}

function run(A, report) {
    if (A.mode === "run") {
        startDetection(A, report);
    } else {
        finishDetection(A, report);
    }
}
