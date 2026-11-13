// Premiere Pro: cut clips onto one video track, lay an optional audio file under them, add
// transitions and export the master. Input: {project, clips, audio, master, preset, fps, report}; each
// clip is {file, start, in_point, out_point, transition, frames} in seconds on the frame grid.
function sourceItem(path) {
    var name = new File(path).name, root = app.project.rootItem, i;
    for (i = 0; i < root.children.numItems; i++) {
        if (root.children[i].name === decodeURI(name) || root.children[i].name === name) {
            return root.children[i];
        }
    }
    fail("Imported item not found: " + name);
}

function cutTimecode(frames, fps) {
    var f = frames % fps, s = Math.floor(frames / fps);
    return "00:00:" + (s < 10 ? "0" : "") + s + ":" + (f < 10 ? "0" : "") + f;
}

function clear(lane) {
    while (lane.clips.numItems > 0) {
        lane.clips[0].remove(false, false);
    }
}

function run(A, report) {
    var i, clip, files = [], sequence, video, source, entry, effect, index = 0, first, lane;
    report.project = A.project;
    report.master = A.master;
    report.transitions = [];
    // A project left open by an earlier cut stalls newProject on the same path, so close every one unsaved.
    closeAll();
    if (!app.newProject(A.project)) {
        fail("Premiere could not create " + A.project);
    }
    for (i = 0; i < A.clips.length; i++) {
        files.push(A.clips[i].file);
    }
    if (A.audio) {
        files.push(A.audio);
    }
    if (!app.project.importFiles(files, true, app.project.rootItem, false)) {
        fail("Premiere could not import " + files.join(", "));
    }

    // The sequence takes its settings from the first clip; the clips it placed are removed.
    sequence = app.project.createNewSequenceFromClips("CUT", [sourceItem(A.clips[0].file)], app.project.rootItem);
    video = sequence.videoTracks[0];
    clear(video);
    for (i = 0; i < sequence.audioTracks.numTracks; i++) {
        clear(sequence.audioTracks[i]);
    }
    for (i = 0; i < A.clips.length; i++) {
        clip = A.clips[i];
        source = sourceItem(clip.file);
        source.setInPoint(clip.in_point, 4);
        source.setOutPoint(clip.out_point, 4);
        video.overwriteClip(source, clip.start);
    }
    if (A.audio) {
        sequence.audioTracks[0].overwriteClip(sourceItem(A.audio), 0);
    }

    app.enableQE();
    lane = qe.project.getActiveSequence().getVideoTrackAt(0);
    for (i = 0; i < lane.numItems; i++) {
        entry = lane.getItemAt(i);
        if (entry.type === "Empty") {
            continue;
        }
        clip = A.clips[index];
        index += 1;
        if (!clip.transition || clip.frames <= 0) {
            continue;
        }
        try {
            effect = qe.project.getVideoTransitionByName(clip.transition);
            first = index === 1;
            entry.addTransition(effect, true, cutTimecode(clip.frames, A.fps), cutTimecode(0, A.fps),
                first ? 0 : 0.5, first, true);
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
