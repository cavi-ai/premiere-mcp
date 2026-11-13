// Split clips with the QE razor at one or more times. Input: {sequence, times, kind (video|audio|all),
// track}. Every track of the kind is cut when track is null. Seconds, snapped to the frame grid.
function run(A, report) {
    var sequence = findSequence(A.sequence), fps = frameRate(sequence), lanes = [], i, j,
        before = 0, after = 0;
    app.enableQE();
    var q = qe.project.getActiveSequence();

    function add(kind, count) {
        for (var n = 0; n < count; n++) {
            if (A.track === null || A.track === undefined || A.track === n) {
                lanes.push(kind === "audio" ? q.getAudioTrackAt(n) : q.getVideoTrackAt(n));
            }
        }
    }

    function clips() {
        var total = 0;
        each(sequence.videoTracks, function (lane) { total += count(lane.clips); });
        each(sequence.audioTracks, function (lane) { total += count(lane.clips); });
        return total;
    }

    if (A.kind !== "audio") {
        add("video", sequence.videoTracks.numTracks);
    }
    if (A.kind !== "video") {
        add("audio", sequence.audioTracks.numTracks);
    }
    before = clips();
    for (i = 0; i < A.times.length; i++) {
        for (j = 0; j < lanes.length; j++) {
            lanes[j].razor(tcOf(A.times[i], fps));
        }
    }
    after = clips();
    report.sequence = sequence.name;
    report.cuts = A.times.length;
    report.clips_before = before;
    report.clips_after = after;
}
