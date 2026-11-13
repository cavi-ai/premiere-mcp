// Add a video or audio effect to a placed clip through QE. Input: {sequence, kind, track, at |
// position_index, effect}. Reports the clip's components after.
function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        item = qeItem(sequence, A.kind, A.track, clip), before = count(clip.components), effect;
    effect = A.kind === "audio" ? qe.project.getAudioEffectByName(A.effect) : qe.project.getVideoEffectByName(A.effect);
    if (!effect) {
        fail("Premiere has no " + A.kind + " effect named " + A.effect);
    }
    if (!(A.kind === "audio" ? item.addAudioEffect(effect) : item.addVideoEffect(effect))) {
        fail("Premiere did not add " + A.effect);
    }
    report.clip = clip.name;
    report.components_before = before;
    report.components = describeComponents(clip);
    if (report.components.length <= before) {
        fail("The clip has no new component after adding " + A.effect);
    }
}
