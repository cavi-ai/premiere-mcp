// Queue a sequence in Adobe Media Encoder and start the batch. Input: {sequence, master, preset,
// range (entire|in_out|work_area), failure}. The script returns once the job is queued; the file is judged
// by the caller. Premiere's onEncoderJobError for this job, which comes after the script has returned,
// writes Media Encoder's message to failure.
function run(A, report) {
    var sequence = findSequence(A.sequence), job = null,
        modes = {entire: app.encoder.ENCODE_ENTIRE, in_out: app.encoder.ENCODE_IN_TO_OUT,
            work_area: app.encoder.ENCODE_WORKAREA};
    report.sequence = sequence.name;
    report.fps = TICKS / Number(sequence.timebase);
    report.sequence_end = endSeconds(sequence);
    report.span = rangeSpan(sequence, A.range);
    app.project.save();
    app.encoder.launchEncoder();
    app.encoder.bind("onEncoderJobError", function (id, message) {
        var file;
        if (String(id) === job && A.failure) {
            file = new File(A.failure);
            file.encoding = "UTF-8";
            file.open("w");
            file.write(String(message));
            file.close();
        }
    });
    job = String(app.encoder.encodeSequence(sequence, A.master, A.preset, modes[A.range], 1));
    report.job = job;
    app.encoder.startBatch();
}
