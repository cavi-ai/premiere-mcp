// Slip a placed clip: change which part of the source it shows while its place on the timeline stays.
// Input: {sequence, kind, track, at | position_index, offset | in_point, with_linked}. offset moves the
// source in point by that many seconds (positive shows later footage); in_point sets it. Seconds. Linked
// clips move by the same amount. A result outside the source is undone and reported.
function slipTime(seconds) {
    var t = new Time();
    t.ticks = String(Math.round(seconds * TICKS));
    return t;
}

function slipOne(clip, begin) {
    var length = secs(clip.outPoint) - secs(clip.inPoint), was = {begin: secs(clip.inPoint), stop: secs(clip.outPoint)},
        start = secs(clip.start), end = secs(clip.end), limit = null;
    try {
        limit = clip.projectItem.getOutPoint(clip.mediaType === "Audio" ? 2 : 1).seconds;
    } catch (error) {
        limit = null;
    }
    if (begin < -0.0005 || (limit !== null && begin + length > limit + 0.0005)) {
        fail("The slip of " + clip.name + " to source " + begin + "-" + (begin + length) + " s is outside its media"
             + (limit !== null ? " (" + limit + " s)" : ""));
    }
    try {
        clip.inPoint = slipTime(begin);
        clip.outPoint = slipTime(begin + length);
    } catch (failure) {
        clip.inPoint = slipTime(was.begin);
        clip.outPoint = slipTime(was.stop);
        fail("Premiere refused the slip of " + clip.name + ": " + String(failure.message || failure));
    }
    if (Math.abs(secs(clip.inPoint) - begin) > 0.0005 || Math.abs(secs(clip.start) - start) > 0.0005
            || Math.abs(secs(clip.end) - end) > 0.0005) {
        clip.inPoint = slipTime(was.begin);
        clip.outPoint = slipTime(was.stop);
        fail("The slip of " + clip.name + " to source time " + begin + " s is outside its media");
    }
}

function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        shift = A.in_point !== null && A.in_point !== undefined ? A.in_point - secs(clip.inPoint) : A.offset,
        partners = [], i;
    report.sequence = sequence.name;
    report.clip = clip.name;
    report.before = {in_point: secs(clip.inPoint), out_point: secs(clip.outPoint)};
    if (A.with_linked !== false) {
        try {
            each(clip.getLinkedItems(), function (member) {
                if (member.nodeId !== clip.nodeId) {
                    partners.push(member);
                }
            });
        } catch (error) {
            partners = [];
        }
    }
    slipOne(clip, secs(clip.inPoint) + shift);
    for (i = 0; i < partners.length; i++) {
        slipOne(partners[i], secs(partners[i].inPoint) + shift);
    }
    report.after = {in_point: secs(clip.inPoint), out_point: secs(clip.outPoint)};
    report.start = secs(clip.start);
    report.end = secs(clip.end);
    report.linked = partners.length;
}
