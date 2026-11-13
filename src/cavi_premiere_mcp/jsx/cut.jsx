// Premiere Pro: cut clips onto one video track, lay an optional audio file under them, add
// transitions and export the master. Input global CAVI_ARGS = {project, clips, audio, master,
// preset, fps, report}; each clip is {file, start, in_point, out_point, transition, frames} in
// seconds on the frame grid. Writes a JSON report to CAVI_ARGS.report and answers "OK" or "ERROR".
(function () {
    var A = CAVI_ARGS;
    var report = {project: A.project, master: A.master, transitions: [], warnings: [], errors: []};

    function quote(text) {
        return '"' + String(text).replace(/\\/g, "\\\\").replace(/"/g, '\\"')
            .replace(/\n/g, "\\n").replace(/\r/g, "\\r") + '"';
    }

    function stringify(value) {
        if (value === null || value === undefined) {
            return "null";
        }
        if (typeof value === "number" || typeof value === "boolean") {
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

    function item(path) {
        var name = new File(path).name, root = app.project.rootItem, i;
        for (i = 0; i < root.children.numItems; i++) {
            if (root.children[i].name === decodeURI(name) || root.children[i].name === name) {
                return root.children[i];
            }
        }
        throw new Error("Imported item not found: " + name);
    }

    function timecode(frames) {
        var f = frames % A.fps, s = Math.floor(frames / A.fps);
        return "00:00:" + (s < 10 ? "0" : "") + s + ":" + (f < 10 ? "0" : "") + f;
    }

    function clear(track) {
        while (track.clips.numItems > 0) {
            track.clips[0].remove(false, false);
        }
    }

    function save() {
        var file = new File(A.report);
        file.encoding = "UTF-8";
        file.open("w");
        file.write(stringify(report));
        file.close();
    }

    try {
        cut();
    } catch (failure) {
        report.errors.push(failure + " (line " + failure.line + ")");
    }
    save();
    return report.errors.length ? "ERROR" : "OK";

    function cut() {
    var i, clip, files = [];
    // A project left open by an earlier cut stalls newProject on the same path, so close every one unsaved.
    for (i = app.projects.numProjects - 1; i >= 0; i--) {
        app.projects[i].closeDocument(0, 0);
    }
    if (!app.newProject(A.project)) {
        throw new Error("Premiere could not create " + A.project);
    }
    for (i = 0; i < A.clips.length; i++) {
        files.push(A.clips[i].file);
    }
    if (A.audio) {
        files.push(A.audio);
    }
    app.project.importFiles(files, true, app.project.rootItem, false);

    // The sequence takes its settings from the first clip; the clips it placed are removed.
    var sequence = app.project.createNewSequenceFromClips("CUT", [item(A.clips[0].file)], app.project.rootItem);
    var video = sequence.videoTracks[0];
    clear(video);
    for (i = 0; i < sequence.audioTracks.numTracks; i++) {
        clear(sequence.audioTracks[i]);
    }
    for (i = 0; i < A.clips.length; i++) {
        clip = A.clips[i];
        var source = item(clip.file);
        source.setInPoint(clip.in_point, 4);
        source.setOutPoint(clip.out_point, 4);
        video.overwriteClip(source, clip.start);
    }
    if (A.audio) {
        sequence.audioTracks[0].overwriteClip(item(A.audio), 0);
    }

    app.enableQE();
    var track = qe.project.getActiveSequence().getVideoTrackAt(0), index = 0;
    for (i = 0; i < track.numItems; i++) {
        var entry = track.getItemAt(i);
        if (entry.type === "Empty") {
            continue;
        }
        clip = A.clips[index];
        index += 1;
        if (!clip.transition || clip.frames <= 0) {
            continue;
        }
        try {
            var effect = qe.project.getVideoTransitionByName(clip.transition);
            var first = index === 1;
            entry.addTransition(effect, true, timecode(clip.frames), timecode(0), first ? 0 : 0.5, first, true);
            report.transitions.push("clip " + index + ": " + clip.transition + " " + clip.frames + "f");
        } catch (error) {
            report.warnings.push("clip " + index + " transition: " + error);
        }
    }

    app.project.save();
    report.exported = sequence.exportAsMediaDirect(A.master, A.preset, app.encoder.ENCODE_ENTIRE);
    report.sequence_end = sequence.end;
    app.project.save();
    }
})();
