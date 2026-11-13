// Add tracks and set their mute, lock and target state. Input: {sequence, add_video, add_audio, tracks:
// [{kind, track, muted, locked, targeted}]}. New tracks go after the last one.
function counts(sequence) {
    return {video: sequence.videoTracks.numTracks, audio: sequence.audioTracks.numTracks};
}

function state(sequence) {
    var info = {video: [], audio: []};

    function lane(kind, item, index) {
        info[kind].push({index: index, name: item.name, muted: !!item.isMuted(), locked: !!item.isLocked(),
            targeted: !!item.isTargeted(), clips: count(item.clips)});
    }

    each(sequence.videoTracks, function (item, index) {
        lane("video", item, index);
    });
    each(sequence.audioTracks, function (item, index) {
        lane("audio", item, index);
    });
    return info;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), before = counts(sequence), q, i, spec, lane;
    if (A.add_video || A.add_audio) {
        app.enableQE();
        q = qe.project.getActiveSequence();
        q.addTracks(A.add_video || 0, before.video - 1, A.add_audio || 0, before.audio - 1, 1);
        sequence = findSequence(A.sequence);
    }
    for (i = 0; i < (A.tracks || []).length; i++) {
        spec = A.tracks[i];
        lane = track(sequence, spec.kind, spec.track);
        if (given(spec.muted)) {
            lane.setMute(spec.muted ? 1 : 0);
        }
        if (given(spec.locked)) {
            lane.setLocked(spec.locked ? 1 : 0);
        }
        if (given(spec.targeted)) {
            lane.setTargeted(!!spec.targeted, true);
        }
    }
    report.sequence = sequence.name;
    report.before = before;
    report.after = counts(sequence);
    report.tracks = state(sequence);
}
