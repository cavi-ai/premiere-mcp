// Change a sequence. Input: {sequence, settings: {width, height, fps, audio_rate}, in_point, out_point,
// nest: {name, clips: [{kind, track, position_index}]}, duplicate (name of the copy), new_name, delete}.
// Seconds. Applied in that order; delete is last.
function ticksTime(ticks) {
    var t = new Time();
    t.ticks = String(Math.round(ticks));
    return t;
}

function sequenceNames() {
    var names = [];
    each(app.project.sequences, function (candidate) {
        names.push(candidate.name);
    });
    return names;
}

function describe(sequence) {
    var settings = sequence.getSettings(), mark = sequence.getInPointAsTime(), out = sequence.getOutPointAsTime();
    return {name: sequence.name, id: sequence.sequenceID, width: settings.videoFrameWidth,
        height: settings.videoFrameHeight, fps: TICKS / Number(settings.videoFrameRate.ticks),
        audio_rate: Math.round(TICKS / Number(settings.audioSampleRate.ticks)), end: endSeconds(sequence),
        in_point: Number(mark.ticks) < 0 ? null : secs(mark), out_point: Number(out.ticks) < 0 ? null : secs(out)};
}

function run(A, report) {
    var sequence = findSequence(A.sequence), settings, fps, clips = [], i, before, made = null, key;
    if (given(A.settings)) {
        settings = sequence.getSettings();
        if (given(A.settings.width)) {
            settings.videoFrameWidth = settings.previewFrameWidth = A.settings.width;
        }
        if (given(A.settings.height)) {
            settings.videoFrameHeight = settings.previewFrameHeight = A.settings.height;
        }
        if (given(A.settings.fps)) {
            fps = A.settings.fps === Math.round(A.settings.fps) ? A.settings.fps : Math.round(A.settings.fps) * 1000 / 1001;
            settings.videoFrameRate = ticksTime(TICKS / fps);
        }
        if (given(A.settings.audio_rate)) {
            settings.audioSampleRate = ticksTime(TICKS / A.settings.audio_rate);
        }
        if (!sequence.setSettings(settings)) {
            fail("Premiere refused the sequence settings");
        }
    }
    if (given(A.in_point)) {
        sequence.setInPoint(A.in_point);
    }
    if (given(A.out_point)) {
        sequence.setOutPoint(A.out_point);
    }
    if (given(A.nest)) {
        app.project.openSequence(sequence.sequenceID);
        for (i = 0; i < A.nest.clips.length; i++) {
            key = A.nest.clips[i];
            clips.push(findClip(sequence, key.kind, key.track, null, key.position_index));
        }
        for (i = 0; i < clips.length; i++) {
            clips[i].setSelected(false, true);
            clips[i].setSelected(true, true);
        }
        before = sequenceNames().length;
        made = sequence.createSubsequence(false);
        if (!made || sequenceNames().length !== before + 1) {
            fail("Premiere did not create the nested sequence");
        }
        if (A.nest.name) {
            made.name = A.nest.name;
        }
        report.nested = describe(made);
    }
    if (given(A.duplicate)) {
        before = sequenceNames().length;
        if (!sequence.clone() || sequenceNames().length !== before + 1) {
            fail("Premiere did not duplicate the sequence");
        }
        made = app.project.activeSequence;
        if (A.duplicate) {
            made.name = A.duplicate;
        }
        report.duplicate = describe(made);
    }
    if (given(A.new_name)) {
        sequence.name = A.new_name;
    }
    if (A.remove) {
        report.deleted = sequence.name;
        before = sequenceNames().length;
        app.project.deleteSequence(sequence);
        if (sequenceNames().length !== before - 1) {
            fail("Premiere did not delete the sequence");
        }
    } else {
        report.sequence = describe(sequence);
    }
    report.sequences = sequenceNames();
}
