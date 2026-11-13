// List the video and audio transitions Premiere offers, read from QE. Input: {}.
function names(list) {
    var seen = {}, found = [], i;
    for (i = 0; i < list.length; i++) {
        if (!seen[list[i]]) {
            seen[list[i]] = true;
            found.push(String(list[i]));
        }
    }
    return found;
}

function run(A, report) {
    app.enableQE();
    report.video = names(qe.project.getVideoTransitionList());
    report.audio = names(qe.project.getAudioTransitionList());
}
