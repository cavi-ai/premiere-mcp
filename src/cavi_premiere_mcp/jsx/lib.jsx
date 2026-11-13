// Shared helpers for the tool scripts. A tool script defines run(A, report); tail.jsx calls it with
// CAVI_ARGS, writes the JSON report to A.report and answers "OK" or "ERROR".
var TICKS = 254016000000;

function quote(text) {
    var out = "", i, code, ch;
    text = String(text);
    for (i = 0; i < text.length; i++) {
        ch = text.charAt(i);
        code = text.charCodeAt(i);
        if (ch === "\\" || ch === '"') {
            out += "\\" + ch;
        } else if (code < 32 || code === 0x2028 || code === 0x2029) {
            out += "\\u" + ("0000" + code.toString(16)).slice(-4);
        } else {
            out += ch;
        }
    }
    return '"' + out + '"';
}

function stringify(value) {
    if (value === null || value === undefined) {
        return "null";
    }
    if (typeof value === "number") {
        return isFinite(value) ? String(value) : "null";
    }
    if (typeof value === "boolean") {
        return String(value);
    }
    if (typeof value === "string") {
        return quote(value);
    }
    var parts = [], i, key;
    if (value instanceof Array) {
        for (i = 0; i < value.length; i++) {
            parts.push(stringify(value[i]));
        }
        return "[" + parts.join(",") + "]";
    }
    for (key in value) {
        if (value.hasOwnProperty(key)) {
            parts.push(quote(key) + ":" + stringify(value[key]));
        }
    }
    return "{" + parts.join(",") + "}";
}

function save(path, report) {
    var file = new File(path);
    file.encoding = "UTF-8";
    file.lineFeed = "Unix";
    if (!file.open("w")) {
        fail("Cannot write the report to " + path);
    }
    file.write(stringify(report));
    file.close();
}

function given(value) {
    return value !== null && value !== undefined;
}

function fail(message) {
    throw new Error(message);
}

function count(list) {
    var names = ["numItems", "numSequences", "numTracks"], i;
    for (i = 0; i < names.length; i++) {
        if (typeof list[names[i]] === "number") {
            return list[names[i]];
        }
    }
    return 0;
}

function each(list, visit) {
    for (var i = 0, n = count(list); i < n; i++) {
        visit(list[i], i);
    }
}

function secs(time) {
    return time ? Number(time.seconds) : null;
}

// Sequence.end is a string of ticks.
function endSeconds(sequence) {
    return Number(sequence.end) / TICKS;
}

function mediaPath(item) {
    try {
        return item.getMediaPath() || null;
    } catch (error) {
        return null;
    }
}

function isBin(item) {
    return item.type === ProjectItemType.BIN || item.type === ProjectItemType.ROOT;
}

function walk(bin, visit) {
    each(bin.children, function (child) {
        visit(child, bin);
        if (isBin(child)) {
            walk(child, visit);
        }
    });
}

function sameFile(a, b) {
    return a && b && new File(a).fsName === new File(b).fsName;
}

// A project item by absolute media path, else by name; bins are found by name.
function findItem(ref) {
    var found = null;
    walk(app.project.rootItem, function (child) {
        if (!found && (sameFile(mediaPath(child), ref) || child.name === ref)) {
            found = child;
        }
    });
    if (!found) {
        fail("No project item " + ref);
    }
    return found;
}

function findBin(name, create) {
    var found = null;
    if (!name) {
        return app.project.rootItem;
    }
    walk(app.project.rootItem, function (child) {
        if (!found && isBin(child) && child.name === name) {
            found = child;
        }
    });
    if (!found && create) {
        found = app.project.rootItem.createBin(name);
    }
    if (!found) {
        fail("No bin " + name);
    }
    return found;
}

// The named sequence, opened so that it is the active one; the active sequence when no name is given.
function findSequence(name) {
    var found = null;
    if (!name) {
        found = app.project.activeSequence;
    } else {
        each(app.project.sequences, function (candidate) {
            if (!found && candidate.name === name) {
                found = candidate;
            }
        });
    }
    if (!found) {
        fail(name ? "No sequence " + name : "No active sequence");
    }
    if (!app.project.activeSequence || app.project.activeSequence.sequenceID !== found.sequenceID) {
        app.project.openSequence(found.sequenceID);
        found = app.project.activeSequence || found;
    }
    return found;
}

