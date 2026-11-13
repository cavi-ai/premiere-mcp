// Set Motion position (pixels), scale, rotation, Opacity and audio Volume (dB) on a placed clip,
// static or keyframed. Keyframe times are seconds from the clip's start. Input: {sequence, kind,
// track, at, position_index, position, scale, rotation, opacity, volume_db, keyframes: [{time, ...}]}.
// Volume Level is stored as linear gain where 0.17782794 is 0 dB.
var UNITY = 0.17782794;

function component(clip, name) {
    var found = null;
    each(clip.components, function (candidate) {
        if (!found && candidate.displayName === name) {
            found = candidate;
        }
    });
    if (!found) {
        fail("The clip has no " + name + " component");
    }
    return found;
}

function property(clip, group, name) {
    var found = null;
    each(component(clip, group).properties, function (candidate) {
        if (!found && candidate.displayName === name) {
            found = candidate;
        }
    });
    if (!found) {
        fail(group + " has no " + name);
    }
    return found;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        width = sequence.frameSizeHorizontal, height = sequence.frameSizeVertical, begin = secs(clip.inPoint),
        names = {position: ["Motion", "Position"], scale: ["Motion", "Scale"], rotation: ["Motion", "Rotation"],
            opacity: ["Opacity", "Opacity"], volume_db: ["Volume", "Level"]}, keys = A.keyframes || [], name, i,
        handles = {}, applied = {}, series;

    function toRaw(key, value) {
        if (key === "position") {
            return [value[0] / width, value[1] / height];
        }
        return key === "volume_db" ? UNITY * Math.pow(10, value / 20) : value;
    }

    function round(value) {
        return Math.round(value * 10000) / 10000;
    }

    function fromRaw(key, value) {
        if (key === "position") {
            return [round(Number(value[0]) * width), round(Number(value[1]) * height)];
        }
        return round(key === "volume_db" ? 20 * Math.log(Number(value) / UNITY) / Math.LN10 : Number(value));
    }

    function handle(key) {
        if (!handles[key]) {
            handles[key] = property(clip, names[key][0], names[key][1]);
        }
        return handles[key];
    }

    for (name in names) {
        if (names.hasOwnProperty(name) && A[name] !== null && A[name] !== undefined) {
            handle(name).setValue(toRaw(name, A[name]), true);
            applied[name] = fromRaw(name, handle(name).getValue());
        }
    }
    report.keyframes = {};
    for (name in names) {
        if (!names.hasOwnProperty(name)) {
            continue;
        }
        series = [];
        for (i = 0; i < keys.length; i++) {
            if (keys[i][name] !== null && keys[i][name] !== undefined) {
                series.push(keys[i]);
            }
        }
        if (!series.length) {
            continue;
        }
        handle(name).setTimeVarying(true);
        for (i = 0; i < series.length; i++) {
            handle(name).addKey(begin + series[i].time);
            handle(name).setValueAtKey(begin + series[i].time, toRaw(name, series[i][name]), true);
        }
        report.keyframes[name] = [];
        for (i = 0; i < series.length; i++) {
            report.keyframes[name].push({time: series[i].time,
                value: fromRaw(name, handle(name).getValueAtTime(begin + series[i].time))});
        }
    }
    report.clip = clip.name;
    report.applied = applied;
}
