// Scale a placed clip to the sequence frame: fit shows the whole picture, fill covers the frame. Sets
// the Motion Scale and centers the position. Input: {sequence, kind (video), track, at | position_index, mode}.
// Widths count the pixel aspect ratios of the source and the sequence.

// A pixel aspect ratio given as a number or as "a:b"; 1 when unreadable.
function aspect(text) {
    var part = /^\s*([\d.]+)\s*:\s*([\d.]+)\s*$/.exec(String(text)), value;
    value = part ? Number(part[1]) / Number(part[2]) : Number(text);
    return value > 0 && isFinite(value) ? value : 1;
}

function sourceAspect(item, info) {
    var found;
    try {
        return aspect(item.getFootageInterpretation().pixelAspectRatio);
    } catch (error) {
        found = /\(([\d.]+)\)/.exec(info);
        return found ? aspect(found[1]) : 1;
    }
}

function sequenceAspect(sequence) {
    try {
        return aspect(sequence.getSettings().videoPixelAspectRatio);
    } catch (error) {
        return 1;
    }
}

function run(A, report) {
    var sequence = findSequence(A.sequence), clip = findClip(sequence, "video", A.track, A.at, A.position_index),
        info = field(clip.projectItem.getProjectMetadata(), "VideoInfo") || "", size = /(\d+)\s*x\s*(\d+)/.exec(info),
        width = sequence.frameSizeHorizontal, height = sequence.frameSizeVertical, par, across, ratio, scale = null,
        place = null;
    if (!size) {
        fail("The clip's source frame size is unknown");
    }
    par = sourceAspect(clip.projectItem, info);
    across = width * sequenceAspect(sequence) / (size[1] * par);
    ratio = A.mode === "fill" ? Math.max(across, height / size[2]) : Math.min(across, height / size[2]);
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
    report.pixel_aspect = Math.round(par * 10000) / 10000;
    report.sequence_size = {width: width, height: height};
    report.scale = Math.round(Number(scale.getValue()) * 100) / 100;
}
