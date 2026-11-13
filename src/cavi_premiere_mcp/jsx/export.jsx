// Export a sequence through exportAsMediaDirect with a preset. Input: {sequence, master, preset,
// work_area (entire|in_out)}. The call blocks until Premiere has written the file.
function run(A, report) {
    var sequence = findSequence(A.sequence);
    report.sequence = sequence.name;
    report.fps = TICKS / Number(sequence.timebase);
    report.sequence_end = endSeconds(sequence);
    app.project.save();
    report.exported = sequence.exportAsMediaDirect(A.master, A.preset,
        A.work_area === "in_out" ? app.encoder.ENCODE_IN_TO_OUT : app.encoder.ENCODE_ENTIRE);
}
