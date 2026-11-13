// Scale a placed clip to the sequence frame: fit shows the whole picture, fill covers the frame. Sets
// the Motion Scale and centers the position. Input: {sequence, kind (video), track, at | position_index, mode}.
function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, "video", A.track, A.at, A.position_index),
        xml = clip.projectItem.getProjectMetadata(), size = /(\d+)\s*x\s*(\d+)/.exec(field(xml, "VideoInfo") || ""),
        width = sequence.frameSizeHorizontal, height = sequence.frameSizeVertical, ratio, scale = null, place = null;
    if (!size) {
        fail("The clip's source frame size is unknown");
    }
    ratio = A.mode === "fill" ? Math.max(width / size[1], height / size[2]) : Math.min(width / size[1], height / size[2]);
    each(clip.components, function (component) {
        if (component.displayName === "Motion") {
            each(component.properties, function (candidate) {
                if (candidate.displayName === "Scale") {
                    scale = candidate;
                } else if (candidate.displayName === "Position") {
                    place = candidate;
                }
            });
        }
    });
    if (!scale || !place) {
        fail("The clip has no Motion component");
    }
    scale.setValue(ratio * 100, true);
    place.setValue([0.5, 0.5], true);
    report.clip = clip.name;
    report.source = {width: Number(size[1]), height: Number(size[2])};
    report.sequence_size = {width: width, height: height};
    report.scale = Math.round(Number(scale.getValue()) * 100) / 100;
}
