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
    file.open("w");
    file.write(stringify(report));
    file.close();
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
