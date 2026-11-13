// Describe the open project: bins, project items, sequences with every track's clips and
// transitions, and sequence markers. Input: {sequence} (a name; every sequence when empty).
function field(xml, name) {
    var found = new RegExp("Column\\.Intrinsic\\." + name + ">([^<]*)<").exec(xml);
    return found ? found[1] : null;
}

function seconds(code, fps) {
    var p = String(code).split(/[:;]/);
    return p.length === 4 && fps ? Number(p[0]) * 3600 + Number(p[1]) * 60 + Number(p[2]) + Number(p[3]) / fps : null;
}

function itemInfo(child, binPath, sequenceIds) {
    var info = {name: child.name, bin: binPath, kind: isBin(child) ? "bin" : "clip", media_path: null,
        offline: null, duration: null, fps: null, width: null, height: null}, xml = "", size, rate;
    if (info.kind === "bin") {
        return info;
    }
    if (sequenceIds[child.nodeId]) {
        info.kind = "sequence";
        return info;
    }
    info.media_path = mediaPath(child);
    try {
        info.offline = child.isOffline();
    } catch (error) {
        info.offline = null;
    }
    try {
        xml = child.getProjectMetadata();
    } catch (error) {
        return info;
    }
    rate = parseFloat(field(xml, "MediaTimebase"));
    info.fps = isNaN(rate) || field(xml, "MediaType") !== "Video" ? null : rate;
    info.duration = seconds(field(xml, "MediaDuration"), rate);
    size = /(\d+)\s*x\s*(\d+)/.exec(field(xml, "VideoInfo") || "");
    if (size) {
        info.width = Number(size[1]);
        info.height = Number(size[2]);
    }
    return info;
}

function clipInfo(clip, position) {
    return {position: position, name: clip.name, start: secs(clip.start), end: secs(clip.end),
        in_point: secs(clip.inPoint), out_point: secs(clip.outPoint), media_path: mediaPath(clip.projectItem)};
}

function laneInfo(lane, index) {
    var info = {index: index, name: lane.name, clips: [], transitions: []};
    each(lane.clips, function (clip, i) {
        info.clips.push(clipInfo(clip, i));
    });
    each(lane.transitions, function (move) {
        info.transitions.push({name: move.name || null, start: secs(move.start), end: secs(move.end)});
    });
    return info;
}

function markerList(sequence) {
    var list = [], marker = sequence.markers.getFirstMarker();
    while (marker) {
        list.push({name: marker.name, comment: marker.comments, start: secs(marker.start), end: secs(marker.end)});
        marker = sequence.markers.getNextMarker(marker);
    }
    return list;
}

function sequenceInfo(sequence) {
    var info = {name: sequence.name, id: sequence.sequenceID, fps: TICKS / Number(sequence.timebase),
        width: sequence.frameSizeHorizontal, height: sequence.frameSizeVertical, end: endSeconds(sequence),
        video: [], audio: [], markers: markerList(sequence)};
    each(sequence.videoTracks, function (lane, i) {
        info.video.push(laneInfo(lane, i));
    });
    each(sequence.audioTracks, function (lane, i) {
        info.audio.push(laneInfo(lane, i));
    });
    return info;
}

function run(A, report) {
    var ids = {}, bins = [], items = [];
    if (!app.project) {
        fail("No project is open");
    }
    report.project = app.project.path;
    each(app.project.sequences, function (sequence) {
        ids[sequence.projectItem.nodeId] = true;
    });
    (function visit(bin, path) {
        each(bin.children, function (child) {
            var info = itemInfo(child, path, ids);
            if (info.kind === "bin") {
                bins.push(path ? path + "/" + child.name : child.name);
                visit(child, bins[bins.length - 1]);
            }
            items.push(info);
        });
    })(app.project.rootItem, "");
    report.bins = bins;
    report.items = items;
    report.sequences = [];
    each(app.project.sequences, function (sequence) {
        if (!A.sequence || sequence.name === A.sequence) {
            report.sequences.push(sequenceInfo(sequence));
        }
    });
    if (A.sequence && !report.sequences.length) {
        fail("No sequence " + A.sequence);
    }
}
