// Open, create, save or close a project. A project already open at the same path is closed first
// because Premiere stalls on a second one at that path.
// Input: {action: open|new|save|close, path, save, close_others}; close_others closes every other
// open project unsaved after open or new.
function closeAt(path) {
    for (var i = app.projects.numProjects - 1; i >= 0; i--) {
        if (sameFile(app.projects[i].path, path)) {
            app.projects[i].closeDocument(0, 0);
        }
    }
}

function closeOthers(path) {
    for (var i = app.projects.numProjects - 1; i >= 0; i--) {
        if (!sameFile(app.projects[i].path, path)) {
            app.projects[i].closeDocument(0, 0);
        }
    }
}

function run(A, report) {
    if (A.action === "open") {
        closeAt(A.path);
        // No conversion, locate-file or warning dialog: a modal dialog stops every later call.
        if (!app.openDocument(A.path, true, true, true, true)) {
            fail("Premiere could not open " + A.path);
        }
        if (A.close_others) {
            closeOthers(A.path);
        }
    } else if (A.action === "new") {
        closeAt(A.path);
        if (!app.newProject(A.path)) {
            fail("Premiere could not create " + A.path);
        }
        if (A.close_others) {
            closeOthers(A.path);
        }
    } else if (A.action === "save") {
        if (!app.project) {
            fail("No project is open");
        }
        app.project.save();
    } else if (A.action === "close") {
        if (!app.project) {
            fail("No project is open");
        }
        report.closed = app.project.path;
        app.project.closeDocument(A.save ? 1 : 0, 0);
    } else {
        fail("Unknown action " + A.action);
    }
    report.open = app.projects.numProjects;
    report.project = app.project ? app.project.path : null;
    report.name = app.project ? app.project.name : null;
    report.sequences = app.project ? app.project.sequences.numSequences : 0;
}
