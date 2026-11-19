// Place project items (or importable files) on the tracks of one sequence, in list order. Input:
// {sequence, clips: [{item, kind (video|audio), track, at, in_point, out_point, mode (overwrite|insert)}]}.
// Seconds. Every track and item is found, and files no item holds are imported, before the first placement.
function place(lane, source, spec, frame) {
    var was = {in_point: secs(source.getInPoint()), out_point: secs(source.getOutPoint())}, placed = null,
        nearest = frame / 2 + 0.001;
    if (given(spec.in_point)) {
        source.setInPoint(spec.in_point, 4);
    }
    if (given(spec.out_point)) {
        source.setOutPoint(spec.out_point, 4);
    }
    try {
        if (spec.mode === "insert") {
            lane.insertClip(source, spec.at);
        } else {
            lane.overwriteClip(source, spec.at);
        }
    } finally {
        // The in and out points were only for this placement.
        source.setInPoint(was.in_point, 4);
        source.setOutPoint(was.out_point, 4);
    }
    // Premiere moves the start to the nearest frame.
    each(lane.clips, function (clip, i) {
        var off = Math.abs(secs(clip.start) - spec.at);
        if (off < nearest) {
            nearest = off;
            placed = clipInfo(clip, i);
        }
    });
    if (!placed) {
        fail("The clip is not on " + spec.kind + " track " + spec.track + " at " + spec.at + " s");
    }
    return placed;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), lanes = [], sources = [], missing = [], seen = {}, index = itemIndex(),
        i, spec;
    for (i = 0; i < A.clips.length; i++) {
        spec = A.clips[i];
        lanes.push(track(sequence, spec.kind, spec.track));
        if (!itemsFor(spec.item, index).length && new File(spec.item).exists && !entriesOf(seen, spec.item)) {
            addTo(seen, spec.item, true);
            missing.push(spec.item);
        }
    }
    if (missing.length) {
        app.project.importFiles(missing, true, app.project.rootItem, false);
        index = itemIndex();
    }
    for (i = 0; i < A.clips.length; i++) {
        sources.push(findItem(A.clips[i].item, index));
    }
    report.sequence = sequence.name;
    report.clips = [];
    for (i = 0; i < A.clips.length; i++) {
        report.clips.push(place(lanes[i], sources[i], A.clips[i], 1 / frameRate(sequence)));
    }
}
