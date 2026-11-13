// Place a project item (or an importable file) on a track at a time. Input: {sequence, item, kind
// (video|audio), track, at, in_point, out_point, mode (overwrite|insert)}. Seconds.
function run(A, report) {
    var sequence = findSequence(A.sequence), lane = track(sequence, A.kind, A.track), source, was, placed = null;
    try {
        source = findItem(A.item);
    } catch (error) {
        if (!new File(A.item).exists) {
            throw error;
        }
        app.project.importFiles([A.item], true, app.project.rootItem, false);
        source = findItem(A.item);
    }
    was = {in_point: secs(source.getInPoint()), out_point: secs(source.getOutPoint())};
    if (A.in_point !== null && A.in_point !== undefined) {
        source.setInPoint(A.in_point, 4);
    }
    if (A.out_point !== null && A.out_point !== undefined) {
        source.setOutPoint(A.out_point, 4);
    }
    try {
        if (A.mode === "insert") {
            lane.insertClip(source, A.at);
        } else {
            lane.overwriteClip(source, A.at);
        }
    } finally {
        // The in and out points were only for this placement.
        source.setInPoint(was.in_point, 4);
        source.setOutPoint(was.out_point, 4);
    }
    each(lane.clips, function (clip, i) {
        if (!placed && Math.abs(secs(clip.start) - A.at) < 0.001) {
            placed = {position: i, name: clip.name, start: secs(clip.start), end: secs(clip.end),
                in_point: secs(clip.inPoint), out_point: secs(clip.outPoint)};
        }
    });
    if (!placed) {
        fail("The clip is not on " + A.kind + " track " + A.track + " at " + A.at + " s");
    }
    report.sequence = sequence.name;
    report.clip = placed;
}
