// Create a sequence with the settings of a project item or of a .sqpreset file.
// Input: {name, clip, preset, bin}; clip is a media path or item name, preset an absolute path.
function emptyTracks(sequence) {
    var i;
    for (i = 0; i < sequence.videoTracks.numTracks; i++) {
        while (sequence.videoTracks[i].clips.numItems > 0) {
            sequence.videoTracks[i].clips[0].remove(false, false);
        }
    }
    for (i = 0; i < sequence.audioTracks.numTracks; i++) {
        while (sequence.audioTracks[i].clips.numItems > 0) {
            sequence.audioTracks[i].clips[0].remove(false, false);
        }
    }
}

function run(A, report) {
    var bin = findBin(A.bin, true), made = null;
    if (A.clip) {
        made = app.project.createNewSequenceFromClips(A.name, [findItem(A.clip)], bin);
        // The clip the sequence was made from is removed; the settings stay.
        emptyTracks(made);
    } else {
        app.enableQE();
        qe.project.newSequence(A.name, A.preset);
        each(app.project.sequences, function (candidate) {
            if (candidate.name === A.name) {
                made = candidate;
            }
        });
    }
    if (!made) {
        fail("Premiere did not create sequence " + A.name);
    }
    report.name = made.name;
    report.id = made.sequenceID;
    report.fps = TICKS / Number(made.timebase);
    report.width = made.frameSizeHorizontal;
    report.height = made.frameSizeVertical;
    report.video_tracks = made.videoTracks.numTracks;
    report.audio_tracks = made.audioTracks.numTracks;
}
