// Find or close empty gaps. Input: {sequence, action (list|close), min_seconds, leading}. A gap is a time
// range with no clip on any unlocked track. close moves each later clip of every unlocked track left once,
// by the length of the gaps before it, so audio and video stay in sync. leading includes the empty space
// before the first clip.
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

// Each clip of a lane is moved once, in timeline order, by the gaps that end at or before its start; a
// clip never moves past room the clip before it left.
function closeAll(sequence, gaps) {
    var all = lanes(sequence), moved = 0, i;
    for (i = 0; i < all.length; i++) {
        if (all[i].lane.isLocked()) {
            continue;
        }
        (function (lane) {
            var next = 0, shift = 0;
            each(lane.clips, function (clip) {
                var start = secs(clip.start);
                while (next < gaps.length && gaps[next].end <= start + 0.0005) {
                    shift += gaps[next].end - gaps[next].start;
                    next += 1;
                }
                if (shift > 0) {
                    clip.move(timeAt(-shift));
                    moved += 1;
                }
            });
        })(all[i].lane);
    }
    return moved;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), gaps = findGaps(sequence, A.min_seconds || 0, A.leading);
    report.sequence = sequence.name;
    report.gaps = gaps;
    if (A.action === "list") {
        return;
    }
    report.moved = gaps.length ? closeAll(sequence, gaps) : 0;
    report.closed = gaps.length;
    report.remaining = findGaps(sequence, A.min_seconds || 0, A.leading).length;
}
