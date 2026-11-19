// Make a sequence the active one, the one the other tools act on when no sequence is given. Input:
// {sequence}: its name or id.
function run(A, report) {
    var sequence = findSequence(A.sequence), active = app.project.activeSequence;
    if (!active || active.sequenceID !== sequence.sequenceID) {
        fail("Premiere did not make " + A.sequence + " the active sequence");
    }
    report.sequence = sequence.name;
    report.id = sequence.sequenceID;
}
