// Cut a time range out of the timeline. Input: {sequence, start, end, mode (lift|extract)}. The QE razor
// splits clips at both times on every track; the clips inside are removed. extract also moves every later
// clip of every unlocked track left by the range length. Locked tracks are left untouched. Seconds.
function run(A, report) {
    var sequence = findSequence(A.sequence), fps = frameRate(sequence), q, i, j, lane, lanesList = [],
        doomed = [], later = [], removed = 0, moved = 0, length = A.end - A.start, t;
    A.start = Math.round(A.start * fps) / fps;
    A.end = Math.round(A.end * fps) / fps;
    length = A.end - A.start;
    if (length <= 0) {
        fail("The range is shorter than one frame");
    }
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
    if (A.end > endSeconds(sequence) + 0.0005 || A.start >= endSeconds(sequence)) {
        fail("The range " + A.start + "-" + A.end + " s is past the end of the sequence (" + endSeconds(sequence) + " s)");
    }
    for (i = 0; i < lanesList.length; i++) {
        lanesList[i].q.razor(tcOf(A.start, fps));
        lanesList[i].q.razor(tcOf(A.end, fps));
    }
    for (i = 0; i < lanesList.length; i++) {
        lane = lanesList[i];
        each(lane.lane.clips, function (clip) {
            if (secs(clip.start) >= A.start - 0.0005 && secs(clip.end) <= A.end + 0.0005) {
                doomed.push({kind: lane.kind, index: lane.index, id: clip.nodeId, label: lane.kind + " " + lane.index});
            } else if (A.mode === "extract" && secs(clip.start) >= A.end - 0.0005) {
                later.push({kind: lane.kind, index: lane.index, id: clip.nodeId});
            }
        });
    }
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
    // Track objects go stale once a clip is removed, so tracks are fetched again each time.
    // later was collected in ascending order per track, so each move leaves room for the next.
    for (j = 0; j < later.length; j++) {
        each(track(sequence, later[j].kind, later[j].index).clips, function (clip) {
            if (clip && clip.nodeId === later[j].id) {
                t = new Time();
                t.ticks = String(Math.round(-length * TICKS));
                clip.move(t);
                moved += 1;
            }
        });
    }
    report.sequence = sequence.name;
    report.mode = A.mode;
    report.start = A.start;
    report.end = A.end;
    report.removed = removed;
    report.moved = moved;
    report.sequence_end = endSeconds(sequence);
}
