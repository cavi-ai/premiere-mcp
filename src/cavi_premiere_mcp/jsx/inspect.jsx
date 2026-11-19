// Describe the open project: bins, project items, sequences with every track's clips and
// transitions, and sequence markers. Input: {sequence, active, items, tracks}: the sequence with that id or
// every one with that name; with neither, every sequence, or only the active one when active is true. items
// false leaves out the project items, tracks false each sequence's tracks and markers.
// Seconds of a media timecode at a media rate such as 29.97: its frames are counted at the whole timecode
// base (30) and last 1001/30000 s each; a ";" timecode at 29.97 or 59.94 is drop frame.
function seconds(code, rate) {
    var p = String(code).split(/[:;]/), base = Math.round(rate),
        ntsc = Math.abs(rate - base * 1000 / 1001) < 0.01,
        drop = ntsc && (base === 30 || base === 60) && String(code).indexOf(";") >= 0 ? base / 15 : 0, minutes;
    if (p.length !== 4 || !rate) {
        return null;
    }
    minutes = Number(p[0]) * 60 + Number(p[1]);
    return ((minutes * 60 + Number(p[2])) * base + Number(p[3]) - drop * (minutes - Math.floor(minutes / 10)))
        / (ntsc ? base * 1000 / 1001 : rate);
}

function itemInfo(child, binPath, sequenceIds) {
    var info = {name: child.name, id: child.nodeId, bin: binPath, kind: isBin(child) ? "bin" : "clip",
        media_path: null, offline: null, duration: null, clip_duration: null, label: null, fps: null, width: null, height: null},
        xml = "", size, rate;
    if (info.kind === "bin") {
        return info;
    }
    if (sequenceIds[child.nodeId]) {
        info.kind = "sequence";
        return info;
    }
    info.media_path = mediaPath(child);
    try {
        info.label = Number(child.getColorLabel());
    } catch (error) {
        info.label = null;
    }
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
    info.clip_duration = seconds(field(xml, "VideoDuration"), rate);
    size = /(\d+)\s*x\s*(\d+)/.exec(field(xml, "VideoInfo") || "");
    if (size) {
        info.width = Number(size[1]);
        info.height = Number(size[2]);
    }
    return info;
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
        list.push(markerInfo(marker));
        marker = sequence.markers.getNextMarker(marker);
    }
    return list;
}

function sequenceInfo(sequence, active, tracks) {
    var info = {name: sequence.name, id: sequence.sequenceID,
        active: !!active && active.sequenceID === sequence.sequenceID, fps: TICKS / Number(sequence.timebase), width: sequence.frameSizeHorizontal,
        height: sequence.frameSizeVertical, end: endSeconds(sequence), video: [], audio: [], markers: []};
    if (!tracks) {
        return info;
    }
    info.markers = markerList(sequence);
    each(sequence.videoTracks, function (lane, i) {
        info.video.push(laneInfo(lane, i));
    });
    each(sequence.audioTracks, function (lane, i) {
        info.audio.push(laneInfo(lane, i));
    });
    return info;
}

function run(A, report) {
    var ids = {}, bins = [], items = [], active, chosen = [], i;
    if (!app.project) {
        fail("No project is open");
    }
    report.project = app.project.path;
    each(app.project.sequences, function (sequence) {
        ids[sequence.projectItem.nodeId] = true;
    });
    (function visit(bin, path) {
        each(bin.children, function (child) {
            var info = A.items === false ? null : itemInfo(child, path, ids);
            if (isBin(child)) {
                bins.push(path ? path + "/" + child.name : child.name);
                visit(child, bins[bins.length - 1]);
            }
            if (info) {
                items.push(info);
            }
        });
    })(app.project.rootItem, "");
    report.bins = bins;
    report.items = items;
    report.sequences = [];
    active = app.project.activeSequence;
    if (A.sequence) {
        chosen = sequencesFor(A.sequence);
        if (!chosen.length) {
            fail("No sequence " + A.sequence);
        }
    } else {
        each(app.project.sequences, function (sequence) {
            if (!A.active || (active && sequence.sequenceID === active.sequenceID)) {
                chosen.push(sequence);
            }
        });
    }
    for (i = 0; i < chosen.length; i++) {
        report.sequences.push(sequenceInfo(chosen[i], active, A.tracks !== false));
    }
}
