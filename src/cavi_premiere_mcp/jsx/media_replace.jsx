// Point a project item at a new file, or refresh it when the path is unchanged. Input: {item, path}.
function run(A, report) {
    var source = findItem(A.item), before = mediaPath(source);
    if (sameFile(before, A.path)) {
        source.refreshMedia();
    } else if (!source.changeMediaPath(A.path, true)) {
        fail("Premiere refused to relink " + A.item + " to " + A.path);
    } else {
        source.refreshMedia();
    }
    report.name = source.name;
    report.previous_path = before;
    report.media_path = mediaPath(source);
    report.offline = source.isOffline();
}
