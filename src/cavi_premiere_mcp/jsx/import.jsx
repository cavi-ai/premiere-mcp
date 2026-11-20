// Import files, or the compositions of an After Effects project (A.ae_project; A.comps names some, all when
// empty), into a named bin, created when missing. Input: {files, ae_project, comps, bin}.
function importAe(A, bin, report) {
    var known = {};
    walk(app.project.rootItem, function (child) {
        known[child.nodeId] = true;
    });
    if (A.comps && A.comps.length) {
        app.project.importAEComps(A.ae_project, A.comps, bin);
    } else {
        app.project.importAllAEComps(A.ae_project, bin);
    }
    walk(app.project.rootItem, function (child) {
        if (!known[child.nodeId] && !isBin(child)) {
            report.imported.push({name: child.name, id: child.nodeId, media_path: mediaPath(child)});
        }
    });
    if (!report.imported.length) {
        fail("Premiere imported no compositions from " + A.ae_project);
    }
}

function run(A, report) {
    var bin = findBin(A.bin, true), i, path, wanted = {};
    report.bin = A.bin || "";
    report.imported = [];
    if (A.ae_project) {
        importAe(A, bin, report);
        return;
    }
    if (!app.project.importFiles(A.files, true, bin, false)) {
        fail("Premiere could not import " + A.files.join(", "));
    }
    for (i = 0; i < A.files.length; i++) {
        wanted[new File(A.files[i]).fsName] = A.files[i];
    }
    each(bin.children, function (child) {
        var path = mediaPath(child);
        if (path && wanted[new File(path).fsName]) {
            report.imported.push({name: child.name, id: child.nodeId, media_path: path});
            delete wanted[new File(path).fsName];
        }
    });
    for (path in wanted) {
        if (wanted.hasOwnProperty(path)) {
            report.warnings.push("Not found in the bin after import: " + wanted[path]);
        }
    }
}
