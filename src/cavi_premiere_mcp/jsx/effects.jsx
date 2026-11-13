// List the video and audio effects QE offers. Input: {filter} (case-insensitive substring, may be empty).
function names(list, filter) {
    var found = [], i, name;
    for (i = 0; i < list.length; i++) {
        name = String(list[i]);
        if (!filter || name.toLowerCase().indexOf(filter.toLowerCase()) >= 0) {
            found.push(name);
        }
    }
    return found;
}

function run(A, report) {
    app.enableQE();
    report.video = names(qe.project.getVideoEffectList(), A.filter);
    report.audio = names(qe.project.getAudioEffectList(), A.filter);
}
