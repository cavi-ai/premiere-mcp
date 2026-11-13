// Add a QE transition at the start or end of a clip on any track. Input: {sequence, kind, track,
// at, position_index, transition (Premiere's name), frames, edge (start|end), alignment (0 starts at
// the cut, 0.5 is centered, 1 ends at it), single_sided}.
function timecode(frames, fps) {
    var f = frames % fps, s = Math.floor(frames / fps);
    return "00:00:" + (s < 10 ? "0" : "") + s + ":" + (f < 10 ? "0" : "") + f;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        fps = frameRate(sequence), entry = qeItem(sequence, A.kind, A.track, clip), effect, found = null;
    effect = A.kind === "audio" ? qe.project.getAudioTransitionByName(A.transition)
        : qe.project.getVideoTransitionByName(A.transition);
    if (!effect) {
        fail("Premiere has no " + A.kind + " transition named " + A.transition);
    }
    entry.addTransition(effect, A.edge === "start", timecode(A.frames, fps), timecode(0, fps), A.alignment,
        A.single_sided, true);
    each(track(sequence, A.kind, A.track).transitions, function (move) {
        var from = secs(move.start), to = secs(move.end), edge = A.edge === "start" ? secs(clip.start) : secs(clip.end);
        if (!found && from - 0.001 <= edge && edge <= to + 0.001) {
            found = {name: move.name || null, start: from, end: to};
        }
    });
    if (!found) {
        fail("Premiere did not add a transition at the " + A.edge + " of the clip");
    }
    report.clip = clip.name;
    report.transition = found;
}
