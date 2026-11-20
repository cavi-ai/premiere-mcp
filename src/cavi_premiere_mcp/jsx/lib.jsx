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

// A Time of the given seconds, on the tick grid.
function timeAt(seconds) {
    var t = new Time();
    t.ticks = String(Math.round(seconds * TICKS));
    return t;
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

var MARKER_TYPES = {comment: "setTypeAsComment", chapter: "setTypeAsChapter", segmentation: "setTypeAsSegmentation"};

// Colour (index 0 to 7) and type of a marker; a weblink needs its url.
function styleMarker(marker, spec) {
    if (given(spec.color)) {
        marker.setColorByIndex(spec.color);
    }
    if (spec.type === "weblink") {
        marker.setTypeAsWebLink(spec.url, "");
    } else if (spec.type) {
        marker[MARKER_TYPES[spec.type]]();
    }
}

function markerInfo(marker) {
    var info = {name: marker.name, comment: marker.comments, start: secs(marker.start), end: secs(marker.end),
        color: marker.getColorByIndex(), type: String(marker.type).toLowerCase()};
    if (info.type === "weblink") {
        info.url = marker.getWebLinkURL();
    }
    return info;
}

// Source seconds a clip plays per timeline second: 2 at 200%. A clip's DOM in and out points read source
// time divided by it; getSpeed stays positive on a reversed clip.
function speedOf(clip) {
    var ratio;
    try {
        ratio = Number(clip.getSpeed());
    } catch (error) {
        ratio = 1;
    }
    return ratio > 0 && isFinite(ratio) ? ratio : 1;
}

function reversedOf(clip) {
    try {
        return !!clip.isSpeedReversed();
    } catch (error) {
        return false;
    }
}

function micro(seconds) {
    return Math.round(seconds * 1000000) / 1000000;
}

function sourceIn(clip) {
    return micro(secs(clip.inPoint) * speedOf(clip));
}

function sourceOut(clip) {
    return micro(secs(clip.outPoint) * speedOf(clip));
}

// Keyframe times are source times: a key `offset` seconds after the clip's start on the timeline sits at
// (in point + offset) x speed. Keys on a reversed clip are refused.
function keyClock(clip) {
    var begin = secs(clip.inPoint), ratio = speedOf(clip);
    if (reversedOf(clip)) {
        fail("Keyframes on a reversed clip are not supported");
    }
    return function (offset) {
        return (begin + offset) * ratio;
    };
}

function clipInfo(clip, position) {
    var item = clip.projectItem || null;
    return {position: position, name: clip.name, item_id: item ? item.nodeId : null, start: secs(clip.start),
        end: secs(clip.end), in_point: sourceIn(clip), out_point: sourceOut(clip),
        speed: Math.round(speedOf(clip) * 10000) / 100, reversed: reversedOf(clip), media_path: mediaPath(item)};
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

// The one entry of a lookup; none, or several that only their ids tell apart, is refused.
function single(found, what, ref, idOf) {
    var ids = [], i;
    if (!found.length) {
        fail("No " + what + " " + ref);
    }
    if (found.length > 1) {
        for (i = 0; i < found.length; i++) {
            ids.push(idOf(found[i]));
        }
        fail(found.length + " " + what + "s match " + ref + "; give one of their ids: " + ids.join(", "));
    }
    return found[0];
}

// Lists kept by text; the "k" prefix keeps a text such as "constructor" off the object's own fields.
function entriesOf(map, text) {
    return map.hasOwnProperty("k" + text) ? map["k" + text] : null;
}

function addTo(map, text, value) {
    if (!map.hasOwnProperty("k" + text)) {
        map["k" + text] = [];
    }
    map["k" + text].push(value);
}

// Project items by id, by media path and by name, from one walk of the project.
function itemIndex() {
    var index = {id: {}, path: {}, name: {}};
    walk(app.project.rootItem, function (child) {
        var path = mediaPath(child);
        addTo(index.id, child.nodeId, child);
        if (path) {
            addTo(index.path, new File(path).fsName, child);
        }
        addTo(index.name, child.name, child);
    });
    return index;
}

// The project items a reference names: the item with that id, else those with that absolute media path,
// else those with that name.
function itemsFor(ref, index) {
    index = index || itemIndex();
    return entriesOf(index.id, ref) || entriesOf(index.path, new File(ref).fsName) || entriesOf(index.name, ref)
        || [];
}

// The one project item (or bin) a reference names; a reference several items answer to is refused.
function findItem(ref, index) {
    return single(itemsFor(ref, index), "project item", ref, function (item) {
        return item.nodeId;
    });
}

// The one project item a reference names, importing a file that no item holds yet.
function itemOrImport(ref) {
    if (!itemsFor(ref).length && new File(ref).exists) {
        app.project.importFiles([ref], true, app.project.rootItem, false);
    }
    return findItem(ref);
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

// The sequences a reference names: the one with that id, else those with that name.
function sequencesFor(ref) {
    var byId = [], byName = [];
    each(app.project.sequences, function (candidate) {
        if (candidate.sequenceID === ref) {
            byId.push(candidate);
        } else if (candidate.name === ref) {
            byName.push(candidate);
        }
    });
    return byId.length ? byId : byName;
}

// The sequence a name or id names, opened so that it is the active one; the active sequence when none is
// given. A name several sequences share is refused.
function findSequence(ref) {
    var found = ref ? single(sequencesFor(ref), "sequence", ref, function (sequence) {
        return sequence.sequenceID;
    }) : app.project.activeSequence;
    if (!found) {
        fail("No active sequence");
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

// Close, unsaved, a project open at the path: Premiere stalls on a second one at the same path.
function closeAt(path) {
    for (var i = app.projects.numProjects - 1; i >= 0; i--) {
        if (sameFile(app.projects[i].path, path)) {
            app.projects[i].closeDocument(0, 0);
        }
    }
}

// Frames dropped per minute by the drop-frame display formats: 102 is 29.97 Drop, 106 is 59.94 Drop.
var DROPPED = {102: 2, 106: 4};

// Frames per second of a sequence, exact: 23.976 is 24000/1001.
function frameRate(sequence) {
    return TICKS / Number(sequence.timebase);
}

function dropped(sequence) {
    try {
        return DROPPED[Number(sequence.getSettings().videoDisplayFormat)] || 0;
    } catch (error) {
        return 0;
    }
}

// The label of a frame number counted at the whole timecode base (30 for 29.97): hh:mm:ss:ff, or the
// drop-frame label hh;mm;ss;ff when `drop` frame numbers are skipped each minute but every tenth.
function frameCode(frames, base, drop) {
    var tenMinutes = base * 600 - drop * 9, minute = base * 60 - drop, rest, s, m, mark = drop ? ";" : ":";

    function two(n) {
        return (n < 10 ? "0" : "") + n;
    }
    if (drop) {
        rest = frames % tenMinutes;
        frames += drop * 9 * Math.floor(frames / tenMinutes)
            + (rest > drop ? drop * Math.floor((rest - drop) / minute) : 0);
    }
    s = Math.floor(frames / base);
    m = Math.floor(s / 60);
    return two(Math.floor(m / 60)) + mark + two(m % 60) + mark + two(s % 60) + mark + two(frames % base);
}

// A time snapped to the sequence's frame grid, in seconds.
function snap(seconds, sequence) {
    var rate = frameRate(sequence);
    return Math.round(seconds * rate) / rate;
}

// The timecode of the frame a sequence time falls on, in the sequence's own timecode.
function tcOf(seconds, sequence) {
    var rate = frameRate(sequence);
    return frameCode(Math.round(seconds * rate), Math.round(rate), dropped(sequence));
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

// How a placement is retimed to play spec.in_point to spec.out_point of the source at spec.speed (percent),
// backwards when spec.reversed; null when it is not retimed. A faster clip is placed at its timeline length
// and sped up in that span; a slower one is placed at its source length and stretched, so the track must be
// free where it grows. Checked before any change.
function retiming(sequence, lane, spec) {
    var ratio = given(spec.speed) ? spec.speed / 100 : 1, length, placed, from, to;
    if (ratio === 1 && spec.reversed !== true) {
        return null;
    }
    if (!given(spec.in_point) || !given(spec.out_point) || !(ratio > 0)) {
        fail("A retimed placement needs its in_point, out_point and a positive speed");
    }
    length = snap((spec.out_point - spec.in_point) / ratio, sequence);
    if (!(length > 0)) {
        fail("The clip would last " + length + " s at " + spec.speed + "%; it must be at least one frame");
    }
    placed = ratio >= 1 ? length : spec.out_point - spec.in_point;
    from = spec.mode === "insert" ? spec.at : spec.at + placed;
    to = from + length - placed;
    each(lane.clips, function (clip) {
        if (to - from > 0.0005 && secs(clip.start) < to - 0.0005 && secs(clip.end) > from + 0.0005) {
            fail("No room for the clip at " + spec.at + " s on " + spec.kind + " track " + spec.track + ": at "
                + spec.speed + "% it lasts " + length + " s and would run into " + clip.name + " at "
                + secs(clip.start) + " s");
        }
    });
    return {ratio: ratio, reversed: spec.reversed === true, length: length, out_point: spec.in_point + placed};
}

// Place a project item on a lane at spec.at with spec.in_point and spec.out_point (source seconds) set for
// this placement only, retimed when spec.speed or spec.reversed asks. Input spec: {at, kind, track,
// in_point, out_point, mode (overwrite|insert), speed, reversed}. Reports the placed clip.
function place(sequence, lane, source, spec) {
    var plan = retiming(sequence, lane, spec), frame = 1 / frameRate(sequence),
        was = {in_point: secs(source.getInPoint()), out_point: secs(source.getOutPoint())}, placed = null,
        position = null, nearest = frame / 2 + 0.001, id;
    if (given(spec.in_point)) {
        source.setInPoint(spec.in_point, 4);
    }
    if (given(spec.out_point)) {
        source.setOutPoint(plan ? plan.out_point : spec.out_point, 4);
    }
    try {
        if (spec.mode === "insert") {
            lane.insertClip(source, spec.at);
        } else {
            lane.overwriteClip(source, spec.at);
        }
    } finally {
        // The in and out points were only for this placement.
        source.setInPoint(was.in_point, 4);
        source.setOutPoint(was.out_point, 4);
    }
    // Premiere moves the start to the nearest frame.
    each(lane.clips, function (clip, i) {
        var off = Math.abs(secs(clip.start) - spec.at);
        if (off < nearest) {
            nearest = off;
            placed = clip;
            position = i;
        }
    });
    if (!placed) {
        fail("The clip is not on " + spec.kind + " track " + spec.track + " at " + spec.at + " s");
    }
    if (plan) {
        if (!qeItem(sequence, spec.kind, spec.track, placed).setSpeed(plan.ratio, tcOf(plan.length, sequence),
                plan.reversed, true, false)) {
            fail("Premiere refused to retime the clip at " + spec.at + " s");
        }
        id = placed.nodeId;
        each(lane.clips, function (clip, i) {
            if (clip.nodeId === id) {
                placed = clip;
                position = i;
            }
        });
        if (Math.abs(secs(placed.end) - secs(placed.start) - plan.length) > frame / 2) {
            fail("Premiere retimed the clip at " + spec.at + " s to " + (secs(placed.end) - secs(placed.start))
                + " s, not " + plan.length + " s");
        }
    }
    return clipInfo(placed, position);
}

// Seconds covered by an export range: the whole sequence, its in/out points or its work area.
function rangeSpan(sequence, range) {
    var from, to, span;
    if (range === "in_out") {
        from = sequence.getInPointAsTime();
        to = sequence.getOutPointAsTime();
        if (Number(from.ticks) < 0 || Number(to.ticks) < 0) {
            fail("The sequence has no in and out points");
        }
        span = secs(to) - secs(from);
    } else if (range === "work_area") {
        span = Number(sequence.getWorkAreaOutPoint()) - Number(sequence.getWorkAreaInPoint());
    } else {
        span = endSeconds(sequence);
    }
    // An empty range writes no file, so the caller would wait for one until its timeout.
    if (span <= 0) {
        fail("Nothing to export: the " + range + " range of " + sequence.name + " is empty");
    }
    return span;
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

// Select exactly the clips whose ids are given, on every track of a sequence; returns the ids selected before.
function setSelection(sequence, ids) {
    var before = {};
    function mark(lane) {
        each(lane.clips, function (clip) {
            var want = ids[clip.nodeId] === true, now = !!clip.isSelected();
            if (now) {
                before[clip.nodeId] = true;
            }
            if (now !== want) {
                clip.setSelected(want, true);
            }
        });
    }
    each(sequence.videoTracks, mark);
    each(sequence.audioTracks, mark);
    return before;
}

// Run action with only this clip selected, then put the earlier selection back.
function onlySelected(sequence, clip, action) {
    var only = {}, before;
    only[clip.nodeId] = true;
    before = setSelection(sequence, only);
    try {
        return action();
    } finally {
        setSelection(sequence, before);
    }
}
