// Import a motion graphics template onto a track and set its text parameters. Input: {sequence,
// mogrt, at, video_track, audio_track, duration, text: {parameter name: text}}. Templates built in
// After Effects expose their text parameters; native Essential Graphics titles expose none.
function textParameters(comp) {
    var found = [];
    each(comp.properties, function (candidate) {
        var raw = candidate.getValue();
        if (typeof raw === "string" && raw.indexOf("textEditValue") >= 0) {
            found.push(candidate);
        }
    });
    return found;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), placed, comp, params, name, i, value, found, limit;
    // importMGT puts a template on the last track when the offset is past it, so refuse that.
    track(sequence, "video", A.video_track);
    placed = sequence.importMGT(A.mogrt, String(Math.round(A.at * TICKS)), A.video_track, A.audio_track);
    if (!placed) {
        fail("Premiere could not import " + A.mogrt);
    }
    if (A.duration) {
        limit = new Time();
        limit.seconds = A.at + A.duration;
        placed.end = limit;
    }
    report.clip = placed.name;
    report.start = secs(placed.start);
    report.end = secs(placed.end);
    each(sequence.videoTracks, function (lane, index) {
        each(lane.clips, function (candidate) {
            if (candidate.name === placed.name && candidate.start.ticks === placed.start.ticks
                    && candidate.end.ticks === placed.end.ticks) {
                report.track = index;
            }
        });
    });
    comp = placed.getMGTComponent();
    report.text = {};
    if (!comp) {
        for (name in A.text) {
            fail("The template exposes no text parameters; use a template built in After Effects");
        }
        return;
    }
    params = textParameters(comp);
    report.parameters = [];
    for (i = 0; i < params.length; i++) {
        report.parameters.push(params[i].displayName);
    }
    for (name in A.text) {
        if (!A.text.hasOwnProperty(name)) {
            continue;
        }
        found = null;
        for (i = 0; i < params.length; i++) {
            if (params[i].displayName === name) {
                found = params[i];
            }
        }
        if (!found) {
            fail("No text parameter " + name + "; the template has: " + report.parameters.join(", "));
        }
        value = eval("(" + found.getValue() + ")");
        value.textEditValue = A.text[name];
        found.setValue(stringify(value), true);
        report.text[name] = eval("(" + found.getValue() + ")").textEditValue;
    }
}
