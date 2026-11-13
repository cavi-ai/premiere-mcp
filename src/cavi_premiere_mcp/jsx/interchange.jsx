// Export a sequence as FCP XML, AAF or OMF, or import an FCP XML. Input: {sequence, action (xml|aaf|omf|
// import_xml), path, audio_rate, bits}.
function names() {
    var list = [];
    each(app.project.sequences, function (candidate) {
        list.push(candidate.name);
    });
    return list;
}

function run(A, report) {
    var sequence, before;
    if (A.action === "import_xml") {
        before = names();
        app.project.importFiles([A.path], true, app.project.rootItem, false);
        report.sequences_before = before;
        report.sequences_after = names();
        return;
    }
    sequence = findSequence(A.sequence);
    report.sequence = sequence.name;
    if (A.action === "xml") {
        report.result = sequence.exportAsFinalCutProXML(A.path, 1);
    } else if (A.action === "aaf") {
        report.result = app.project.exportAAF(sequence, A.path, 1, 0, A.audio_rate, A.bits, 0, 0, 0, 0, "", 0, 0);
    } else {
        report.result = app.project.exportOMF(sequence, A.path, sequence.name, A.audio_rate, A.bits, 0, 0, 0, 0, 0);
    }
    report.exists = new File(A.path).exists;
}
