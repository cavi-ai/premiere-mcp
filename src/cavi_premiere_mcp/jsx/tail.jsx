(function () {
    var report = {warnings: [], errors: []};
    try {
        run(CAVI_ARGS, report);
    } catch (failure) {
        report.errors.push(String(failure.message || failure) + " (line " + failure.line + ")");
    }
    try {
        save(CAVI_ARGS.report, report);
    } catch (failure) {
        return "ERROR " + String(failure.message || failure);
    }
    return report.errors.length ? "ERROR" : "OK";
})();
