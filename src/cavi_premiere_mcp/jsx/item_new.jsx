// Create a synthetic project item. Input: {kind, name, bin, width, height, fps, sequence}; size and rate
// default to the sequence's. The item is found by comparing the project's items before and after.
function itemIds() {
    var ids = {};
    walk(app.project.rootItem, function (child) {
        ids[child.nodeId] = child;
    });
    return ids;
}

function run(A, report) {
    var sequence = A.sequence || app.project.activeSequence ? findSequence(A.sequence) : null,
        width = given(A.width) ? A.width : sequence && sequence.frameSizeHorizontal,
        height = given(A.height) ? A.height : sequence && sequence.frameSizeVertical,
        fps = given(A.fps) ? A.fps : sequence && TICKS / Number(sequence.timebase),
        bin = A.bin ? findBin(A.bin, true) : null, before, after, made = null, id, ok;
    if (!width || !height || !fps) {
        fail("Give width, height and fps, or open a sequence");
    }
    app.enableQE();
    // Reading the QE project first binds it to the open project.
    report.qe_items = qe.project.numItems;
    before = itemIds();
    if (A.kind === "black_video") {
        ok = qe.project.newBlackVideo(width, height, fps, 1, 1);
    } else if (A.kind === "transparent_video") {
        ok = qe.project.newTransparentVideo(width, height, fps, 1, 1);
    } else if (A.kind === "bars_and_tone") {
        ok = qe.project.newBarsAndTone(width, height, fps, 1, 1, 48000);
    } else {
        fail("Unknown kind " + A.kind);
    }
    after = itemIds();
    for (id in after) {
        if (!before[id] && !made) {
            made = after[id];
        }
    }
    if (!made) {
        fail("Premiere did not add the item to the project (the call answered " + ok + ")");
    }
    if (A.name) {
        made.name = A.name;
    }
    if (bin) {
        made.moveBin(bin);
    }
    report.name = made.name;
    report.id = made.nodeId;
    report.kind = A.kind;
    report.bin = bin ? bin.name : null;
}
