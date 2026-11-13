// Find or close empty gaps. Input: {sequence, action (list|close), min_seconds, leading}. A gap is a time
// range with no clip on any unlocked track. close moves every later clip of every unlocked track left,
// last gap first, so audio and video stay in sync. leading includes the empty space before the first clip.
function lanes(sequence) {
    var found = [];
    each(sequence.videoTracks, function (lane, i) {
        found.push({kind: "video", index: i, lane: lane});
    });
    each(sequence.audioTracks, function (lane, i) {
        found.push({kind: "audio", index: i, lane: lane});
    });
    return found;
}

function occupied(sequence) {
    var spans = [], all = lanes(sequence), i;
    for (i = 0; i < all.length; i++) {
        if (all[i].lane.isLocked()) {
            continue;
        }
        each(all[i].lane.clips, function (clip) {
            spans.push([secs(clip.start), secs(clip.end)]);
        });
    }
    spans.sort(function (a, b) { return a[0] - b[0]; });
    return spans;
}

function findGaps(sequence, min, leading) {
    var spans = occupied(sequence), gaps = [], edge = leading ? 0 : null, i;
    if (!spans.length) {
        return gaps;
    }
    if (edge === null) {
        edge = spans[0][0];
    }
    for (i = 0; i < spans.length; i++) {
        if (spans[i][0] - edge > Math.max(min, 0.0005)) {
            gaps.push({start: edge, end: spans[i][0]});
        }
        edge = Math.max(edge, spans[i][1]);
    }
    return gaps;
}

function shiftLeft(sequence, from, by) {
    var all = lanes(sequence), moved = 0, i, t, ids = [];
    for (i = 0; i < all.length; i++) {
        if (all[i].lane.isLocked()) {
            continue;
        }
        each(all[i].lane.clips, function (clip) {
            if (secs(clip.start) >= from - 0.0005) {
                ids.push({lane: all[i].lane, id: clip.nodeId});
            }
        });
    }
    for (i = 0; i < ids.length; i++) {
        each(ids[i].lane.clips, function (clip) {
            if (clip.nodeId === ids[i].id) {
                t = new Time();
                t.ticks = String(Math.round(-by * TICKS));
                clip.move(t);
                moved += 1;
            }
        });
    }
    return moved;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), gaps = findGaps(sequence, A.min_seconds || 0, A.leading), i;
    report.sequence = sequence.name;
    report.gaps = gaps;
    if (A.action === "list") {
        return;
    }
    report.closed = 0;
    report.moved = 0;
    for (i = gaps.length - 1; i >= 0; i--) {
        report.moved += shiftLeft(sequence, gaps[i].end, gaps[i].end - gaps[i].start);
        report.closed += 1;
    }
    report.remaining = findGaps(sequence, A.min_seconds || 0, A.leading).length;
}
