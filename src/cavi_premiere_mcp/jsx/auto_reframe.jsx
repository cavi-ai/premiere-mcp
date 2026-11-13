// Make a new sequence at another aspect ratio with Auto Reframe. Input: {sequence, numerator,
// denominator, motion (slower|default|faster), name, nest}.
function run(A, report) {
    var sequence = findSequence(A.sequence), made = sequence.autoReframeSequence(A.numerator, A.denominator,
        A.motion, A.name, A.nest);
    if (!made) {
        fail("Premiere did not create the reframed sequence");
    }
    report.source = sequence.name;
    report.sequence = {name: made.name, id: made.sequenceID, width: made.frameSizeHorizontal,
        height: made.frameSizeVertical, fps: TICKS / Number(made.timebase), end: endSeconds(made),
        video_tracks: made.videoTracks.numTracks, audio_tracks: made.audioTracks.numTracks};
}
