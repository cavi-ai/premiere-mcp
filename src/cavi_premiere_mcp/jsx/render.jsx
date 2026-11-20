// Render state of a sequence and preview rendering. Input: {sequence, action (status|render), mode (all|preview)}.
// Ranges are timeline seconds from the QE sequence's red (needs render) and yellow (renders in real time) bars.
function bars(list) {
    var out = [], i;
    for (i = 0; i + 1 < list.length; i += 2) {
        out.push({start: Number(list[i].ticks) / TICKS, end: Number(list[i + 1].ticks) / TICKS});
    }
    return out;
}

function state(report) {
    var qs = qe.project.getActiveSequence();
    report.red = bars(qs.getRedBarTimes());
    report.yellow = bars(qs.getYellowBarTimes());
}

function run(A, report) {
    var sequence = findSequence(A.sequence), qs;
    app.enableQE();
    qs = qe.project.getActiveSequence();
    if (!qs || qs.name !== sequence.name) {
        fail("QE has no active sequence " + sequence.name);
    }
    report.sequence = sequence.name;
    state(report);
    if (A.action === "render") {
        report.before = {red: report.red, yellow: report.yellow};
        if (A.mode === "preview") {
            qs.renderPreview();
        } else {
            qs.renderAll();
        }
        state(report);
    }
}
