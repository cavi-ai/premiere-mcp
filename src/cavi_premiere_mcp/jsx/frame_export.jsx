// Export PNG stills of a sequence through QE exportFramePNG. Input: {sequence, times, paths}: one
// absolute path without extension per time (QE appends .png). Seconds.
function run(A, report) {
    var sequence = findSequence(A.sequence), fps = frameRate(sequence), end = endSeconds(sequence), i, q;
    app.enableQE();
    q = qe.project.getActiveSequence();
    report.sequence = sequence.name;
    report.frames = [];
    for (i = 0; i < A.times.length; i++) {
        if (A.times[i] >= end) {
            fail("Time " + A.times[i] + " s is past the end of the sequence (" + end + " s)");
        }
        if (!q.exportFramePNG(tcOf(A.times[i], fps), A.paths[i])) {
            fail("Premiere did not export the frame at " + A.times[i] + " s");
        }
        report.frames.push({time: A.times[i], path: A.paths[i] + ".png", exists: new File(A.paths[i] + ".png").exists});
    }
}
