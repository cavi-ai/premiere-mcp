// Set component parameters on a clip, static or keyframed, or remove the component. Input: {sequence, kind,
// track, at | position_index, component (display name), component_index, list, remove, params: [{name,
// value, color, keyframes: [{time, value, color, interpolation}]}]}. Key times are seconds from the clip's
// start.
var INTERPOLATION = {linear: 0, hold: 4, bezier: 5};

function hexColor(text) {
    var hex = String(text).replace("#", "");
    return [255, parseInt(hex.substr(0, 2), 16), parseInt(hex.substr(2, 2), 16), parseInt(hex.substr(4, 2), 16)];
}

function param(component, name, index) {
    var found = null, n = 0;
    each(component.properties, function (candidate) {
        if (candidate.displayName === name) {
            if (n === (index || 0) && !found) {
                found = candidate;
            }
            n += 1;
        }
    });
    if (!found) {
        fail(component.displayName + " has no parameter " + name);
    }
    return found;
}

function write(handle, value, color) {
    var rgb;
    if (color) {
        rgb = hexColor(color);
        handle.setColorValue(rgb[0], rgb[1], rgb[2], rgb[3], true);
    } else {
        handle.setValue(value, true);
    }
}

// Remove the component_index-th component named A.component through QE, which the DOM cannot do.
function removeComponent(sequence, A, clip) {
    var entry = qeItem(sequence, A.kind, A.track, clip), before = count(clip.components), n = 0, k, found = null,
        after;
    for (k = 0; k < entry.numComponents && !found; k++) {
        if (entry.getComponentAt(k).name === A.component) {
            if (n === (A.component_index || 0)) {
                found = entry.getComponentAt(k);
            }
            n += 1;
        }
    }
    if (!found) {
        fail("Premiere cannot remove " + A.component + " from the clip");
    }
    found.remove();
    after = count(findClip(sequence, A.kind, A.track, A.at, A.position_index).components);
    if (after !== before - 1) {
        fail("Premiere did not remove " + A.component + " (the clip has " + after + " components)");
    }
}

function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        begin = secs(clip.inPoint), component = null, n = 0, i, k, spec, handle, key, at, shown;
    if (A.component) {
        each(clip.components, function (candidate) {
            if (candidate.displayName === A.component) {
                if (n === (A.component_index || 0) && !component) {
                    component = candidate;
                }
                n += 1;
            }
        });
        if (!component) {
            fail("The clip has no " + A.component + " component");
        }
    }
    report.clip = clip.name;
    report.applied = {};
    if (A.remove) {
        removeComponent(sequence, A, clip);
        report.removed = A.component;
        report.components = describeComponents(findClip(sequence, A.kind, A.track, A.at, A.position_index));
        return;
    }
    for (i = 0;i < (A.params || []).length; i++) {
        spec = A.params[i];
        handle = param(component, spec.name, spec.index);
        if (spec.keyframes && spec.keyframes.length) {
            handle.setTimeVarying(true);
            for (k = 0; k < spec.keyframes.length; k++) {
                key = spec.keyframes[k];
                at = begin + key.time;
                handle.addKey(at);
                write({setValue: function (v, u) { handle.setValueAtKey(at, v, u); },
                    setColorValue: function (a, r, g, b, u) { handle.setColorValueAtKey(at, a, r, g, b, u); }},
                    key.value, key.color);
                if (key.interpolation) {
                    handle.setInterpolationTypeAtKey(at, INTERPOLATION[key.interpolation], true);
                }
            }
            shown = [];
            for (k = 0; k < spec.keyframes.length; k++) {
                shown.push({time: spec.keyframes[k].time, value: handle.getValueAtTime(begin + spec.keyframes[k].time)});
            }
            report.applied[spec.name] = shown;
        } else {
            write(handle, spec.value, spec.color);
            shown = handle.getValue();
            report.applied[spec.name] = typeof shown === "object" && shown !== null ? stringify(shown) : shown;
        }
    }
    if (A.list) {
        report.components = [];
        shown = describeComponents(clip);
        for (i = 0; i < shown.length; i++) {
            if (!A.component || shown[i].name === A.component) {
                report.components.push(shown[i]);
            }
        }
    }
}
