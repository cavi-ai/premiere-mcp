// Add a QE transition at the start or end of a clip on any track, or remove the one there. Input: {sequence,
// kind, track, at, position_index, transition (Premiere's name), frames, edge (start|end), alignment (0
// starts at the cut, 0.5 is centered, 1 ends at it), single_sided, remove}.
function covering(sequence, A, clip) {
    var edge = A.edge === "start" ? secs(clip.start) : secs(clip.end), found = null;
    each(track(sequence, A.kind, A.track).transitions, function (move, index) {
        var from = secs(move.start), to = secs(move.end);
        if (!found && from - 0.001 <= edge && edge <= to + 0.001) {
            found = {move: move, index: index, info: {name: move.name || null, start: from, end: to}};
        }
    });
    return found;
}

function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        base = Math.round(frameRate(sequence)), effect, found, before;
    report.clip = clip.name;
    if (A.remove) {
        found = covering(sequence, A, clip);
        if (!found) {
            fail("No transition at the " + A.edge + " of the clip");
        }
        before = count(track(sequence, A.kind, A.track).transitions);
        found.move.remove(false, false);
        if (count(track(sequence, A.kind, A.track).transitions) !== before - 1) {
            fail("Premiere did not remove the transition at the " + A.edge + " of the clip");
        }
        report.removed = found.info;
        return;
    }
    app.enableQE();
    effect = A.kind === "audio" ? qe.project.getAudioTransitionByName(A.transition)
        : qe.project.getVideoTransitionByName(A.transition);
    if (!effect) {
        fail("Premiere has no " + A.kind + " transition named " + A.transition);
    }
    qeItem(sequence, A.kind, A.track, clip).addTransition(effect, A.edge === "start", frameCode(A.frames, base, 0),
        frameCode(0, base, 0), A.alignment, A.single_sided, true);
    found = covering(sequence, A, clip);
    if (!found) {
        fail("Premiere did not add a transition at the " + A.edge + " of the clip");
    }
    report.transition = found.info;
}