function track(sequence, kind, index) {
    var list = kind === "audio" ? sequence.audioTracks : sequence.videoTracks;
    if (index < 0 || index >= list.numTracks) {
        fail("No " + kind + " track " + index + " (the sequence has " + list.numTracks + ")");
    }
    return list[index];
}

// The clip on a track that covers a time, or the one starting at it; index selects by position.
function findClip(sequence, kind, index, at, position) {
    var lane = track(sequence, kind, index), found = null;
    each(lane.clips, function (clip, i) {
        if (found) {
            return;
        }
        if (position !== null && position !== undefined ? i === position
                : at >= secs(clip.start) - 0.0005 && at < secs(clip.end) - 0.0005) {
            found = clip;
        }
    });
    if (!found) {
        fail("No clip on " + kind + " track " + index + (position !== null && position !== undefined
            ? " at position " + position : " at " + at + " s"));
    }
    return found;
}

function frameSeconds(sequence) {
    return Number(sequence.timebase) / TICKS;
}

function closeAll() {
    for (var i = app.projects.numProjects - 1; i >= 0; i--) {
        app.projects[i].closeDocument(0, 0);
    }
}

function tcOf(seconds, fps) {
    var frames = Math.round(seconds * fps), s = Math.floor(frames / fps), m = Math.floor(s / 60);

    function two(n) {
        return (n < 10 ? "0" : "") + n;
    }
    return two(Math.floor(m / 60)) + ":" + two(m % 60) + ":" + two(s % 60) + ":" + two(frames % fps);
}

function frameRate(sequence) {
    return Math.round(TICKS / Number(sequence.timebase));
}

// The QE item of a clip: the nth item of type Clip on the QE track is the nth clip of the track.
function qeItem(sequence, kind, index, clip) {
    var position = -1, n = 0, i, lane, item;
    each(track(sequence, kind, index).clips, function (candidate, k) {
        if (candidate.nodeId === clip.nodeId) {
            position = k;
        }
    });
    app.enableQE();
    lane = kind === "audio" ? qe.project.getActiveSequence().getAudioTrackAt(index)
        : qe.project.getActiveSequence().getVideoTrackAt(index);
    for (i = 0; i < lane.numItems; i++) {
        item = lane.getItemAt(i);
        if (item.type === "Clip") {
            if (n === position) {
                return item;
            }
            n += 1;
        }
    }
    fail("QE has no item for the clip");
}

// Seconds covered by an export range: the whole sequence, its in/out points or its work area.
function rangeSpan(sequence, range) {
    var from, to;
    if (range === "in_out") {
        from = sequence.getInPointAsTime();
        to = sequence.getOutPointAsTime();
        if (Number(from.ticks) < 0 || Number(to.ticks) < 0) {
            fail("The sequence has no in and out points");
        }
        return secs(to) - secs(from);
    }
    if (range === "work_area") {
        return Number(sequence.getWorkAreaOutPoint()) - Number(sequence.getWorkAreaInPoint());
    }
    return endSeconds(sequence);
}

// The components of a clip with their parameters: {name, index, params: [{name, index, value, keyed}]}.
function describeComponents(clip) {
    var list = [];
    each(clip.components, function (component, i) {
        var info = {name: component.displayName, index: i, params: []};
        each(component.properties, function (param, k) {
            var value = null, keyed = false;
            try {
                value = param.getValue();
                value = typeof value === "object" && value !== null ? stringify(value) : value;
            } catch (error) {
                value = null;
            }
            try {
                keyed = !!param.isTimeVarying();
            } catch (error) {
                keyed = false;
            }
            info.params.push({name: param.displayName, index: k, value: value === undefined ? null : value,
                keyed: keyed});
        });
        list.push(info);
    });
    return list;
}

function field(xml, name) {
    var found = new RegExp("Column\\.Intrinsic\\." + name + ">([^<]*)<").exec(xml);
    return found ? found[1] : null;
}
