// Export a sequence through exportAsMediaDirect with a preset. Input: {sequence, master, preset,
// range (entire|in_out|work_area)}. The call blocks until Premiere has written the file.
function run(A, report) {
    var sequence = findSequence(A.sequence),
        modes = {entire: app.encoder.ENCODE_ENTIRE, in_out: app.encoder.ENCODE_IN_TO_OUT,
            work_area: app.encoder.ENCODE_WORKAREA};
    report.sequence = sequence.name;
    report.fps = TICKS / Number(sequence.timebase);
    report.sequence_end = endSeconds(sequence);
    report.span = rangeSpan(sequence, A.range);
    app.project.save();
    report.exported = sequence.exportAsMediaDirect(A.master, A.preset, modes[A.range]);
}
