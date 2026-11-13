// Import a caption file and make a caption track on a sequence. Input: {sequence, file, start, format
// (subtitle|608|708|teletext|op42|op47|open_ebu)}. Seconds.
function run(A, report) {
    var sequence = findSequence(A.sequence), item, formats = {subtitle: Sequence.CAPTION_FORMAT_SUBTITLE,
        "608": Sequence.CAPTION_FORMAT_608, "708": Sequence.CAPTION_FORMAT_708,
        teletext: Sequence.CAPTION_FORMAT_TELETEXT, op42: Sequence.CAPTION_FORMAT_OP42,
        op47: Sequence.CAPTION_FORMAT_OP47, open_ebu: Sequence.CAPTION_FORMAT_OPEN_EBU};
    try {
        item = findItem(A.file);
    } catch (error) {
        app.project.importFiles([A.file], true, app.project.rootItem, false);
        item = findItem(A.file);
    }
    app.project.openSequence(sequence.sequenceID);
    if (!sequence.createCaptionTrack(item, A.start, formats[A.format])) {
        fail("Premiere did not create the caption track");
    }
    report.sequence = sequence.name;
    report.item = item.name;
}
