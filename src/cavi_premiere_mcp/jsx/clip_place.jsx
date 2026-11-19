// Place project items (or importable files) on the tracks of one sequence, in list order. Input:
// {sequence, clips: [{item, kind (video|audio), track, at, in_point, out_point, mode (overwrite|insert),
// speed, reversed}]}. Seconds; speed in percent. Every track and item is found, and files no item holds are
// imported, before the first placement.
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
        report.clips.push(place(sequence, lanes[i], sources[i], A.clips[i]));
    }
}
