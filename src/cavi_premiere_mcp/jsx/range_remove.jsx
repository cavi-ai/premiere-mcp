// Cut time ranges out of the timeline. Input: {sequence, ranges: [{start, end}], mode (lift|extract)}: the
// ranges in timeline order without overlaps, in seconds before anything is removed. The QE razor splits
// clips at every range edge on every unlocked track; the clips inside a range are removed. extract also
// moves each later clip of every unlocked track left once, by the length removed before it. Locked tracks
// are left untouched.
function run(A, report) {
    var sequence = findSequence(A.sequence), q, i, j, lanesList = [], ranges = [], doomed = [], shifts = {},
        removed = 0, moved = 0, start, stop, last;
    for (i = 0; i < A.ranges.length; i++) {
        start = snap(A.ranges[i].start, sequence);
        stop = snap(A.ranges[i].end, sequence);
        if (stop - start <= 0) {
            fail("The range " + A.ranges[i].start + "-" + A.ranges[i].end + " s is shorter than one frame");
        }
        if (ranges.length && start < ranges[ranges.length - 1].end - 0.0005) {
            fail("The ranges " + ranges[ranges.length - 1].start + "-" + ranges[ranges.length - 1].end + " s and "
                 + start + "-" + stop + " s overlap on the frame grid");
        }
        ranges.push({start: start, end: stop});
    }
    last = ranges[ranges.length - 1];
    app.enableQE();
    q = qe.project.getActiveSequence();

    function collect(kind, list) {
        each(list, function (lane, index) {
            if (lane.isLocked()) {
                return;
            }
            lanesList.push({kind: kind, index: index, lane: lane,
                            q: kind === "audio" ? q.getAudioTrackAt(index) : q.getVideoTrackAt(index)});
        });
    }

    collect("video", sequence.videoTracks);
    collect("audio", sequence.audioTracks);
    if (last.end > endSeconds(sequence) + 0.0005 || last.start >= endSeconds(sequence)) {
        fail("The range " + last.start + "-" + last.end + " s is past the end of the sequence ("
             + endSeconds(sequence) + " s)");
    }
    for (i = 0; i < lanesList.length; i++) {
        for (j = 0; j < ranges.length; j++) {
            lanesList[i].q.razor(tcOf(ranges[j].start, sequence));
            lanesList[i].q.razor(tcOf(ranges[j].end, sequence));
        }
    }
    // Clips come in timeline order, so one walk over the ranges finds the range a clip is inside and the
    // length removed before it.
    for (i = 0; i < lanesList.length; i++) {
        (function (lane) {
            var next = 0, by = 0;
            each(lane.lane.clips, function (clip) {
                var at = secs(clip.start);
                while (next < ranges.length && ranges[next].end <= at + 0.0005) {
                    by += ranges[next].end - ranges[next].start;
                    next += 1;
                }
                if (next < ranges.length && at >= ranges[next].start - 0.0005
                        && secs(clip.end) <= ranges[next].end + 0.0005) {
                    doomed.push({kind: lane.kind, index: lane.index, id: clip.nodeId, label: lane.kind + " " + lane.index});
                } else if (A.mode === "extract" && by > 0) {
                    shifts[lane.kind + lane.index + "/" + clip.nodeId] = by;
                }
            });
        })(lanesList[i]);
    }
    // Track objects go stale once a clip is removed, so tracks are fetched again each time.
    for (i = 0; i < doomed.length; i++) {
        each(track(sequence, doomed[i].kind, doomed[i].index).clips, function (clip) {
            if (clip && clip.nodeId === doomed[i].id) {
                try {
                    clip.remove(false, false);
                    removed += 1;
                } catch (failure) {
                    report.warnings.push("Could not remove " + clip.name + " on track " + doomed[i].label + ": "
                                         + String(failure.message || failure));
                }
            }
        });
    }
    // Each lane is moved in timeline order, so each clip moves into room the one before it left.
    for (i = 0; i < lanesList.length; i++) {
        (function (lane) {
            each(track(sequence, lane.kind, lane.index).clips, function (clip) {
                var by = clip ? shifts[lane.kind + lane.index + "/" + clip.nodeId] : 0;
                if (by) {
                    clip.move(timeAt(-by));
                    moved += 1;
                }
            });
        })(lanesList[i]);
    }
    report.sequence = sequence.name;
    report.mode = A.mode;
    report.start = ranges[0].start;
    report.end = last.end;
    report.ranges = ranges;
    report.removed = removed;
    report.moved = moved;
    report.sequence_end = endSeconds(sequence);
}
