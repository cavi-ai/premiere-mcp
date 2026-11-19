// Add tracks and set their mute, lock, target state and audio Volume. Input: {sequence, add_video, add_audio,
// tracks: [{kind, track, muted, locked, targeted, volume_db}]}. New tracks go after the last one.
function counts(sequence) {
    return {video: sequence.videoTracks.numTracks, audio: sequence.audioTracks.numTracks};
}

// The QE component of an audio track of the active sequence that holds its Volume and Mute parameters.
// Volume is linear gain: 1 is 0 dB, 2 is +6 dB, 0 is silence; Premiere shows it to two decimals.
function trackVolume(index) {
    var lane, i;
    app.enableQE();
    lane = qe.project.getActiveSequence().getAudioTrackAt(index);
    for (i = 0; i < lane.numComponents; i++) {
        if (("," + lane.getComponentAt(i).getParamList() + ",").indexOf(",Volume,") >= 0) {
            return lane.getComponentAt(i);
        }
    }
    fail("Audio track " + index + " has no Volume parameter");
}

function state(sequence) {
    var info = {video: [], audio: []};

    function lane(kind, item, index) {
        var entry = {index: index, name: item.name, muted: !!item.isMuted(), locked: !!item.isLocked(),
            targeted: !!item.isTargeted(), clips: count(item.clips)};
        if (kind === "audio") {
            entry.volume = Number(trackVolume(index).getParamValue("Volume"));
        }
        info[kind].push(entry);
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
        if (given(spec.volume_db) && !trackVolume(spec.track).setParamValue("Volume",
                Math.pow(10, spec.volume_db / 20).toFixed(8))) {
            fail("Premiere could not set the Volume of audio track " + spec.track);
        }
    }
    report.sequence = sequence.name;
    report.before = before;
    report.after = counts(sequence);
    report.tracks = state(sequence);
}
