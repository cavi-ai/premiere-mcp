// Queue a sequence in Adobe Media Encoder and start the batch. Input: {sequence, master, preset,
// range (entire|in_out|work_area)}. The script returns once the job is queued; the file is judged by
// the caller.
function run(A, report) {
    var sequence = findSequence(A.sequence),
        modes = {entire: app.encoder.ENCODE_ENTIRE, in_out: app.encoder.ENCODE_IN_TO_OUT,
            work_area: app.encoder.ENCODE_WORKAREA};
    report.sequence = sequence.name;
    report.fps = TICKS / Number(sequence.timebase);
    report.sequence_end = endSeconds(sequence);
    report.span = rangeSpan(sequence, A.range);
    app.project.save();
    app.encoder.launchEncoder();
    report.job = String(app.encoder.encodeSequence(sequence, A.master, A.preset, modes[A.range], 1));
    app.encoder.startBatch();
}
