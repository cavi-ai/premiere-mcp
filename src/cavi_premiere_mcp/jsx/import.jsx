// Import files into a named bin, created when missing. Input: {files, bin}.
function run(A, report) {
    var bin = findBin(A.bin, true), i, path, wanted = {};
    if (!app.project.importFiles(A.files, true, bin, false)) {
        fail("Premiere could not import " + A.files.join(", "));
    }
    report.bin = A.bin || "";
    report.imported = [];
    for (i = 0; i < A.files.length; i++) {
        wanted[new File(A.files[i]).fsName] = A.files[i];
    }
    each(bin.children, function (child) {
        var path = mediaPath(child);
        if (path && wanted[new File(path).fsName]) {
            report.imported.push({name: child.name, media_path: path});
            delete wanted[new File(path).fsName];
        }
    });
    for (path in wanted) {
        if (wanted.hasOwnProperty(path)) {
            report.warnings.push("Not found in the bin after import: " + wanted[path]);
        }
    }
}
