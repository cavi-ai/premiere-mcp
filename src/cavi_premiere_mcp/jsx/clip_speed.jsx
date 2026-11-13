// Change a clip's speed through QE setSpeed. Input: {sequence, kind, track, at | position_index,
// speed (percent) | duration (seconds), reverse, maintain_pitch, ripple}. The source range is kept, so
// a faster clip gets shorter and a slower one longer.
function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, A.kind, A.track, A.at, A.position_index),
        item = qeItem(sequence, A.kind, A.track, clip), fps = frameRate(sequence), now = secs(clip.end) - secs(clip.start),
        current = Number(item.speed), speed, length, after;
    if ((A.speed === null || A.speed === undefined) === (A.duration === null || A.duration === undefined)) {
        fail("Give exactly one of speed or duration");
    }
    if (A.speed !== null && A.speed !== undefined) {
        speed = A.speed / 100;
        length = now * current / speed;
    } else {
        length = A.duration;
        speed = now * current / length;
    }
    length = Math.round(length * fps) / fps;
    if (!item.setSpeed(speed, tcOf(length, fps), A.reverse, A.maintain_pitch, A.ripple)) {
        fail("Premiere refused to set the speed");
    }
    each(track(sequence, A.kind, A.track).clips, function (candidate) {
        if (candidate.nodeId === clip.nodeId) {
            after = candidate;
        }
    });
    after = after || clip;
    report.clip = clip.name;
    report.speed = Math.round(Number(qeItem(sequence, A.kind, A.track, after).speed) * 10000) / 100;
    report.reversed = !!after.isSpeedReversed();
    report.start = secs(after.start);
    report.end = secs(after.end);
    report.duration = secs(after.end) - secs(after.start);
}
